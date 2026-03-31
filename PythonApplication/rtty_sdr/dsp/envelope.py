from rtty_sdr.core.options import SignalOpts
from rtty_sdr.dsp.filters import LowPassFilter, SosFilter

import numpy as np
import numpy.typing as npt


class Envelope:
    def __init__(self, opts: SignalOpts, order: int) -> None:
        self.__filter: SosFilter = LowPassFilter(opts.Fs, opts.rtty.baud * 1.5, order)
        self.delay: float = SosFilter.group_delay([self.__filter], np.array([0]))[0]

    def envelope(self, chunk: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        return self.__filter.filter(chunk**2)
