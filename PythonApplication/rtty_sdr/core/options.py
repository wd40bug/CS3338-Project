# from dataclasses import dataclass, field
from typing import Final, Literal, ClassVar

from msgspec import Struct


class RTTYOpts(Struct, frozen=True):
    stop_bits: float = 1.5
    baud: float = 45.45
    mark: int = 2125
    shift: int = 170
    pre_msg_stops: int = 0
    post_msg_stops: int = 0

    data_bits: ClassVar[Final[int]] = 5

    @property
    def space(self):
        return self.mark + self.shift

    @property
    def seconds_per_bit(self) -> float:
        return 1 / self.baud

    @property
    def bits_per_character(self) -> float:
        return 1 + self.data_bits + self.stop_bits

    def __str__(self) -> str:
        return f"Mark: {self.mark}, Space: {self.space}, Baud: {self.baud}"


class SignalOpts(Struct, frozen=True):
    Fs: int
    rtty: RTTYOpts

    @property
    def nsamp(self):
        return round(self.Fs / self.rtty.baud)


class DecodeCommon(Struct, frozen=True):
    oversampling: int
    signal: SignalOpts

    @property
    def chunk_size(self) -> int:
        return self.signal.nsamp // self.oversampling


class GoertzelOpts(Struct, frozen=True):
    overlap_ratio: float
    dft_len: int
    decode: DecodeCommon

    @property
    def overlap_size(self) -> int:
        return round(self.decode.chunk_size * self.overlap_ratio)


class EnvelopeOpts(Struct, frozen=True):
    envelopes_order: int
    decode: DecodeCommon


class SquelchOpts(Struct, frozen=True):
    lower_thresh: float
    upper_thresh: float
    decode: DecodeCommon
    order: int = 4
    envelopes_order: int = 4
    bw_safety_margin: float = 2


class DecodeStreamOpts(Struct, frozen=True):
    squelch_grace_percent: float
    idle_bits: float
    none_friction: float
    decode: DecodeCommon

    @property
    def squelch_grace_period(self) -> int:
        return round(self.squelch_grace_percent * self.decode.chunk_size)

    @property
    def idle_samples(self) -> int:
        return round(self.idle_bits * self.decode.chunk_size)


class SystemOpts(Struct, frozen=True):
    # Stem configs
    rtty: RTTYOpts
    signal: SignalOpts
    decode: DecodeCommon

    # Leaf configs
    envelope: EnvelopeOpts
    goertzel: GoertzelOpts
    squelch: SquelchOpts
    stream: DecodeStreamOpts

    # System Options
    engine: Literal["goertzel", "envelope"]
    source: Literal["microphone", "internal"]

    @classmethod
    def default(cls) -> SystemOpts:
        rtty = RTTYOpts()
        signal = SignalOpts(Fs=8000, rtty=rtty)
        decode = DecodeCommon(oversampling=5, signal=signal)

        return cls(
            rtty=rtty,
            signal=signal,
            decode=decode,
            envelope=EnvelopeOpts(envelopes_order=4, decode=decode),
            goertzel=GoertzelOpts(overlap_ratio=0.5, dft_len=256, decode=decode),
            squelch=SquelchOpts(lower_thresh=0.2, upper_thresh=2, decode=decode),
            stream=DecodeStreamOpts(
                squelch_grace_percent=0.25,
                idle_bits=2,
                decode=decode,
                none_friction=0.1,
            ),
            engine="goertzel",
            source="microphone",
        )
