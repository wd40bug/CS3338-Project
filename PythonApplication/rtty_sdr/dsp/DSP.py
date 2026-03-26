from typing import Literal, Iterator
from dataclasses import dataclass
import numpy as np
import numpy.typing as npt

from rtty_sdr.dsp.sources import AudioSource
from rtty_sdr.dsp.engines import DemodulatorEngine
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.debug.annotations import DebugAnnotations


@dataclass(frozen=True)
class ReceivedDebug:
    code: int
    indices: npt.NDArray[np.int_]
    signal: npt.NDArray[np.float64]
    envelope: npt.NDArray[np.float64]
    squelch: npt.NDArray[np.float64]
    annotations: DebugAnnotations

class ReceivedCodeBuilder:
    def __init__(self) -> None:
        self.__global_frame: int = 0  # Absolute sample index of the entire SDR stream
        self.__word_start_global: int = 0  # Absolute index where the CURRENT word started

        # Accumulated slices for the current word
        self.__signal: list[npt.NDArray[np.float64]] = []
        self.__envelope: list[npt.NDArray[np.float64]] = []
        self.__squelch: list[npt.NDArray[np.float64]] = []

        self.__start_bit: int | None = None
        self.__data_bits: list[int] = []

        # Active chunk state
        self.__active_audio: npt.NDArray[np.float64] = np.array([])
        self.__active_env: npt.NDArray[np.float64] = np.array([])
        self.__active_sq: npt.NDArray[np.float64] = np.array([])
        self.__chunk_start_idx: int = 0  # Where in the active chunk the unrecorded data begins

    def load_chunk(
        self,
        signal: npt.NDArray[np.float64],
        envelope: npt.NDArray[np.float64],
        squelch: npt.NDArray[np.float64],
    ) -> None:
        """Called at the start of a new audio chunk to provide the builder with data."""
        self.__active_audio = signal
        self.__active_env = envelope
        self.__active_sq = squelch
        self.__chunk_start_idx = 0

    def start_bit(self, i: int) -> None:
        self.__start_bit = self.__global_frame + i

    def data_bit(self, i: int) -> None:
        self.__data_bits.append(self.__global_frame + i)

    def build(self, code: int, i: int) -> ReceivedDebug:
        """Called when a stop bit is found at local chunk index 'i'."""
        
        # 1. Record the slice up to the stop bit (inclusive)
        self.__signal.append(self.__active_audio[self.__chunk_start_idx : i + 1])
        self.__envelope.append(self.__active_env[self.__chunk_start_idx : i + 1])
        self.__squelch.append(self.__active_sq[self.__chunk_start_idx : i + 1])

        # 2. Build contiguous arrays
        signal_arr = np.concatenate(self.__signal) if self.__signal else np.array([])
        envelope_arr = np.concatenate(self.__envelope) if self.__envelope else np.array([])
        squelch_arr = np.concatenate(self.__squelch) if self.__squelch else np.array([])

        stop_bit_global = self.__global_frame + i
        word_end_global = stop_bit_global + 1

        start_bits = (
            np.array([self.__start_bit])
            if self.__start_bit is not None
            else np.array([])
        )

        ret = ReceivedDebug(
            code,
            np.arange(self.__word_start_global, word_end_global),
            signal_arr,
            envelope_arr,
            squelch_arr,
            DebugAnnotations(
                start_bits,
                np.array([stop_bit_global]),
                np.array(self.__data_bits, dtype=np.int_)
            ),
        )

        # 3. Update internal index so the rest of the chunk goes to the NEXT word
        self.__chunk_start_idx = i + 1
        self.__word_start_global = word_end_global

        # 4. Clear accumulators for the next word
        self.__signal.clear()
        self.__envelope.clear()
        self.__squelch.clear()
        self.__start_bit = None
        self.__data_bits.clear()

        return ret

    def commit_chunk(self) -> None:
        """Called at the end of the loop to save any remaining chunk data."""
        if self.__chunk_start_idx < len(self.__active_audio):
            self.__signal.append(self.__active_audio[self.__chunk_start_idx :])
            self.__envelope.append(self.__active_env[self.__chunk_start_idx :])
            self.__squelch.append(self.__active_sq[self.__chunk_start_idx :])

        # Advance the global frame counter by the entire chunk size
        self.__global_frame += len(self.__active_audio)

        # Drop references to free memory
        self.__active_audio = np.array([])
        self.__active_env = np.array([])
        self.__active_sq = np.array([])


def decode_stream(
    source: AudioSource, engine: DemodulatorEngine, opts: SystemOpts
) -> Iterator[ReceivedDebug]:
    countdown: None | int = None
    state: Literal["no_signal", "idle", "start", "data", "stop"] = "start"
    current_word: list[bool] = []

    builder = ReceivedCodeBuilder()

    while True:
        raw_audio = source.read_chunk()
        if raw_audio is None:
            return

        samples, squelch_arr = engine.process(raw_audio)
        
        # Give the chunk to the builder
        builder.load_chunk(raw_audio, samples, squelch_arr)

        for i, (sample, sq_val) in enumerate(zip(samples, squelch_arr)):
            # TODO: squelch logic with sq_val

            if countdown is not None and countdown > 0:
                countdown -= 1
                continue

            match state:
                case "no_signal" | "idle":
                    pass
                case "start":
                    if sample < 0:
                        builder.start_bit(i)
                        state = "data"
                        countdown = round(1.5 * opts.nsamp)
                        current_word.clear()
                case "data":
                    current_word.append(sample > 0)
                    builder.data_bit(i)
                    countdown = opts.nsamp
                    if len(current_word) == 5:
                        state = "stop"
                case "stop":
                    code = sum(
                        bit * (2**j) for j, bit in enumerate(reversed(current_word))
                    )
                    
                    yield builder.build(code, i)
                    
                    state = "start"
                    countdown = None

        # Loop finished, save remaining unbuilt data and advance the absolute clock
        builder.commit_chunk()
