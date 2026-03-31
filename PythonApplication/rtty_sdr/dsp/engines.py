from typing import Protocol, Final, TypeVar, Generic
import numpy as np
import numpy.typing as npt

from rtty_sdr.debug.debug_types import DebugCombineable
from rtty_sdr.dsp.envelope import Envelope
from rtty_sdr.dsp.filters import *
from rtty_sdr.core.options import GoertzelOpts, SignalOpts, EnvelopeOpts

import fastgoertzel as fg


T_DebugInfo = TypeVar("T_DebugInfo", bound=DebugCombineable, covariant=True)


class DemodulatorEngine(Protocol, Generic[T_DebugInfo]):
    def process(
        self, audio_chunk: npt.NDArray[np.float64]
    ) -> tuple[npt.NDArray[np.float64], T_DebugInfo]: ...


class EnvelopeEngine(DemodulatorEngine):
    def __init__(self, opts: EnvelopeOpts):
        BW_one = 1.2 * 45.45
        signal_opts = opts.decode.signal
        self.__mark = PeakFilter(signal_opts.Fs, signal_opts.rtty.mark, BW_one, 4)
        self.__space = PeakFilter(signal_opts.Fs, signal_opts.rtty.space, BW_one, 4)
        self.__mark_env = Envelope(signal_opts, opts.envelopes_order)
        self.__space_env = Envelope(signal_opts, opts.envelopes_order)
        self.delay: Final[float] = self.__mark.delay + self.__mark_env.delay

    def process(
        self, audio_chunk: npt.NDArray[np.float64]
    ) -> tuple[npt.NDArray[np.float64], None]:
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
    opts: Final[SignalOpts]
    overlap_size: Final[int]
    dft_block_size: Final[int]
    __overlap: npt.NDArray[np.float64]

    def __init__(
        self,
        opts: GoertzelOpts
    ):
        self.opts = opts.decode.signal
        self.overlap_size =  opts.overlap_size
        self.dft_block_size = opts.dft_len
        self.__overlap = np.zeros(self.overlap_size)

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
        return float((amplitude**2) / 2.0)

    def process(
        self, audio_chunk: npt.NDArray[np.float64]
    ) -> tuple[npt.NDArray[np.float64], None]:
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
