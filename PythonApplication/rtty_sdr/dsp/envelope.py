from dataclasses import dataclass
from typing import Self
from rtty_sdr.core.options import SignalOpts
from rtty_sdr.debug.debug_types import DebugSliceable
from rtty_sdr.dsp.filters import LowPassFilter, SosFilter

import numpy as np
import numpy.typing as npt


@dataclass
class EnvelopeDebug(DebugSliceable):
    squared: npt.NDArray[np.float64]

    def __getitem__(self, key: slice | int) -> Self:
        return self.__class__(self.squared[key])

    def __len__(self) -> int:
        return len(self.squared)

    @classmethod
    def combine(cls, debugs: list[Self]) -> Self:
        return cls(np.concatenate([d.squared for d in debugs]))

    @classmethod
    def default(cls) -> Self:
        return cls(np.array([]))


class Envelope:
    def __init__(self, opts: SignalOpts, order: int, baud_safety_margin: float) -> None:
        self.__filter: SosFilter = LowPassFilter(opts.Fs, opts.rtty.baud * baud_safety_margin, order)
        self.delay: float = SosFilter.group_delay([self.__filter], np.array([0]))[0]

    def envelope(
        self, chunk: npt.NDArray[np.float64]
    ) -> tuple[npt.NDArray[np.float64], EnvelopeDebug]:
        squared = chunk**2
        return self.__filter.filter(squared), EnvelopeDebug(squared)
