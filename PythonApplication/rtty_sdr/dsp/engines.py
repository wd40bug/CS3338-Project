from dataclasses import dataclass
from typing import ClassVar, Protocol, Final, Self, Type, TypeVar, Generic
import numpy as np
import numpy.typing as npt

from rtty_sdr.debug.debug_types import DebugSliceable
from rtty_sdr.dsp.envelope import Envelope, EnvelopeDebug
from rtty_sdr.dsp.filters import *
from rtty_sdr.core.options import GoertzelOpts, SignalOpts, EnvelopeOpts

import fastgoertzel as fg


@dataclass
class EnvelopeEngineDebug(DebugSliceable):
    mark_env: npt.NDArray[np.float64]
    space_env: npt.NDArray[np.float64]

    mark_filtered: npt.NDArray[np.float64]
    mark_env_debug: EnvelopeDebug

    space_filtered: npt.NDArray[np.float64]
    space_env_debug: EnvelopeDebug


    @classmethod
    def combine(cls, debugs: list[Self]) -> Self:
        if not debugs:
            return cls.default()
        return cls(
            np.concatenate([d.mark_env for d in debugs]),
            np.concatenate([d.space_env for d in debugs]),
            np.concatenate([d.mark_filtered for d in debugs]),
            EnvelopeDebug.combine([d.mark_env_debug for d in debugs]),
            np.concatenate([d.space_filtered for d in debugs]),
            EnvelopeDebug.combine([d.space_env_debug for d in debugs]),
        )

    @classmethod
    def default(cls) -> Self:
        return cls(
            np.array([]),
            np.array([]),
            np.array([]),
            EnvelopeDebug.default(),
            np.array([]),
            EnvelopeDebug.default(),
        )

    def __getitem__(self, key: slice | int) -> Self:
        return self.__class__(
            self.mark_env[key],
            self.space_env[key],
            self.mark_filtered[key],
            self.mark_env_debug[key],
            self.space_filtered[key],
            self.space_env_debug[key],
        )

    def __len__(self) -> int:
        return len(self.mark_env)


class EnvelopeEngine:
    def __init__(self, opts: EnvelopeOpts):
        BW_one = 1.2 * 45.45
        signal_opts = opts.decode.signal
        self.__mark = PeakFilter(
            signal_opts.Fs, signal_opts.rtty.mark, BW_one, opts.order
        )
        self.__space = PeakFilter(
            signal_opts.Fs, signal_opts.rtty.space, BW_one, opts.order
        )
        self.__mark_env = Envelope(signal_opts, opts.envelopes_order, opts.envelopes_margin)
        self.__space_env = Envelope(signal_opts, opts.envelopes_order, opts.envelopes_margin)
        self.delay: Final[float] = self.__mark.delay + self.__mark_env.delay

    def process(
        self, audio_chunk: npt.NDArray[np.float64]
    ) -> tuple[npt.NDArray[np.float64], EnvelopeEngineDebug]:
        # Apply Mark/Space filters
        mark = self.__mark.filter(audio_chunk)
        space = self.__space.filter(audio_chunk)
        # Square and Low-Pass
        mark_env, mark_debug = self.__mark_env.envelope(mark)
        space_env, space_debug = self.__space_env.envelope(space)
        # Compare Envelopes
        diff: npt.NDArray[np.float64] = mark_env - space_env
        return diff, EnvelopeEngineDebug(
            mark_env, space_env, mark, mark_debug, space, space_debug
        )

    debug_t: ClassVar = EnvelopeEngineDebug

@dataclass
class GoertzelDebug(DebugSliceable):
    mark_power: npt.NDArray[np.float64]
    space_power: npt.NDArray[np.float64]

    @classmethod
    def combine(cls, debugs: list[Self]) -> Self:
        if not debugs:
            return cls.default()
        return cls(
            np.concatenate([d.mark_power for d in debugs]),
            np.concatenate([d.space_power for d in debugs]),
        )

    @classmethod
    def default(cls) -> Self:
        return cls(
            np.array([]),
            np.array([])
        )

    def __getitem__(self, key: slice | int) -> Self:
        return self.__class__(self.mark_power[key], self.space_power[key])

    def __len__(self) -> int:
        return super().__len__()



class GoertzelEngine:
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
    ) -> tuple[npt.NDArray[np.float64], tuple[float, float]]:
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

        return np.full(audio_chunk.shape, mark_power - space_power), (
            mark_power,
            space_power,
        )

    def process(
        self, audio_chunk: npt.NDArray[np.float64]
    ) -> tuple[npt.NDArray, GoertzelDebug]:
        ret = []
        mark_powers = []
        space_powers = []
        indices = np.arange(
            self.__opts.decode.chunk_size,
            len(audio_chunk),
            self.__opts.decode.chunk_size,
        )
        for chunk in np.array_split(audio_chunk, indices):
            detected, (mark_pow, space_pow) = self.__process(chunk)
            ret.append(detected)
            mark_powers.append(np.full(len(chunk), mark_pow))
            space_powers.append(np.full(len(chunk), space_pow))

        return (
            np.concatenate(ret),
            GoertzelDebug(np.concatenate(mark_powers), np.concatenate(space_powers)),
        )

    debug_t: ClassVar = GoertzelDebug

type DemodulatorEngine = EnvelopeEngine | GoertzelEngine
