from collections.abc import Iterable
from dataclasses import dataclass
from rtty_sdr.core.baudot import BaudotDecoder, BaudotEncoder
import crcmod.predefined
from typing import Final, Iterator
from enum import StrEnum, auto
from rtty_sdr.debug.debug_types import DebugCombineable
from rtty_sdr.dsp.decode import DecodeYield, DecodeDebug
from rtty_sdr.debug.annotations import DebugAnnotations
import numpy as np
import numpy.typing as npt

from rtty_sdr.dsp.squelch import SquelchDebug

LengthLen: Final[int] = 2
ChecksumLen: Final[int] = 4
CallsignLen: Final[int] = 6

crc16_xmodem = crcmod.predefined.mkCrcFun("xmodem")


def calculate_checksum(codes: list[int]) -> int:
    return crc16_xmodem(bytes(codes))


@dataclass(frozen=True)
class ProtocolMessage:
    msg: str
    callsign: str
    encoding: str
    codes: list[int]
    checksum: int


class SendMessage(ProtocolMessage):
    def __init__(
        self,
        msg: str,
        callsign: str,
        encoder: BaudotEncoder,
        replace_invalid_with: str | None = None,
    ) -> None:
        length_str = f"{len(msg):02x}"
        pre_checksum = encoder.encode(length_str + msg, replace_invalid_with)
        checksum = calculate_checksum(pre_checksum)
        checksum_str = f"{checksum:4x}".upper()
        encoding = f"{length_str}{msg.upper()}{checksum_str}{callsign.upper()}"
        codes = pre_checksum + encoder.encode(checksum_str + callsign)
        super().__init__(msg, callsign, encoding, codes, checksum)

class ProtocolDebug:
    def __init__(self, decode: list[DecodeDebug]) -> None:
        self.decode = DecodeDebug.combine(decode)


class RecvMessage(ProtocolMessage):
    calculatedChecksum: Final[int]
    validChecksum = Final[bool]

    def __init__(
        self,
        msg: str,
        callsign: str,
        encoding: str,
        codes: list[int],
        checksum_start_idx: int,
        checksum_str: str,
        decode_debug: list[DecodeDebug],
    ):
        checksum = int(checksum_str, 16)
        super().__init__(msg, callsign, encoding, codes, checksum)
        self.calculatedChecksum = calculate_checksum(codes[:checksum_start_idx])
        self.validChecksum = self.calculatedChecksum == self.checksum
        self.debug: ProtocolDebug = ProtocolDebug(
            decode_debug
        )


def protocol(
    code_generator: Iterable[DecodeYield], decoder: BaudotDecoder
) -> Iterator[RecvMessage]:
    class ProtocolState(StrEnum):
        Length = auto()
        Data = auto()
        Checksum = auto()
        Callsign = auto()

    state: ProtocolState = ProtocolState.Length
    chars = ""
    data_length = 0
    codes = []
    debugs = []
    checksum_start_idx = 0

    for response in code_generator:
        assert response != "reset"
        code, resp_debug = response
        debugs.append(resp_debug)
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
            case ProtocolState.Data:
                if len(chars) == LengthLen + data_length:
                    state = ProtocolState.Checksum
            case ProtocolState.Checksum:
                if len(chars) == LengthLen + data_length:
                    checksum_start_idx = len(codes)
                if len(chars) == LengthLen + data_length + ChecksumLen:
                    state = ProtocolState.Callsign
            case ProtocolState.Callsign:
                if len(chars) == LengthLen + data_length + ChecksumLen + CallsignLen:
                    state = ProtocolState.Length
                    msg = chars[LengthLen : LengthLen + data_length]
                    checksum = chars[
                        LengthLen + data_length : LengthLen + data_length + ChecksumLen
                    ]
                    callsign = chars[LengthLen + data_length + ChecksumLen :]
                    yield RecvMessage(
                        msg,
                        callsign,
                        chars,
                        codes,
                        checksum_start_idx,
                        checksum,
                        debugs,
                    )
                    debugs.clear()
