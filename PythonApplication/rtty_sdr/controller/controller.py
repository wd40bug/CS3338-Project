import threading
import queue

from typing import Literal

from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.comms.topics import TopicsRegistry
from rtty_sdr.controller.espcom import (
    EspComSuccess,
    EspComms,
    ToESP,
)
from loguru import logger

from rtty_sdr.core.catch_and_broadcast import catch_and_broadcast
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.core.protocol import SendMessage

class EspComThread(threading.Thread):
    """Thread to communicate with the ESP and publish controller.sent messages"""
    def __init__(
        self,
        msgqueue: queue.Queue[ToESP | Literal["done"]],
        registry: TopicsRegistry,
    ):
        super().__init__()
        self.__msgqueue = msgqueue
        self.__comms = EspComms()
        self.__pubsub = PubSub([], registry)

    def broadcast_shutdown(self):
        self.__pubsub.publish_message('system.shutdown', None)

    @catch_and_broadcast
    def run(self):
        while True:
            msg = self.__msgqueue.get()
            if msg == "done":
                logger.trace("Esp Communication done")
                self.__msgqueue.task_done()
                return
            ret = self.__comms.send_receive(msg)
            assert isinstance(ret, EspComSuccess), f"Failed to send message to ESP: {ret.detail}"
            logger.debug("Successfully sent message to ESP")
            self.__pubsub.publish_message("controller.sent", None)
            self.__msgqueue.task_done()
                


class ControllerModule(threading.Thread):
    """Thread to recieve messages from the messagequeue to manage the EspComThread"""
    def __init__(self, initial_settings: SystemOpts, registry: TopicsRegistry):
        super().__init__()
        registry.register("controller.sent", None)
        self.__registry = registry
        self.__settings = initial_settings
        
    @catch_and_broadcast
    def run(self):
        logger.info("Running Controller Process")
        pubsub = PubSub(["ui.send_message", "system.shutdown", "ui.settings"], self.__registry)

        msgqueue: queue.Queue[ToESP | Literal["done"]] = queue.Queue()
        esp_comm = EspComThread(msgqueue, self.__registry)
        esp_comm.start()

        while True:
            topic, payload = pubsub.recv_message()
            logger.trace(f"Received {topic} msg")
            if topic == "ui.settings":
                assert isinstance(payload, SystemOpts)
                self.__settings = payload
            elif topic == "system.shutdown":
                assert payload is None
                msgqueue.put("done")
                esp_comm.join()
                logger.info("Ending Controller thread")
                return
            elif topic == "ui.send":
                assert isinstance(payload, SendMessage)
                msgqueue.put(ToESP(payload.codes, self.__settings.rtty))

