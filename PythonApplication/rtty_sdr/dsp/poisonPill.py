from typing import Iterator, Protocol, Literal
import queue
import numpy as np
import numpy.typing as npt


class PoisonPill(Protocol):
    def check(self) -> None | Literal["stop"]:
        ...

class NonePoisonPill(PoisonPill):
    def check(self) -> None | Literal["stop"]:
        return None

type PillQueue = queue.Queue[Literal["stop"]]
class QueuePoisonPill(PoisonPill):
    def __init__(self, queue: PillQueue):
        self.__queue = queue

    def check(self) -> None | Literal["stop"]:
        try:
            cmd = self.__queue.get_nowait()
            self.__queue.task_done()
            
            if cmd == "stop":
                return "stop"
            else:
                raise ValueError(f"Unknown Command: {cmd}")
        except queue.Empty:
            return None
