from typing import Literal, Iterator, Iterable

import numpy as np
import numpy.typing as npt
from dataclasses import dataclass
from rtty_sdr.dsp.sources import AudioSource
from rtty_sdr.dsp.engines import DemodulatorEngine
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.dsp.squelch import Squelch
from rtty_sdr.debug.annotations import DebugAnnotations
from rtty_sdr.debug.debug_types import DebugCombineable

type DecodeYield = Literal["reset"] | tuple[int, DecodeDebug]

def decode_stream(
    source: AudioSource, squelch: Squelch, engine: DemodulatorEngine, opts: SystemOpts
) -> Iterator[DecodeYield]:
    countdown: None | int = None
    state: Literal["no_signal", "idle", "start", "data", "stop"] = "start"
    current_word: list[bool] = []

    builder = DecodeDebugBuilder()

    while True:
        raw_audio = source.read_chunk()
        if raw_audio is None:
            return

        filtered_audio, squelch_arr, _ = squelch.process(raw_audio)

        samples, _ = engine.process(filtered_audio)
        
        # Give the chunk to the builder
        builder.load_frame(raw_audio, samples, squelch_arr)

        for i, (sample, _) in enumerate(zip(samples, squelch_arr)):
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
                    
                    yield (code, builder.build(i))
                    
                    state = "start"
                    countdown = None

        # Loop finished, save remaining unbuilt data and advance the absolute clock
        builder.commit_frame()


@dataclass(frozen=True)
class DecodeDebug(DebugCombineable):
    indices: npt.NDArray[np.int_]
    signal: npt.NDArray[np.float64]
    envelope: npt.NDArray[np.float64]
    squelch: npt.NDArray[np.int_]
    annotations: DebugAnnotations

    @classmethod
    def combine(cls, debugs: Iterable[DecodeDebug]) -> DecodeDebug:
        debug_list = list(debugs)
        
        if not debug_list:
            # Return an empty instance if the iterable is empty
            return cls(
                np.array([]), np.array([]), np.array([]), np.array([]),
                DebugAnnotations(np.array([]), np.array([]), np.array([]))
            )

        # Concat the arrays
        return cls(
            indices=np.concatenate([d.indices for d in debug_list]),
            signal=np.concatenate([d.signal for d in debug_list]),
            envelope=np.concatenate([d.envelope for d in debug_list]),
            squelch=np.concatenate([d.squelch for d in debug_list]),
            annotations=DebugAnnotations.combine([d.annotations for d in debug_list])
        )


@dataclass
class StreamData:
    signal: npt.NDArray[np.float64]
    envelope: npt.NDArray[np.float64]
    squelch: npt.NDArray[np.int_]

    def __len__(self) -> int:
        return len(self.signal)

    def __getitem__(self, key: slice | int) -> StreamData:
        return StreamData(
            self.signal[key],
            self.envelope[key],
            self.squelch[key]
        )

class DecodeDebugBuilder:
    def __init__(self) -> None:
        self.__start_index: int = 0
        self.__accumulated_data: list[StreamData] = []
        self.__start_bit: int | None = None
        self.__data_bits: list[int] = []

        # Current frame state
        self.__frame_index: int = 0  
        self.__frame_consumed: int = 0 
        self.__frame_data: StreamData | None = None

    def load_frame(
        self,
        signal: npt.NDArray[np.float64],
        envelope: npt.NDArray[np.float64],
        squelch: npt.NDArray[np.int_],
    ) -> None:
        assert self.__frame_data is None, "Previous frame was not committed!"
        self.__frame_consumed = 0
        self.__frame_data = StreamData(signal, envelope, squelch)

    def start_bit(self, i: int) -> None:
        self.__start_bit = self.__frame_index + i

    def data_bit(self, i: int) -> None:
        self.__data_bits.append(i + self.__frame_index)

    def commit_frame(self) -> None:
        if self.__frame_data:
            if self.__frame_consumed < len(self.__frame_data):
                self.__accumulated_data.append(self.__frame_data[self.__frame_consumed:])

            self.__frame_index += len(self.__frame_data)
            self.__frame_data = None  # Clear for the assert in load_frame

    def build(self, i: int) -> DecodeDebug:
        if self.__frame_data:
            self.__accumulated_data.append(self.__frame_data[self.__frame_consumed : i + 1])

        start_bits = (
            np.array([self.__start_bit])
            if self.__start_bit is not None
            else np.array([])
        )

        signal_arr = np.concatenate([d.signal for d in self.__accumulated_data]) if self.__accumulated_data else np.array([])
        envelope_arr = np.concatenate([d.envelope for d in self.__accumulated_data]) if self.__accumulated_data else np.array([])
        squelch_arr = np.concatenate([d.squelch for d in self.__accumulated_data]) if self.__accumulated_data else np.array([])

        ret = DecodeDebug(
            np.arange(self.__start_index, self.__frame_index + i + 1),
            signal_arr,
            envelope_arr,
            squelch_arr,
            DebugAnnotations(
                start_bits,
                np.array([i + self.__frame_index]),
                np.array(self.__data_bits),
            ),
        )
        
        self.__start_index = i + self.__frame_index + 1
        self.__accumulated_data.clear()
        self.__start_bit = None
        self.__data_bits.clear()
        self.__frame_consumed = i + 1

        return ret
