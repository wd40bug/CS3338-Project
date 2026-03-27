from dataclasses import dataclass
from typing import Final
import numpy as np
import numpy.typing as npt
import sys

from rtty_sdr.core.options import SystemOpts
from rtty_sdr.dsp.envelope import Envelope
from rtty_sdr.dsp.filters import PeakFilter

@dataclass
class SquelchDebug:
    signal_envelope: npt.NDArray[np.float64]
    total_envelope: npt.NDArray[np.float64]
    noise_envelope: npt.NDArray[np.float64]
    snrs: npt.NDArray[np.float64]

class Squelch:
    def __init__(
        self,
        opts: SystemOpts,
        lower_thresh: float,
        upper_thresh: float,
        bw_safety_margin: float = 2,
    ) -> None:
        self.BW: Final[float] = bw_safety_margin * (opts.rtty.shift + opts.rtty.baud)
        self.__filter = PeakFilter(
            opts.Fs, (opts.rtty.mark + opts.rtty.space) / 2, self.BW, 4
        )
        self.__signal_envelope = Envelope(opts)
        self.__full_envelope = Envelope(opts)
        self.__last_was_squelch = True
        self.lower_thresh: Final[float] = lower_thresh
        self.upper_thresh: Final[float] = upper_thresh
        self.delay: Final[float] = self.__filter.delay
        self.squelch_delay: Final[float] = self.delay + self.__signal_envelope.delay

    def process(
        self, audio_chunk: npt.NDArray[np.float64]
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.int_], SquelchDebug]:
        # Apply filter
        filtered = self.__filter.filter(audio_chunk)
        # Envelopes
        tot_env = self.__full_envelope.envelope(audio_chunk)
        sig_env = self.__signal_envelope.envelope(filtered)

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

        return filtered, squelch, SquelchDebug(sig_env, tot_env, noise_env, snrs)
