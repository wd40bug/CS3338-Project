import crcmod.predefined
from loguru import logger
import msgspec
from typing import Self

from numpy.random.mtrand import random

import copy

from rtty_sdr.core.options import BaudotOptions, Shift
from rtty_sdr.core.baudot import decode, encode

phrase: list[int] = [0x15, 0x0A, 0x15]

crc16_xmodem = crcmod.predefined.mkCrcFun("xmodem")


def calculate_checksum(codes: list[int]) -> int:
    return crc16_xmodem(bytes(codes))


class ProtocolMessage(msgspec.Struct, frozen=True):
    """Representation of a message

    Attributes:
        msg: actual message
        callsign: 
        codes: baudot codes as integers
        checksum: (may or may not be valid)
    """
    msg: str
    callsign: str
    codes: list[int]
    checksum: int
    def __str__(self) -> str: return f"Message from {self.callsign}: {self.msg} (Codes: {self.codes}, Checksum: {self.checksum:04X})"

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
        def chunk_bits(num: int, numchunks: int) -> list[int]:
            bits: list[int] = []
            mask = 31
            while num > 0:
                bits.append(num & mask)
                num >>= 5
                
            bits = bits[::-1]
            
            if len(bits) < numchunks:
                for i in range(len(bits), numchunks):
                    bits.append(0)
            return bits
    
        length = len(msg)

        msg_encoding = encode(msg, opts)

        checksum = calculate_checksum(msg_encoding)

        lencodes = chunk_bits(length)

        checkcodes = chunk_bits(checksum)

        callsign_encoding, _ = encode(callsign, opts)

        codes = phrase + [lencodes] * 3 + msg_encoding + [checkcodes] + callsign_encoding

        new_opts = copy.replace(opts, replace_invalid_with = "�")
        corrupted_msg_encoding = corrupt(msg_encoding[3:7], corruption)

        corrupted_msg, _ = decode(corrupted_msg_encoding, new_opts)
        corrupted_codes = copy.deepcopy(codes)
        corrupted_codes[3:7] = corrupted_msg_encoding

        return cls(
            msg=corrupted_msg,
            original_msg=msg,
            callsign=callsign,
            checksum=checksum,
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
