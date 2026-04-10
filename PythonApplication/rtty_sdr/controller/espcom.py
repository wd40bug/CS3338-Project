import msgspec
import serial
import time
from typing import Annotated, Literal

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
    """Class wrapping a serial.Serial port and our communication strategy"""
    def __init__(self) -> None:
        #TODO: Option for port
        self.__encoder = msgspec.json.Encoder()
        self.__esp: serial.Serial = serial.Serial(port="/dev/ttyUSB0", baudrate=115200)
        time.sleep(0.05)
        self.__esp.reset_input_buffer()
        time.sleep(0.2)

    def send_receive(self, msg: ToESP) -> EspComReturn:
        # Write msg to esp
        json = self.__encoder.encode(msg)
        self.__esp.write(json)
        logger.trace(f"Wrote to esp: {json}")
        # Read reply from esp
        reply = self.__esp.readline()
        logger.trace(reply)
        # TODO: Verify reply is sound
        return EspComSuccess()
