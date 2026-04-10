import threading

from loguru import logger
import zmq

from rtty_sdr.comms.broker import DEBUG_SOCKET
from rtty_sdr.comms.messages import AnyMessage, DebugMessage, Shutdown
from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.dsp.protocol_decode import ProtocolDebug


class DebugSocket(threading.Thread):
    def __init__(self):
        super().__init__()
        self.__debugs: list[ProtocolDebug] = []
        self.__pubsub = PubSub(sub_addr=DEBUG_SOCKET, module_name="Debug Socket")
        self.__pubsub.subscribe_all(self.__on_msg)
        self.__pubsub.subscribe(Shutdown, self.__on_shutdown)
        self.__pubsub.subscribe(DebugMessage, self.__on_debug)

    def __on_msg(self, msg: AnyMessage):
        logger.debug(f"msg sent {msg.topic}")

    def __on_shutdown(self, _: Shutdown):
        logger.debug("Shutting down debug socket")
        return "stop"

    def __on_debug(self, msg: DebugMessage):
        self.__debugs.append(msg.debug)

    def run(self):
        self.__pubsub.run_receive(thread=False)

    def collect(self) -> ProtocolDebug:
        return ProtocolDebug.combine(self.__debugs)
