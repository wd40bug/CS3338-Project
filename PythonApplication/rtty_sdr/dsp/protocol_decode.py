from rtty_sdr.core.protocol import RecvMessage

from typing import Final, Iterator, Self
from enum import IntEnum, auto
from collections.abc import Iterable
from loguru import logger
from rtty_sdr.core.baudot import decode
import msgspec

from rtty_sdr.core.options import BaudotOptions, Shift
from rtty_sdr.debug.state_changes import StateChanges
from rtty_sdr.dsp.poisonPill import Command
from rtty_sdr.dsp.decode import DecodeYield, DecodeDebug

LengthLen: Final[int] = 2
ChecksumLen: Final[int] = 4
CallsignLen: Final[int] = 6

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
        return cls(decode=DecodeDebug.combine(decode), states=states)

    @classmethod
    def combine(cls, debugs: list[Self]) -> Self:
        return cls(
            decode=DecodeDebug.combine([d.decode for d in debugs]),
            states=[state for d in debugs for state in d.states],
        )

class StoppedMsg(msgspec.Struct, frozen=True):
    cmd: Command

def protocol(
    code_generator: Iterable[DecodeYield], opts: BaudotOptions
) -> Iterator[tuple[RecvMessage | StoppedMsg, ProtocolDebug]]:
    shift: Shift | None = None
    state: ProtocolState = ProtocolState.Length
    chars = ""
    data_length = 0
    codes = []
    debugs: list[DecodeDebug] = []
    checksum_start_idx = 0
    states = StateChanges(state)

    for resp, resp_debug in code_generator:
        if len(resp_debug.indices) != 0:
            index = resp_debug.indices[-1]
        elif len(debugs) != 0:
            for debug in reversed(debugs):
                if len(debug.indices) != 0:
                    index = debug.indices[-1]
            else:
                index = 0
        else:
            index = 0
        debugs.append(resp_debug)
        if resp.kind == "lost_signal":
            state = ProtocolState.Length
            states.change(index, state)
            chars = ""
            shift = None
            continue
        elif resp.kind == "command":
            if resp.command.command == "restart":
                yield (
                    StoppedMsg(
                        cmd=resp.command,
                    ),
                    ProtocolDebug.create(
                        debugs,
                        states.build(index, ProtocolState.Length),
                    ),
                )
            elif resp.command.command == "stop":
                yield (
                    StoppedMsg(
                        cmd=resp.command,
                    ),
                    ProtocolDebug.create(
                        debugs,
                        states.build(index, ProtocolState.Length),
                    ),
                )
            return
        code = resp.code

        codes.append(code)
        char, shift = decode(code, opts, shift)
        if char == "":
            continue
        chars += char
        match state:
            case ProtocolState.Length:
                if len(chars) == LengthLen:
                    try:
                        data_length = int(chars, 16)
                    except ValueError:
                        logger.warning(
                            f"Received msg with invalid len field '{chars}' restarting"
                        )
                        chars = ""
                        shift = None
                    state = (
                        ProtocolState.Data
                        if data_length != 0
                        else ProtocolState.Checksum
                    )
                    states.change(index, state)
            case ProtocolState.Data:
                if len(chars) == LengthLen + data_length:
                    state = ProtocolState.Checksum
                    states.change(index, state)
            case ProtocolState.Checksum:
                # Start
                if len(chars) == LengthLen + data_length:
                    checksum_start_idx = len(codes)
                # End
                if len(chars) == LengthLen + data_length + ChecksumLen:
                    state = ProtocolState.Callsign
                    states.change(index, state)
            case ProtocolState.Callsign:
                if len(chars) == LengthLen + data_length + ChecksumLen + CallsignLen:
                    msg = chars[LengthLen : LengthLen + data_length]
                    checksum = chars[
                        LengthLen + data_length : LengthLen + data_length + ChecksumLen
                    ]
                    callsign = chars[LengthLen + data_length + ChecksumLen :]
                    state = ProtocolState.Length
                    yield (
                        RecvMessage.create(
                            msg,
                            callsign,
                            chars,
                            codes,
                            checksum_start_idx,
                            checksum,
                        ),
                        ProtocolDebug.create(debugs, states.build(index, state)),
                    )
                    debugs.clear()
                    chars = ""
                    shift = None
