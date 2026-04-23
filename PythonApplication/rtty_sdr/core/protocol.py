from loguru import logger
import msgspec
from typing import Final, Self

from numpy.random.mtrand import random

import copy

from rtty_sdr.core.generic_crc import GenericCRC
from rtty_sdr.core.options import BaudotOptions, RTTYOpts
from rtty_sdr.core.baudot import decode, encode

phrase: list[int] = [0x15, 0x0A, 0x15]
LengthLen: Final[int] = 2
LengthDuplicates: Final[int] = 5
ChecksumLen: Final[int] = 4
CallsignLen: Final[int] = 6

crc20 = GenericCRC("CRC20 0xb5827", 20, 0xB5827)


def calculate_checksum(codes: list[int]) -> int:
    return crc20.Calculate(bytes(codes))


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

    def __str__(self) -> str:
        return f"Message from {self.callsign}: {self.msg} (Codes: {self.codes}, Checksum: {self.checksum})"


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
    corrupted_msg: str

    @classmethod
    def create(
        cls, msg: str, callsign: str, opts: BaudotOptions, corruption: float = 0.0
    ) -> Self:
        def unpack_bits(num: int, numchunks: int) -> list[int]:
            codes: list[int] = []
            mask = 2**RTTYOpts.data_bits - 1
            while num > 0:
                codes.append(num & mask)
                num >>= RTTYOpts.data_bits

            codes = codes[::-1]

            if len(codes) < numchunks:
                for _ in range(len(codes), numchunks):
                    codes.insert(0, 0)
            return codes

        msg_encoding, _ = encode(msg, opts)
        length = len(msg_encoding)

        checksum = calculate_checksum(msg_encoding)

        lencodes = unpack_bits(length, LengthLen)

        checkcodes = unpack_bits(checksum, ChecksumLen)
        logger.trace(f"Codes for checksum: {checksum} are {checkcodes}")

        callsign_encoding, _ = encode(callsign, opts)

        codes: list[int] = (
            phrase
            + lencodes * LengthDuplicates
            + msg_encoding
            + checkcodes
            + callsign_encoding
        )

        corrupted_codes = codes
        corrupted_codes[len(phrase) : -CallsignLen] = corrupt(
            codes[len(phrase) : -CallsignLen], corruption
        )
        corrupted_msg_codes = corrupted_codes[len(phrase) : -(CallsignLen + ChecksumLen)]

        new_opts = copy.replace(opts, replace_invalid_with="�")
        corrupted_msg, _ = decode(corrupted_msg_codes, new_opts)

        return cls(
            msg=msg,
            corrupted_msg=corrupted_msg,
            callsign=callsign,
            checksum=checksum,
            original_codes=codes,
            codes=corrupted_codes,
        )


class RecvMessage(ProtocolMessage, frozen=True):
    """A Message received by the protocol

    Attributes:
        calculatedChecksum:
        validChecksum: whether the calculatedChecksum matches the message checksum
    """

    calculated_checksum: int
    valid_checksum: bool

    received_codes: None | list[int]

    msg_start_idx: int
    msg_codes_len: int

    @classmethod
    def create(
        cls,
        msg: str,
        callsign: str,
        codes: list[int],
        msg_codes_len: int,
        checksum: int,
        received_codes: None | list[int] = None
    ) -> Self:
        msg_start_idx = len(phrase) + (LengthLen * LengthDuplicates)
        checksum_start_idx = msg_start_idx + msg_codes_len
        calculatedChecksum = calculate_checksum(codes[:checksum_start_idx])
        logger.trace(
            f"Codes: {codes}, checksum_start: {checksum_start_idx}, calculatedChecksum: {calculatedChecksum:4x}"
        )
        return cls(
            msg=msg,
            callsign=callsign,
            codes=codes,
            checksum=checksum,
            calculated_checksum=calculatedChecksum,
            valid_checksum=calculatedChecksum == checksum,
            msg_start_idx=msg_start_idx,
            msg_codes_len=msg_codes_len,
            received_codes=received_codes
        )
