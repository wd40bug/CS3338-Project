from typing import Protocol, Final
import numpy as np
import numpy.typing as npt
import sounddevice as sd


class AudioSource(Protocol):
    def read_chunk(self) -> npt.NDArray[np.float64] | None: ...


class MockSignalSource:
    signal: Final[npt.NDArray[np.float64]]
    chunk_size: Final[int]
    __idx: int

    def __init__(self, full_signal: npt.NDArray[np.float64], chunk_size: int):
        self.signal = full_signal
        self.chunk_size = chunk_size
        self.__idx = 0

    def read_chunk(self) -> npt.NDArray[np.float64] | None:
        if self.__idx >= len(self.signal):
            return None

        chunk = self.signal[self.__idx : self.__idx + self.chunk_size]
        self.__idx += self.chunk_size
        return chunk


class MicrophoneSource:
    __sample_rate: Final[int]
    __chunk_size: Final[int]
    __stream: sd.InputStream

    def __init__(self, sample_rate: int, chunk_size: int):
        self.__sample_rate = sample_rate
        self.__chunk_size = chunk_size
        
        # Initialize the input stream
        self.__stream = sd.InputStream(
            samplerate=self.__sample_rate,
            channels=1,  # Mono
            blocksize=self.__chunk_size,
            dtype="float32"
        )
        self.__stream.start()

    def read_chunk(self) -> npt.NDArray[np.float64] | None:
        data, overflowed = self.__stream.read(self.__chunk_size)
        
        assert not overflowed
            
        return data.flatten()
            

    def __del__(self) -> None:
        self.__stream.stop()
        self.__stream.close()
