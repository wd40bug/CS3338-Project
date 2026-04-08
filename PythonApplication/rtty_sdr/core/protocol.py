import crcmod.predefined
import msgspec
from typing import Self

from rtty_sdr.core.options import BaudotOptions
from rtty_sdr.core.baudot import encode



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
    def create(cls, msg: str, callsign: str, opts: BaudotOptions) -> Self:
        length_str = f"{len(msg):02x}"
        pre_checksum, state = encode(length_str + msg, opts)
        checksum = calculate_checksum(pre_checksum)
        checksum_str = f"{checksum:4x}".upper()
        encoding = f"{length_str}{msg.upper()}{checksum_str}{callsign.upper()}"
        codes = pre_checksum + encode(checksum_str + callsign, opts, state)[0]
        return cls(
            msg=msg,
            callsign=callsign,
            checksum=checksum,
            encoding=encoding,
            codes=codes,
        )

class RecvMessage(ProtocolMessage, frozen=True):
    calculatedChecksum: int
    validChecksum: bool

    @classmethod
    def create(
        cls,
        msg: str,
        callsign: str,
        encoding: str,
        codes: list[int],
        checksum_start_idx: int,
        checksum_str: str,
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
        )

