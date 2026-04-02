from collections.abc import Iterable
from rtty_sdr.core.baudot import BaudotDecoder, BaudotEncoder
import crcmod.predefined
from typing import Final, Iterator, Self
from enum import IntEnum, auto
from rtty_sdr.debug.state_changes import StateChanges
from rtty_sdr.dsp.decode import DecodeYield, DecodeDebug
import numpy as np
import numpy.typing as npt
import msgspec

LengthLen: Final[int] = 2
ChecksumLen: Final[int] = 4
CallsignLen: Final[int] = 6

crc16_xmodem = crcmod.predefined.mkCrcFun("xmodem")


def calculate_checksum(codes: list[int]) -> int:
    return crc16_xmodem(bytes(codes))


class ProtocolMessage(msgspec.Struct, frozen=True):
    msg: str
    callsign: str
    encoding: str
    codes: list[int]
    checksum: int


class SendMessage(ProtocolMessage, frozen=True):
    @classmethod
    def create(
        cls,
        msg: str,
        callsign: str,
        encoder: BaudotEncoder,
        replace_invalid_with: str | None = None,
    ) -> Self:
        length_str = f"{len(msg):02x}"
        pre_checksum = encoder.encode(length_str + msg, replace_invalid_with)
        checksum = calculate_checksum(pre_checksum)
        checksum_str = f"{checksum:4x}".upper()
        encoding = f"{length_str}{msg.upper()}{checksum_str}{callsign.upper()}"
        codes = pre_checksum + encoder.encode(checksum_str + callsign)
        return cls(
            msg=msg,
            callsign=callsign,
            checksum=checksum,
            encoding=encoding,
            codes=codes,
        )

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
        return cls(
            decode=DecodeDebug.combine(decode),
            states=states
        )


class RecvMessage(ProtocolMessage, frozen=True):
    calculatedChecksum: int
    validChecksum: bool
    debug: ProtocolDebug

    @classmethod
    def create(
        cls,
        msg: str,
        callsign: str,
        encoding: str,
        codes: list[int],
        checksum_start_idx: int,
        checksum_str: str,
        decode_debug: list[DecodeDebug],
        states: list[ProtocolState],
    ) -> Self:
        checksum = int(checksum_str, 16)
        calculatedChecksum = calculate_checksum(codes[:checksum_start_idx])
        return cls(
            msg=msg,
            callsign=callsign,
            encoding=encoding,
            codes=codes,
            checksum=checksum,
            calculatedChecksum=calculatedChecksum,
            validChecksum=calculatedChecksum == checksum,
            debug = ProtocolDebug.create(decode_debug, states)
        )



def protocol(
    code_generator: Iterable[DecodeYield], decoder: BaudotDecoder
) -> Iterator[RecvMessage | ProtocolDebug]:
    state: ProtocolState = ProtocolState.Length
    chars = ""
    data_length = 0
    codes = []
    debugs: list[DecodeDebug] = []
    checksum_start_idx = 0
    states = StateChanges(state)

    for code, resp_debug in code_generator:
        debugs.append(resp_debug)
        if code == "reset":
            state = ProtocolState.Length
            states.change(resp_debug.indices[-1], state)
            chars = ""
            continue
        if code == "end":
            yield ProtocolDebug.create(debugs, states.build(resp_debug.indices[-1], ProtocolState.Length))
            return
            
        codes.append(code)
        char = decoder.decode(code)
        if char == "":
            continue
        chars += char
        match state:
            case ProtocolState.Length:
                if len(chars) == LengthLen:
                    data_length = int(chars, 16)
                    state = (
                        ProtocolState.Data
                        if data_length != 0
                        else ProtocolState.Checksum
                    )
                    states.change(resp_debug.indices[-1], state)
            case ProtocolState.Data:
                if len(chars) == LengthLen + data_length:
                    state = ProtocolState.Checksum
                    states.change(resp_debug.indices[-1], state)
            case ProtocolState.Checksum:
                # Start
                if len(chars) == LengthLen + data_length:
                    checksum_start_idx = len(codes)
                # End
                if len(chars) == LengthLen + data_length + ChecksumLen:
                    state = ProtocolState.Callsign
                    states.change(resp_debug.indices[-1], state)
            case ProtocolState.Callsign:
                if len(chars) == LengthLen + data_length + ChecksumLen + CallsignLen:
                    msg = chars[LengthLen : LengthLen + data_length]
                    checksum = chars[
                        LengthLen + data_length : LengthLen + data_length + ChecksumLen
                    ]
                    callsign = chars[LengthLen + data_length + ChecksumLen :]
                    state = ProtocolState.Length
                    yield RecvMessage.create(
                        msg,
                        callsign,
                        chars,
                        codes,
                        checksum_start_idx,
                        checksum,
                        debugs,
                        states.build(
                            resp_debug.indices[-1], state
                        ),
                    )
                    debugs.clear()
