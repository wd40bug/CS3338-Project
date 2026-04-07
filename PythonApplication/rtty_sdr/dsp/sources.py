from typing import Protocol, Final
from loguru import logger
import numpy as np
import numpy.typing as npt
import sounddevice as sd
import queue

from rtty_sdr.core.options import DecodeCommon
from rtty_sdr.dsp.poisonPill import CommandsQueueQueue, FullStopCommand

class AudioSource(Protocol):
    def read_chunk(self) -> npt.NDArray[np.float64] | None: ...


class MockSignalSource:
    def __init__(
        self,
        initial: npt.NDArray[np.float64],
        opts: DecodeCommon,
        queue: queue.Queue[npt.NDArray[np.float64]] | None = None,
        pill_queue: CommandsQueueQueue | None = None
    ):
        self.__buffer: npt.NDArray[np.float64] = initial
        self.chunk_size: Final[int] = opts.chunk_size
        self.__queue: Final[queue.Queue[npt.NDArray[np.float64]] | None] = queue
        self.__pill_queue = pill_queue

    def read_chunk(self) -> npt.NDArray[np.float64] | None:
        if self.__queue is not None:
            new_data: list[npt.NDArray[np.float64]] = []
            while True:
                try:
                    chunk = self.__queue.get_nowait()
                    new_data.append(chunk)
                    self.__queue.task_done()
                    logger.trace(f"Received {len(new_data)} samples")
                except queue.Empty:
                    break
            
            if new_data:
                self.__buffer = np.concatenate([self.__buffer] + new_data)

        if len(self.__buffer) == 0:
            if self.__pill_queue is not None:
                self.__pill_queue.put(FullStopCommand())
            return None

        chunk_size = min(len(self.__buffer), self.chunk_size)
        chunk = self.__buffer[:chunk_size]
        self.__buffer = self.__buffer[chunk_size:]

        return chunk


class MicrophoneSource:
    __sample_rate: Final[int]
    __chunk_size: Final[int]
    __stream: sd.InputStream

    def __init__(self, opts: DecodeCommon):
        self.__sample_rate = opts.signal.Fs
        self.__chunk_size = opts.chunk_size

        # Initialize the input stream
        self.__stream = sd.InputStream(
            samplerate=self.__sample_rate,
            channels=1,  # Mono
            blocksize=self.__chunk_size,
            dtype="float32",
        )
        self.__stream.start()

    def read_chunk(self) -> npt.NDArray[np.float64] | None:
        data, overflowed = self.__stream.read(self.__chunk_size)

        assert not overflowed

        return data.flatten()

    def __del__(self) -> None:
        self.__stream.stop()
        self.__stream.close()
