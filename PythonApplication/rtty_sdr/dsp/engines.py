from typing import Protocol, Final
import numpy as np
import numpy.typing as npt

from rtty_sdr.dsp.filters import *
from rtty_sdr.core.options import SystemOpts

import fastgoertzel as fg


class DemodulatorEngine(Protocol):
    type EngineReturn = tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]

    def process(self, audio_chunk: npt.NDArray[np.float64]) -> EngineReturn: ...


class EnvelopeEngine(DemodulatorEngine):
    __overall: PeakFilter
    __mark: PeakFilter
    __space: PeakFilter
    __lpf_mark: LowPassFilter
    __lpf_space: LowPassFilter
    delay: Final[float]

    def __init__(self, opts: SystemOpts):
        BW_total = 2 * 170 + 2 * 45.45
        BW_one = 1.2 * 45.45
        self.__overall = PeakFilter(
            opts.Fs, (opts.rtty.mark + opts.rtty.space) / 2, BW_total, 4
        )
        self.__mark = PeakFilter(opts.Fs, opts.rtty.mark, BW_one, 4)
        self.__space = PeakFilter(opts.Fs, opts.rtty.space, BW_one, 4)
        self.__lpf_mark = LowPassFilter(opts.Fs, 70, 4)
        self.__lpf_space = LowPassFilter(opts.Fs, 70, 4)
        self.delay = (
            SosFilter.group_delay(
                [self.__overall, self.__mark], np.array([self.__mark.center])
            )[0]
            + SosFilter.group_delay(
                [self.__lpf_mark],
                np.array([1.0]),  # Evaluate at 1 Hz (close enough to DC)
            )[0]
        )

    def process(
        self, audio_chunk: npt.NDArray[np.float64]
    ) -> DemodulatorEngine.EngineReturn:
        # 1. Apply Mark/Space filters
        filtered = self.__overall.filter(audio_chunk)
        mark = self.__mark.filter(filtered)
        space = self.__space.filter(filtered)
        # 2. Square and Low-Pass
        mark_env = self.__lpf_mark.filter(mark**2)
        space_env = self.__lpf_space.filter(space**2)
        # TODO: 3. Calculate Squelch Hysteresis

        # 4. Compare Envelopes
        diff: npt.NDArray[np.float64] = mark_env - space_env
        # Return state_mask and squelch_mask
        return diff, np.ones(len(audio_chunk))


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
        signal_windowed = np.hamming(n) * signal
        signal_padded = np.concat((signal_windowed, np.zeros(N - n)))

        mag, _ = fg.goertzel(signal_padded, freq / Fs)  # type: ignore
        return mag

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
        diff = mark_power - space_power

        # Update overlap
        self.__overlap = frame[-self.overlap_size :]

        # TODO: Squelch
        return np.full(audio_chunk.shape, diff), np.ones(audio_chunk.shape)
