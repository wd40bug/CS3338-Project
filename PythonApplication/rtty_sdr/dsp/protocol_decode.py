from typing import Literal, Self
from enum import IntEnum, auto
from typing import Callable, Final
from loguru import logger
import msgspec
from typing_extensions import Iterable, Iterator
from rtty_sdr.core.baudot import decode, validate_code
from rtty_sdr.core.options import BaudotOptions, Shift
from rtty_sdr.core.protocol import RecvMessage
from rtty_sdr.debug.state_changes import StateChanges
from rtty_sdr.dsp.commands import Command
from rtty_sdr.dsp.decode import DecodeDebug, DecodeYield

LengthLen: Final[int] = 2
ChecksumLen: Final[int] = 4
CallsignLen: Final[int] = 6
HexChars: Final[list[str]] = [
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
]


class ProtocolState(IntEnum):
    Length = auto()
    Data = auto()
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
        self.__state: ProtocolState = ProtocolState.Length
        self.__codes: list[int] = []
        self.__chars = ""
        self.__opts = opts
        self.__shift: Shift | None = None
        self.__msg_len: int = 0
        self.__checksum: str = ""
        self.__msg_start_idx: int = 0
        self.__msg_start_shift: Shift = opts.initial_shift

    @property
    def state(self) -> ProtocolState:
        return self.__state

    @property
    def codes(self) -> list[int]:
        return self.__codes

    def update(self, code: int) -> None | RecvMessage:
        if not validate_code(
            code,
            self.__shift if self.__shift is not None else self.__opts.initial_shift,
        ):
            raise ValueError(f"Invalid code: {code}")

        self.__codes.append(code)
        char, self.__shift = decode(code, self.__opts, self.__shift)
        self.__chars += char
        if char == "":
            # Shift character
            return

        match self.__state:
            case ProtocolState.Length:
                if not char in HexChars:
                    raise ValueError(
                        f"Encountered non-numeric character '{char}' when parsing length field, restarting"
                    )
                if len(self.__chars) == LengthLen:
                    self.__msg_len = int(self.__chars, 16)
                    self.__state = (
                        ProtocolState.Data
                        if self.__msg_len != 0
                        else ProtocolState.Checksum
                    )
                    # TODO: move this to checksum field
                    self.__checksum_start_index = len(self.__codes)
                    self.__msg_start_idx = len(self.__codes)
                    self.__msg_start_shift = self.__shift
            case ProtocolState.Data:
                if len(self.__chars) == LengthLen + self.__msg_len:
                    self.__state = ProtocolState.Checksum
                    self.__checksum_start_index = len(self.__codes)
            case ProtocolState.Checksum:
                if not char in HexChars:
                    raise ValueError(
                        f"Encountered non-numeric character '{char}' when parsing checksum field, restarting"
                    )
                if len(self.__chars) == LengthLen + self.__msg_len + ChecksumLen:
                    self.__checksum = self.__chars[
                        LengthLen + self.__msg_len : LengthLen
                        + self.__msg_len
                        + ChecksumLen
                    ]
                    self.__state = ProtocolState.Callsign
            case ProtocolState.Callsign:
                if (
                    len(self.__chars)
                    == LengthLen + self.__msg_len + ChecksumLen + CallsignLen
                ):
                    msg = self.__chars[LengthLen : LengthLen + self.__msg_len]
                    callsign = self.__chars[LengthLen + self.__msg_len + ChecksumLen :]
                    self.__state = ProtocolState.Length
                    return RecvMessage.create(
                        msg,
                        callsign,
                        self.__chars,
                        self.__codes,
                        self.__msg_start_idx,
                        self.__msg_start_shift,
                        self.__checksum_start_index,
                        self.__checksum,
                    )

    def reset(self) -> None:
        self.__codes.clear()
        self.__chars = ""
        self.__state = ProtocolState.Length
        self.__shift = None
        self.__msg_len = 0
        self.__checksum = ""
        self.__msg_start_idx = 0
        self.__msg_start_shift = self.__opts.initial_shift


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
                # All commands kill this pipeline, so the message is lost
                status_callback("signal_lost")
            yield (
                StoppedMsg(cmd=resp.command),
                ProtocolDebug.create(debugs, states.build(index, protocol.state)),
            )
            return
        code = resp.code
        try:
            msg = protocol.update(code)
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
