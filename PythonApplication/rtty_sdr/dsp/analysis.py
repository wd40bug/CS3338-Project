from dataclasses import dataclass
import numpy as np
import numpy.typing as npt
from typing import Iterable

from rtty_sdr.debug.annotations import DebugAnnotations

@dataclass(frozen=True)
class DecodeDebug:
    indices: npt.NDArray[np.int_]
    signal: npt.NDArray[np.float64]
    envelope: npt.NDArray[np.float64]
    squelch: npt.NDArray[np.float64]
    annotations: DebugAnnotations

    @classmethod
    def concat(cls, debugs: Iterable[DecodeDebug]) -> DecodeDebug:
        debug_list = list(debugs)
        
        if not debug_list:
            # Return an empty instance if the iterable is empty
            return cls(
                np.array([]), np.array([]), np.array([]), np.array([]),
                DebugAnnotations(np.array([]), np.array([]), np.array([]))
            )

        # Merge the annotations
        base_anno = DebugAnnotations(np.array([]), np.array([]), np.array([]))
        for d in debug_list:
            base_anno.join(d.annotations)

        # Concat the arrays
        return cls(
            indices=np.concatenate([d.indices for d in debug_list]),
            signal=np.concatenate([d.signal for d in debug_list]),
            envelope=np.concatenate([d.envelope for d in debug_list]),
            squelch=np.concatenate([d.squelch for d in debug_list]),
            annotations=base_anno
        )


@dataclass
class StreamData:
    signal: npt.NDArray[np.float64]
    envelope: npt.NDArray[np.float64]
    squelch: npt.NDArray[np.float64]

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
        squelch: npt.NDArray[np.float64],
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
