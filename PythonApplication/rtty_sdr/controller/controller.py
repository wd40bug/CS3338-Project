import sys
import threading
import queue

from typing import Literal

from rtty_sdr.comms.messages import Send, Sent, Settings, Shutdown
from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.controller.espcom import (
    EspComSuccess,
    EspComms,
    ToESP,
)
from loguru import logger

from rtty_sdr.core.catch_and_broadcast import catch_and_broadcast
from rtty_sdr.core.options import SystemOpts

class ControllerModule(threading.Thread):
    """Thread to communicate with the ESP"""
    def __init__(self, initial_settings: SystemOpts):
        super().__init__()
        self.__settings = initial_settings
        self.__pubsub = PubSub(module_name="Controller")
        self.__pubsub.subscribe(Send, self.__on_send_message)
        self.__pubsub.subscribe(Settings, self.__on_settings)
        self.__pubsub.subscribe(Shutdown, self.__on_shutdown)
        self.__msgqueue: queue.Queue[ToESP | Literal["done"]] = queue.Queue()
        self.__comms = EspComms("/dev/ttyUSB0" if sys.platform == "linux" else "COM1")

    def __on_send_message(self, msg: Send):
        self.__msgqueue.put(ToESP(msg.msg.codes, self.__settings.rtty))

    def __on_settings(self, msg: Settings):
        self.__settings = msg.settings

    def __on_shutdown(self, _: Shutdown):
        self.__msgqueue.put("done")
        self.join()
        logger.info("Ending Controller thread")
        return "stop"

    @catch_and_broadcast
    def run(self):
        logger.info("Running Controller Process")
        self.__pubsub.run_receive()

        while True:
            msg = self.__msgqueue.get()
            if msg == "done":
                logger.trace("Esp Controller done")
                self.__msgqueue.task_done()
                return
            ret = self.__comms.send_receive(msg)
            assert isinstance(ret, EspComSuccess), (
                f"Failed to send message to ESP: {ret.detail}"
            )
            logger.debug("Successfully sent message to ESP")
            self.__pubsub.publish(Sent())
            self.__msgqueue.task_done()
