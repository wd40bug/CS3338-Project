from typing import Protocol, Final
import numpy as np
import numpy.typing as npt


class AudioSource(Protocol):
    def read_chunk(self) -> npt.NDArray[np.float64]: ...


class MockSignalSource:
    signal: Final[npt.NDArray[np.float64]]
    chunk_size: Final[int]
    __idx: int

    def __init__(self, full_signal: npt.NDArray[np.float64], chunk_size: int):
        self.signal = full_signal
        self.chunk_size = chunk_size
        self.__idx = 0

    def read_chunk(self) -> npt.NDArray[np.float64]:
        if self.__idx >= len(self.signal):
            raise StopIteration

        chunk = self.signal[self.__idx : self.__idx + self.chunk_size]
        self.__idx += self.chunk_size
        return chunk


class MicrophoneSource:
    def __init__(self, sample_rate: int, chunk_size: int = 1024):
        # Setup PyAudio or SoundDevice stream here
        ...

    def read_chunk(self) -> npt.NDArray[np.float64]:
        # Read from the hardware buffer and return the numpy array
        # This will naturally block until audio is available, keeping your pipeline perfectly paced
        ...
