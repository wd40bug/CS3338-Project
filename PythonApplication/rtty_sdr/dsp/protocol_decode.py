from typing import Literal, Self
from copy import replace
from enum import IntEnum, auto
from typing import Callable
from loguru import logger
import msgspec
from typing_extensions import Iterable, Iterator
from rtty_sdr.core.baudot import decode, validate_code
from rtty_sdr.core.options import BaudotOptions, RTTYOpts, Shift
from rtty_sdr.core.protocol import (
    CallsignLen,
    ChecksumLen,
    LengthDuplicates,
    LengthLen,
    MsgStart,
    RecvMessage,
)
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
    def __init__(self, opts: BaudotOptions, skip_unknown_baudot: bool = True) -> None:
        self.__state: ProtocolState = ProtocolState.Phrase
        self.__codes: list[int] = []
        self.__opts = opts
        self.__shift: Shift | None = None
        self.__msg_len: int = 0
        self.__checksum: int = 0
        self.__callsign = ""
        self.__skip = skip_unknown_baudot

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
        logger.trace(f"Protocol received code {code}")
        self.__codes.append(code)

        match self.__state:
            case ProtocolState.Phrase:
                if len(self.__codes) == len(phrase):
                    if self.__codes == list(phrase):
                        logger.trace(f"Found phrase: {self.__codes}")
                        self.__state = ProtocolState.Length
                    else:
                        raise RuntimeError(
                            f"Did not encounter code phrase ({phrase}). Encountered {self.__codes}"
                        )
            case ProtocolState.Length:

                def QMR(nums: Iterable[tuple[int, int]]) -> int:
                    length_len_bits = LengthLen * RTTYOpts.data_bits
                    counts: list[int] = [0] * length_len_bits
                    for length in nums:
                        len = self.pack_bits(length)
                        logger.trace(len)
                        for i in range(0, length_len_bits):
                            bit = (len & 1 << i) != 0
                            counts[i] += 1 if bit else -1

                    ret: int = 0
                    logger.trace(f"{list(reversed(counts))}")
                    for i, count in reversed(list(enumerate(counts))):
                        if count > 0:
                            ret |= 1 << i
                        elif count == 0:
                            raise RuntimeError(
                                f"Failed to get majority for bit {length_len_bits - i}"
                            )
                    return ret

                if len(self.__codes) == (LengthLen * LengthDuplicates) + len(phrase):
                    length = QMR(
                        [
                            (self.__codes[i], self.__codes[i + 1])
                            for i in range(len(phrase), len(self.__codes), LengthLen)
                        ]
                    )
                    self.__msg_len = length
                    logger.debug(
                        f"Found msg with length: {length}, from codes: {self.__codes[len(phrase) :]}"
                    )
                    if length > 0:
                        self.__state = ProtocolState.Message
                    else:
                        self.__state = ProtocolState.Checksum
            case ProtocolState.Message:
                if len(self.__codes) == self.__msg_len + (
                    LengthLen * LengthDuplicates
                ) + len(phrase):
                    msg_codes = self.__codes[-self.__msg_len :]
                    try:
                        msg, _ = decode(msg_codes, self.__opts)
                        logger.trace(f"Receiving message with msg '{msg}'")
                    except ValueError as e:
                        logger.debug(f"{e} continuing")
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
                    logger.trace(
                        f"Receiving message with checksum codes: {self.__codes[-ChecksumLen:]} -> {self.__checksum}"
                    )
                    self.__state = ProtocolState.Callsign
            case ProtocolState.Callsign:
                if validate_code(
                    code,
                    self.__shift
                    if self.__shift is not None
                    else self.__opts.initial_shift,
                ):
                    char, self.__shift = decode(code, self.__opts, self.__shift)
                else:
                    char = " "
                self.__callsign += char
                if len(self.__callsign) == CallsignLen:
                    if self.__skip:
                        local_baudot = replace(
                            self.__opts, replace_invalid_with="\ufffd"
                        )
                    else:
                        local_baudot = self.__opts
                    msg_codes = self.__codes[MsgStart : MsgStart + self.__msg_len]
                    msg, _ = decode(msg_codes, local_baudot)
                    return RecvMessage.create(
                        msg,
                        self.__callsign.strip(" "),
                        self.__codes,
                        self.__msg_len,
                        self.__checksum,
                    )

    def reset(self) -> None:
        self.__codes.clear()
        self.__state = ProtocolState.Phrase
        self.__shift = None
        self.__msg_len = 0
        self.__callsign = ""
        self.__checksum = 0


class StoppedMsg(msgspec.Struct, frozen=True):
    cmd: Command


type Status = Literal["signal", "signal_lost"]


def protocol(
    code_generator: Iterable[DecodeYield],
    opts: BaudotOptions,
    status_callback: Callable[[Status, str], None] | None = None,
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
                status_callback("signal_lost", "Squelched")
            continue
        elif resp.kind == "command":
            if status_callback:
                # All commands kill this pipeline, so the current message is lost
                status_callback("signal_lost", "Closed")
            yield (
                StoppedMsg(cmd=resp.command),
                ProtocolDebug.create(debugs, states.build(index, protocol.state)),
            )
            return
        code = resp.code
        try:
            msg = protocol.update(code)
            states.change(index, protocol.state)
            if len(protocol.codes) == len(phrase) and status_callback and protocol.state == ProtocolState.Length:
                status_callback("signal", "Codephrase Received")
            if msg is not None:
                logger.debug(f"Decoded message: {msg}")
                yield (
                    msg,
                    ProtocolDebug.create(debugs, states.build(index, protocol.state)),
                )
                protocol.reset()
                debugs.clear()
        except ValueError as e:
            logger.warning(f"{e}: Skipping")
        except RuntimeError as e:
            logger.warning(f"{e}: Resetting protocol")
            if status_callback:
                status_callback("signal_lost", "Error")
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
