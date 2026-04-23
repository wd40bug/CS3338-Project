from collections import Counter
from typing import Literal, Self
from enum import IntEnum, auto
from typing import Callable
from loguru import logger
import msgspec
from typing_extensions import Iterable, Iterator
from rtty_sdr.core.baudot import decode, validate_code
from rtty_sdr.core.options import BaudotOptions, RTTYOpts, Shift
from rtty_sdr.core.protocol import CallsignLen, ChecksumLen, LengthDuplicates, LengthLen, RecvMessage
from rtty_sdr.debug.state_changes import StateChanges
from rtty_sdr.dsp.commands import Command
from rtty_sdr.dsp.decode import DecodeDebug, DecodeYield
from rtty_sdr.core.protocol import phrase
from itertools import batched

class ProtocolState(IntEnum):
    Phrase = auto()
    Length = auto()
    Message = auto()
    Checksum = auto()
    Callsign = auto()


class ProtocolDebug(msgspec.Struct, frozen=True):
    decode: DecodeDebug
    states: list[ProtocolState]

    @classmethod
    def create(cls, decode: list[DecodeDebug], states: list[ProtocolState]) -> Self:
        decode_debug = DecodeDebug.combine(decode)
        assert decode_debug.len == len(states), (
            f"Decode len: {decode_debug.len} and states len {len(states)} don't match"
        )
        return cls(decode=decode_debug, states=states)

    @classmethod
    def combine(cls, debugs: list[Self]) -> Self:
        return cls(
            decode=DecodeDebug.combine([d.decode for d in debugs]),
            states=[state for d in debugs for state in d.states],
        )


class ProtocolDecode:
    def __init__(self, opts: BaudotOptions) -> None:
        self.__state: ProtocolState = ProtocolState.Phrase
        self.__codes: list[int] = []
        self.__msg: str = ""
        self.__callsign: str = ""
        self.__opts = opts
        self.__shift: Shift | None = None
        self.__msg_len: int = 0
        self.__checksum: int = 0

    @property
    def state(self) -> ProtocolState:
        return self.__state

    @property
    def codes(self) -> list[int]:
        return self.__codes

    @staticmethod
    def pack_bits(values: Iterable[int]) -> int:
        values_list = list(values)
        packed_value = 0
        for i, val in enumerate(values_list):
            assert val >= 0 and val < 2**RTTYOpts.data_bits
            shift_amount: int = (len(values_list) - 1 - i) * RTTYOpts.data_bits
            packed_value |= val << shift_amount

        return packed_value

    def update(self, code: int) -> None | RecvMessage:
        self.__codes.append(code)

        match self.__state:
            case ProtocolState.Phrase:
                if len(self.__codes) == len(phrase):
                    if self.__codes == list(phrase):
                        self.__state = ProtocolState.Length
                    else:
                        raise ValueError(
                            f"Did not encounter code phrase ({phrase}). Encountered {self.__codes}"
                        )
            case ProtocolState.Length:
                if len(self.__codes) == (LengthLen * LengthDuplicates) + len(phrase):
                    counts = Counter(
                        map(
                            self.pack_bits,
                            batched(self.__codes[len(phrase) :], LengthLen),
                        )
                    )
                    length, count = counts.most_common(1)[0]
                    if count > LengthDuplicates // 2:
                        self.__msg_len = length
                        logger.trace(f"Receiving message of length {length}")
                        if length > 0:
                            self.__state = ProtocolState.Message
                        else:
                            self.__state = ProtocolState.Checksum
                    else:
                        raise ValueError(
                            f"Failed to get majority for length of {length}. Counts: {counts}"
                        )
            case ProtocolState.Message:
                if not validate_code(
                    code,
                    self.__shift
                    if self.__shift is not None
                    else self.__opts.initial_shift,
                ):
                    raise ValueError(f"Invalid code: {code}")
                char, self.__shift = decode(code, self.__opts, self.__shift)
                self.__msg += char

                if len(self.__codes) == self.__msg_len + (
                    LengthLen * LengthDuplicates
                ) + len(phrase):
                    logger.trace(f"Receiving message with msg '{self.__msg}'")
                    self.__state = ProtocolState.Checksum
                    self.__shift = None
            case ProtocolState.Checksum:
                if (
                    len(self.__codes)
                    == len(phrase)
                    + (LengthLen * LengthDuplicates)
                    + self.__msg_len
                    + ChecksumLen
                ):
                    self.__checksum = self.pack_bits(self.__codes[-ChecksumLen:])
                    logger.trace(f"Receiving message with checksum codes: {self.__codes[-ChecksumLen:]} -> {self.__checksum}")
                    self.__state = ProtocolState.Callsign
            case ProtocolState.Callsign:
                if not validate_code(
                    code,
                    self.__shift
                    if self.__shift is not None
                    else self.__opts.initial_shift,
                ):
                    raise ValueError(f"Invalid code: {code}")
                char, self.__shift = decode(code, self.__opts, self.__shift)
                self.__callsign += char
                if len(self.__callsign) == CallsignLen:
                    return RecvMessage.create(
                        self.__msg,
                        self.__callsign.strip(" "),
                        self.__codes,
                        self.__msg_len,
                        self.__checksum,
                    )

    def reset(self) -> None:
        self.__codes.clear()
        self.__state = ProtocolState.Length
        self.__shift = None
        self.__msg_len = 0
        self.__checksum = 0
        self.__msg = ""
        self.__callsign = ""


class StoppedMsg(msgspec.Struct, frozen=True):
    cmd: Command


type Status = Literal["signal", "signal_lost"]


def protocol(
    code_generator: Iterable[DecodeYield],
    opts: BaudotOptions,
    status_callback: Callable[[Status], None] | None = None,
) -> Iterator[tuple[RecvMessage | StoppedMsg, ProtocolDebug]]:
    protocol = ProtocolDecode(opts)
    debugs: list[DecodeDebug] = []
    index = 0
    states = StateChanges(protocol.state)

    for resp, resp_debug in code_generator:
        if resp_debug.len != 0:
            index = resp_debug.indices[-1]
        debugs.append(resp_debug)
        if resp.kind == "lost_signal":
            protocol.reset()
            states.change(index, protocol.state)
            if status_callback:
                status_callback("signal_lost")
            continue
        elif resp.kind == "command":
            if status_callback:
                # All commands kill this pipeline, so the current message is lost
                status_callback("signal_lost")
            yield (
                StoppedMsg(cmd=resp.command),
                ProtocolDebug.create(debugs, states.build(index, protocol.state)),
            )
            return
        code = resp.code
        try:
            msg = protocol.update(code)
            states.change(index, protocol.state)
            if len(protocol.codes) == 1 and status_callback:
                status_callback("signal")
            if msg is not None:
                logger.debug(f"Decoded message: {msg}")
                yield (
                    msg,
                    ProtocolDebug.create(debugs, states.build(index, protocol.state)),
                )
                protocol.reset()
                debugs.clear()
        except ValueError as e:
            logger.warning(f"{e}: Resetting protocol")
            if status_callback:
                status_callback("signal_lost")
            protocol.reset()
            states.change(index, protocol.state)


def plain_protocol(
    code_generator: Iterable[int], opts: BaudotOptions
) -> Iterator[RecvMessage]:
    protocol = ProtocolDecode(opts)
    for code in code_generator:
        msg = protocol.update(code)
        if msg is not None:
            yield msg
            protocol.reset()
