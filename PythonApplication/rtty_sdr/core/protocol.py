import crcmod.predefined
from loguru import logger
import msgspec
from typing import Self

from numpy.random.mtrand import random

import copy

from rtty_sdr.core.options import BaudotOptions, Shift
from rtty_sdr.core.baudot import decode, encode



crc16_xmodem = crcmod.predefined.mkCrcFun("xmodem")


def calculate_checksum(codes: list[int]) -> int:
    return crc16_xmodem(bytes(codes))


class ProtocolMessage(msgspec.Struct, frozen=True):
    """Representation of a message

    Attributes:
        msg: actual message
        callsign: 
        encoding: 
        codes: baudot codes as integers
        checksum: (may or may not be valid)
    """
    msg: str
    callsign: str
    encoding: str
    codes: list[int]
    checksum: int

def corrupt(codes: list[int], corruption: float) -> list[int]:
    corrupted_codes: list[int] = []
    for code in codes:
        new_code = code
        for bit_index in range(0, 5):
            if random() < corruption:
                new_code ^= 1 << bit_index
        corrupted_codes.append(new_code)
    return corrupted_codes

class SendMessage(ProtocolMessage, frozen=True):
    original_codes: list[int]
    original_encoding: str
    original_msg: str
    @classmethod
    def create(cls, msg: str, callsign: str, opts: BaudotOptions, corruption: float = 0.0) -> Self:
        length_str = f"{len(msg):02X}"

        len_encoding, pre_msg_shift = encode(length_str, opts)
        msg_encoding, shift = encode(msg, opts, pre_msg_shift)

        checksum = calculate_checksum(len_encoding + msg_encoding)
        checksum_str = f"{checksum:04X}"
        checksum_encoding, shift = encode(checksum_str, opts, shift)
        callsign_encoding, _ = encode(callsign, opts, shift)

        encoding = f"{length_str}{msg}{checksum_str}{callsign}".upper()
        codes = len_encoding + msg_encoding + checksum_encoding + callsign_encoding

        new_opts = copy.replace(opts, replace_invalid_with = "�")
        corrupted_msg_encoding = corrupt(msg_encoding, corruption)
        corrupted_msg, _ = decode(corrupted_msg_encoding, new_opts, pre_msg_shift)
        corrupted_codes = copy.deepcopy(codes)
        corrupted_codes[len(len_encoding):len(len_encoding) + len(corrupted_msg_encoding)] = corrupted_msg_encoding
        corrupted_encoding = f"{length_str}{corrupted_msg}{checksum_str}{callsign}"

        return cls(
            msg=corrupted_msg,
            original_msg=msg,
            callsign=callsign,
            checksum=checksum,
            original_encoding=encoding,
            encoding=corrupted_encoding,
            original_codes=codes,
            codes=corrupted_codes
        )

class RecvMessage(ProtocolMessage, frozen=True):
    """A Message received by the protocol

    Attributes:
        calculatedChecksum: 
        validChecksum: whether the calculatedChecksum matches the message checksum
    """
    calculated_checksum: int
    valid_checksum: bool

    msg_start_idx: int
    msg_codes_len: int
    msg_start_shift: Shift

    @classmethod
    def create(
        cls,
        msg: str,
        callsign: str,
        encoding: str,
        codes: list[int],
        msg_start_idx: int,
        msg_start_shift: Shift,
        checksum_start_idx: int,
        checksum_str: str,
    ) -> Self:
        checksum = int(checksum_str, 16)
        calculatedChecksum = calculate_checksum(codes[:checksum_start_idx])
        logger.trace(f"Codes: {codes}, checksum_start: {checksum_start_idx}, calculatedChecksum: {calculatedChecksum:4x}")
        return cls(
            msg=msg,
            callsign=callsign,
            encoding=encoding,
            codes=codes,
            checksum=checksum,
            calculated_checksum=calculatedChecksum,
            valid_checksum=calculatedChecksum == checksum,
            msg_start_idx=msg_start_idx,
            msg_codes_len=checksum_start_idx - msg_start_idx,
            msg_start_shift=msg_start_shift,
        )
