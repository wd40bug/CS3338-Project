from typing import Annotated, Protocol, Literal
import queue
from pydantic import BaseModel, ConfigDict, Field

from rtty_sdr.core.options import SystemOpts


class RestartCommand(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    command: Literal["restart"] = "restart"
    new_settings: SystemOpts


class FullStopCommand(BaseModel):
    command: Literal["stop"] = "stop"


type Command = Annotated[
    RestartCommand | FullStopCommand, Field(discriminator="command")
]


class Commands(Protocol):
    def check(self) -> None | Command: ...


class NoCommands(Commands):
    def check(self) -> None | Command:
        return None


type CommandsQueueQueue = queue.Queue[Command]


class CommandsQueue(Commands):
    def __init__(self, queue: CommandsQueueQueue):
        self.__queue = queue

    def check(self) -> None | Command:
        try:
            cmd = self.__queue.get_nowait()
            self.__queue.task_done()

            return cmd
        except queue.Empty:
            return None
