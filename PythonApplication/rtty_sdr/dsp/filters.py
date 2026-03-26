import scipy as sc
import numpy as np
import numpy.typing as npt
import numpy.typing as npt
from typing import Final
from abc import ABC, abstractmethod

class SosFilter(ABC):
    sos: Final[npt.NDArray[np.float64]]
    __zi: npt.NDArray[np.float64]
    order: Final[int]
    Fs: Final[float]

    def __init__(self, sos: npt.NDArray[np.float64], order: int, Fs: float) -> None:
        self.sos = sos
        self.__zi = np.zeros((sos.shape[0], 2), dtype=np.float64)
        self.Fs = Fs
        self.order = order

    def clear(self) -> None:
        self.__zi = np.zeros((self.sos.shape[0], 2), dtype=np.float64)

    def filter(self, chunk: npt.NDArray[np.float64]) -> np.typing.NDArray:
        y, self.__zi = sc.signal.sosfilt(self.sos, chunk, zi=self.__zi)
        return y

    def frequency_response(
        self, worN: None | int | np.typing.ArrayLike = None
    ) -> tuple[npt.NDArray[np.float64], np.typing.NDArray]:
        return sc.signal.freqz_sos(self.sos, worN=worN, fs=self.Fs)

    @abstractmethod
    def __str__(self) -> str:
        pass

    @staticmethod
    def group_delay(
        filters: list[SosFilter], freqs: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        delay = np.zeros(len(freqs))
        for filter in filters:
            _, GD = sc.signal.group_delay(
                sc.signal.sos2tf(filter.sos), w=freqs, fs=filter.Fs
            )
            delay += GD
        return delay



class PeakFilter(SosFilter):
    corners: Final[tuple[float, float]]
    center: Final[float]
    center_name: Final[str]

    def __init__(
        self, Fs: float, freq: float, BW: float, order: int, center_name: str = "Center"
    ):
        fc1 = freq - BW / 2
        fc2 = freq + BW / 2
        sos = sc.signal.butter(order, [fc1, fc2], fs=Fs, btype="bandpass", output="sos")
        super().__init__(sos, order, Fs)
        self.corners = (fc1, fc2)
        self.center = freq
        self.center_name = center_name

    def __str__(self) -> str:
        return f"Bandpass Filter (Order: {self.order}, Fcenter: {self.center} Hz, Width: {self.corners[1] - self.corners[0]:.1f} Hz)"


class LowPassFilter(SosFilter):
    Fcutoff: Final[float]

    def __init__(self, Fs: int, cutoff: float, order: int) -> None:
        sos = sc.signal.butter(order, cutoff, fs=Fs, btype="low", output="sos")
        super().__init__(sos, order, Fs)
        self.Fcutoff = cutoff

    def __str__(self) -> str:
        return f"Lowpass Filter (Order: {self.order}, Fcutoff: {self.Fcutoff})"
