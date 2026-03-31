from dataclasses import dataclass
from typing import Final

@dataclass
class RTTYOpts:
    stop_bits: float = 1.5
    baud: float = 45.45
    mark: int = 2125
    shift: int = 170
    pre_msg_stops: int = 0
    post_msg_stops: int = 0

    data_bits: Final[int] = 5

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
class SystemOpts:
    Fs: int
    rtty: RTTYOpts

    @property
    def nsamp(self):
        return round(self.Fs / self.rtty.baud)

    def mark_bin_index(self, n_fft: int) -> float:
        return self.rtty.mark * n_fft / self.Fs

    def space_bin_index(self, n_fft: int) -> float:
        return self.rtty.space * n_fft / self.Fs
