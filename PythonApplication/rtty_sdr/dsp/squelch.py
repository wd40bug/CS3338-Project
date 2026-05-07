from dataclasses import dataclass
from typing import Final, Self
import numpy as np
import numpy.typing as npt
import sys

from rtty_sdr.core.options import SquelchOpts
from rtty_sdr.debug.debug_types import DebugSliceable
from rtty_sdr.dsp.envelope import Envelope, EnvelopeDebug
from rtty_sdr.dsp.filters import PeakFilter


@dataclass
class SquelchDebug(DebugSliceable):
    signal_envelope: npt.NDArray[np.float64]
    total_envelope: npt.NDArray[np.float64]
    noise_envelope: npt.NDArray[np.float64]
    snrs: npt.NDArray[np.float64]
    signal_envelope_debug: EnvelopeDebug
    total_envelope_debug: EnvelopeDebug

    def __len__(self) -> int:
        return len(self.signal_envelope)

    def __getitem__(self, key: slice | int) -> Self:
        return self.__class__(
            self.signal_envelope[key],
            self.total_envelope[key],
            self.noise_envelope[key],
            self.snrs[key],
            self.signal_envelope_debug[key],
            self.total_envelope_debug[key],
        )

    @classmethod
    def default(cls) -> Self:
        return cls(
            np.array([]),
            np.array([]),
            np.array([]),
            np.array([]),
            EnvelopeDebug.default(),
            EnvelopeDebug.default()
        )

    @classmethod
    def combine(cls, debugs: list[Self]) -> Self:
        if not debugs:
            return cls.default()

        return cls(
            np.concatenate([o.signal_envelope for o in debugs]),
            np.concatenate([o.total_envelope for o in debugs]),
            np.concatenate([o.noise_envelope for o in debugs]),
            np.concatenate([o.snrs for o in debugs]),
            EnvelopeDebug.combine([d.signal_envelope_debug for d in debugs]),
            EnvelopeDebug.combine([d.total_envelope_debug for d in debugs]),
        )


class Squelch:
    def __init__(self, opts: SquelchOpts) -> None:
        signal = opts.decode.signal
        self.BW: Final[float] = opts.bw_safety_margin * (
            signal.rtty.shift + signal.rtty.baud
        )
        self.__filter = PeakFilter(
            signal.Fs, (signal.rtty.mark + signal.rtty.space) / 2, self.BW, 4
        )
        self.__signal_envelope = Envelope(signal, opts.envelopes_order, opts.envelope_margin)
        self.__full_envelope = Envelope(signal, opts.envelopes_order, opts.envelope_margin)
        self.__last_was_squelch = True
        self.lower_thresh: Final[float] = opts.lower_thresh
        self.upper_thresh: Final[float] = opts.upper_thresh
        self.delay: Final[float] = self.__filter.delay
        self.squelch_delay: Final[float] = self.delay + self.__signal_envelope.delay

    def process(
        self, audio_chunk: npt.NDArray[np.float64]
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.int_], SquelchDebug]:
        # Apply filter
        filtered = self.__filter.filter(audio_chunk)
        # Envelopes
        tot_env, tot_debug = self.__full_envelope.envelope(audio_chunk)
        sig_env, sig_debug = self.__signal_envelope.envelope(filtered)

        # Sample by sample noise and SNR
        noise_env = np.maximum(tot_env - sig_env, sys.float_info.epsilon)
        snrs = sig_env / noise_env

        # Squelch hysteresis
        force_squelch = snrs < self.lower_thresh
        force_unsquelch = snrs > self.upper_thresh

        state_defined = force_squelch | force_unsquelch

        squelch: npt.NDArray[np.int_]

        if np.any(state_defined):
            squelch = np.empty(len(snrs), dtype=np.int_)
            squelch[force_squelch] = 1
            squelch[force_unsquelch] = 0

            if not state_defined[0]:
                state_defined[0] = True
                squelch[0] = self.__last_was_squelch

            idx = np.arange(len(snrs))

            last_defined_idx = np.maximum.accumulate(np.where(state_defined, idx, 0))

            squelch = squelch[last_defined_idx]
        else:
            squelch = np.full(len(snrs), self.__last_was_squelch, dtype=np.int_)

        self.__last_was_squelch = squelch[-1]

        return (
            filtered,
            squelch,
            SquelchDebug(sig_env, tot_env, noise_env, snrs, sig_debug, tot_debug),
        )
