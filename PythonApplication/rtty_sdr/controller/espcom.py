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


type EspComReturn = Annotated[EspComError | EspComSuccess, Field(discriminator="kind")]


class ToESP(msgspec.Struct, frozen=True):
    message: list[int]
    options: RTTYOpts


class EspComms:
    """Class wrapping a serial.Serial port and our communication strategy"""

    def __init__(self, port: str) -> None:
        self.__encoder = msgspec.json.Encoder()
        self.__esp: serial.Serial = serial.Serial(port=port, baudrate=115200, timeout=5)
        time.sleep(0.05)
        self.__esp.reset_input_buffer()
        time.sleep(0.2)

    def send_receive(self, msg: ToESP) -> EspComReturn:
        # Write msg to esp
        json = self.__encoder.encode(msg)
        self.__esp.write(json)
        logger.trace(f"Wrote to esp: {json}")
        # Read reply from esp
        self.__esp.timeout = 2
        # self.__esp.reset_input_buffer()
        reply = self.__esp.readline().strip(b"\x00\x80")
        if not reply.endswith(b"\n"):
            return EspComError(detail="Timed out while awaiting initial reply")
        if not reply == b"REPLY: Message Received\r\n":
            return EspComError(
                detail=f"Unexpexted return while awaiting initial reply: {reply}"
            )
        self.__esp.timeout = (
            msg.options.bits_per_character
            * (
                len(msg.message)
                + msg.options.pre_msg_stops
                + msg.options.post_msg_stops
            )
        ) / msg.options.baud + 10
        while True:
            reply = b""
            reply = self.__esp.readline().strip(b"\x00\x80")
            if not reply.endswith(b"\n"):
                return EspComError(detail="Timed out while awaiting DEBUG or DONE")
            topic = reply.partition(b':')[0]
            if topic==b"DEBUG":
                logger.debug(f"From ESP: {reply}")
            elif topic==b"TRACE":
                logger.trace(f"From ESP: {reply}")
            elif topic==b"DONE":
                break
            else:
                return EspComError(detail=f"Unexpeced msg from ESP: {reply}")
        return EspComSuccess()
