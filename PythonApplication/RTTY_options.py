from dataclasses import dataclass
from typing import Final


@dataclass
class RTTYOpts:
    stop_bits: float = 1.5
    baud: float = 45.45
    mark: int = 2125
    shift: int = 170
    pre_msg_stops: int = 0

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

    def nsamp(self, Fs: int) -> int:
        return int(Fs / self.baud)

    # def samples_per_character(self, Fs: int) -> int:
    #     return int(self.nsamp(Fs) * self.bits_per_character)
    #
    # def samples_per_stop(self, Fs: int) -> int:
    #     return int(self.nsamp(Fs) * self.stop_bits)
    #
    # def samples_before_msg(self, Fs: int) -> int:
    #     return int(self.nsamp(Fs) * self.stop_bits)
    #
    # def samples_in_message_of_len(self, Fs: int, len: int) -> int:
    #     return self.samples_before_msg(Fs) + self.samples_per_character(Fs) * len
    #
    # def time_for_message_of_len(self, Fs: int, len: int) -> float:
    #     return self.seconds_per_bit * (
    #         self.pre_msg_stops * self.stop_bits + len * self.bits_per_character
    #     )

    def __str__(self) -> str:
        return f"Mark: {self.mark}, Space: {self.space}, Baud: {self.baud}"
