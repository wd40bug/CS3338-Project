from dataclasses import dataclass
import sys
from typing import Protocol, Final, Type, TypeVar, Generic
import numpy as np
import numpy.typing as npt

from rtty_sdr.dsp.envelope import Envelope
from rtty_sdr.dsp.filters import *
from rtty_sdr.core.options import SystemOpts

import fastgoertzel as fg


T_DebugInfo = TypeVar("T_DebugInfo")


class DemodulatorEngine(Protocol, Generic[T_DebugInfo]):
    type EngineReturn = tuple[
        npt.NDArray[np.float64], T_DebugInfo
    ]

    def process(self, audio_chunk: npt.NDArray[np.float64]) -> EngineReturn: ...


class EnvelopeEngine(DemodulatorEngine):
    class DebugInfo:
        bigger_envelope: npt.NDArray[np.float64]

    def __init__(self, opts: SystemOpts):
        BW_one = 1.2 * 45.45
        self.__mark = PeakFilter(opts.Fs, opts.rtty.mark, BW_one, 4)
        self.__space = PeakFilter(opts.Fs, opts.rtty.space, BW_one, 4)
        self.__mark_env = Envelope(opts)
        self.__space_env = Envelope(opts)
        self.delay: Final[float] = self.__mark.delay + self.__mark_env.delay

    def process(
        self, audio_chunk: npt.NDArray[np.float64]
    ) -> DemodulatorEngine.EngineReturn:
        # Apply Mark/Space filters
        mark = self.__mark.filter(audio_chunk)
        space = self.__space.filter(audio_chunk)
        # Square and Low-Pass
        mark_env = self.__mark_env.envelope(mark)
        space_env = self.__space_env.envelope(space)
        # Compare Envelopes
        diff: npt.NDArray[np.float64] = mark_env - space_env
        return diff, None


class GoertzelEngine(DemodulatorEngine):
    opts: Final[SystemOpts]
    overlap_size: Final[int]
    dft_block_size: Final[int]
    __overlap: npt.NDArray[np.float64]

    def __init__(
        self,
        overlap_size: int,
        dft_block_size: int,
        opts: SystemOpts,
    ):
        self.opts = opts
        self.overlap_size = overlap_size
        self.dft_block_size = dft_block_size
        self.__overlap = np.zeros(overlap_size)

    @staticmethod
    def goertzel(
        signal: np.typing.NDArray[np.float64], Fs: int, freq: float, N: int
    ) -> float:
        n = len(signal)
        N = max(n, N)
        window = np.hamming(n)
        signal_windowed = window * signal
        signal_padded = np.concat((signal_windowed, np.zeros(N - n)))

        mag, _ = fg.goertzel(signal_padded, freq / Fs)  # type: ignore

        # 1. Undo the window's coherent gain to recover the true real-world amplitude
        coherent_gain = np.sum(window)
        amplitude = 2.0 * mag / coherent_gain
        
        # 2. Return the RMS Power of the tone (A^2 / 2)
        return float((amplitude ** 2) / 2.0)

    def process(
        self, audio_chunk: npt.NDArray[np.float64]
    ) -> DemodulatorEngine.EngineReturn:
        frame = np.concat((self.__overlap, audio_chunk))

        mark_power = GoertzelEngine.goertzel(
            frame, self.opts.Fs, self.opts.rtty.mark, self.dft_block_size
        )
        space_power = GoertzelEngine.goertzel(
            frame, self.opts.Fs, self.opts.rtty.space, self.dft_block_size
        )

        # Update overlap
        self.__overlap = frame[-self.overlap_size :]

        return np.full(audio_chunk.shape, mark_power - space_power), None
