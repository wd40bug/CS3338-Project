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
        self.__mark = PeakFilter(
            signal_opts.Fs, signal_opts.rtty.mark, BW_one, opts.order
        )
        self.__space = PeakFilter(
            signal_opts.Fs, signal_opts.rtty.space, BW_one, opts.order
        )
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
    __opts: Final[GoertzelOpts]
    __overlap: npt.NDArray[np.float64]

    def __init__(self, opts: GoertzelOpts):
        self.__opts = opts
        self.__overlap = np.zeros(opts.overlap_size)

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

    def __process(
        self, audio_chunk: npt.NDArray[np.float64]
    ) -> tuple[npt.NDArray[np.float64], None]:
        frame = np.concat((self.__overlap, audio_chunk))

        mark_power = GoertzelEngine.goertzel(
            frame,
            self.__opts.decode.signal.Fs,
            self.__opts.decode.signal.rtty.mark,
            self.__opts.dft_len,
        )
        space_power = GoertzelEngine.goertzel(
            frame,
            self.__opts.decode.signal.Fs,
            self.__opts.decode.signal.rtty.space,
            self.__opts.dft_len,
        )

        # Update overlap
        self.__overlap = frame[-self.__opts.overlap_size :]

        return np.full(audio_chunk.shape, mark_power - space_power), None

    def process(self, audio_chunk: npt.NDArray[np.float64]) -> tuple[npt.NDArray, None]:
        ret = []
        indices = np.arange(
            self.__opts.decode.chunk_size,
            len(audio_chunk),
            self.__opts.decode.chunk_size,
        )
        for chunk in np.array_split(audio_chunk, indices):
            ret.append(self.__process(chunk)[0])
        return (np.concatenate(ret), None)
