from dataclasses import dataclass, field
from typing import Final


@dataclass
class RTTYOpts:
    stop_bits: float = 1.5
    baud: float = 45.45
    mark: int = 2125
    shift: int = 170
    pre_msg_stops: int = 0
    post_msg_stops: int = 0

    data_bits: Final[int] = field(init=False, default=5)

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

@dataclass
class EnvelopeOpts:
    envelopes_order: int
    decode: DecodeCommon

@dataclass
class GoertzelOpts:
    overlap_ratio: float
    dft_len: int
    decode: DecodeCommon

    @property
    def overlap_size(self) -> int:
        return round(self.decode.chunk_size * self.overlap_ratio)

@dataclass 
class SquelchOpts:
    lower_thresh: float
    upper_thresh: float
    decode: DecodeCommon
    order: int = 4
    envelopes_order: int = 4
    bw_safety_margin: float = 2

@dataclass
class DecodeCommon:
    oversampling: int
    signal: SignalOpts

    @property
    def chunk_size(self) -> int:
        return self.signal.nsamp // self.oversampling

@dataclass
class DecodeStreamOpts:
    squelch_grace_percent: float
    idle_bits: float
    decode: DecodeCommon

    @property
    def squelch_grace_period(self) -> int:
        return round(self.squelch_grace_percent * self.decode.chunk_size)

    @property
    def idle_samples(self) -> int:
        return round(self.idle_bits * self.decode.chunk_size)

@dataclass
class SignalOpts:
    Fs: int
    rtty: RTTYOpts

    @property
    def nsamp(self):
        return round(self.Fs / self.rtty.baud)

    def mark_bin_index(self, n_fft: int) -> float:
        return self.rtty.mark * n_fft / self.Fs

    def space_bin_index(self, n_fft: int) -> float:
        return self.rtty.space * n_fft / self.Fs
