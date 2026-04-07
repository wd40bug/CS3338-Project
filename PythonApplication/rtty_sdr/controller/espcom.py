import queue
import msgspec
import serial
import time
import json
from typing import Annotated, Literal
from queue import Queue

from loguru import logger
from rtty_sdr.core.options import RTTYOpts
from pydantic import BaseModel, Field

class EspComError(BaseModel):
    kind: Literal["error"] = "error"
    detail: str

class EspComSuccess:
    kind: Literal["success"] = "success"
    pass

type EspComReturn = Annotated[EspComError | EspComSuccess, Field(discriminator="kind")]

class ToESP(msgspec.Struct, frozen=True):
    message: list[int]
    options: RTTYOpts

class EspComms:
    def __init__(self) -> None:
        self.__encoder = msgspec.json.Encoder()
        self.__esp: serial.Serial = serial.Serial(port="/dev/ttyUSB0", baudrate=115200)
        time.sleep(0.05)
        self.__esp.reset_input_buffer()
        time.sleep(0.2)

    def send_receive(self, msg: ToESP) -> EspComReturn:
        # Write msg to esp
        self.__esp.write(self.__encoder.encode(msg))
        # Read reply from esp
        reply = self.__esp.readline()
        logger.trace(reply)
        # TODO: Verify reply is sound
        return EspComSuccess()
