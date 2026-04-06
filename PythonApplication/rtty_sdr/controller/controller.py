import json
from typing import Literal
from queue import Queue

from loguru import logger
from rtty_sdr.core.options import RTTYOpts
from rtty_sdr.core.protocol import ProtocolMessage
from rtty_sdr.controller.serialcom import send_serial, read_serial

class ToESP:
    options: RTTYOpts
    message: list[int]

    def __init__(self, opts: RTTYOpts, msg: ProtocolMessage):
        self.options = opts
        self.message = msg.codes


def createJSON(info: ToESP):
    data = {
        "stop_bits": info.options.stop_bits,
        "baud": info.options.baud,
        "mark": info.options.mark,
        "shift": info.options.shift,
        "pre_msg_stops": info.options.pre_msg_stops,
        "message": info.message
    }

    jsonstr = json.dumps(data)
    return jsonstr

def send_receive(msgqueue: Queue[ToESP | Literal["done"]]):
    while True:
        msg = msgqueue.get()

        if(msg == "done"):
            msgqueue.task_done()
            return
        
        send_serial(createJSON(msg))
        logger.debug(read_serial())
        msgqueue.task_done()




