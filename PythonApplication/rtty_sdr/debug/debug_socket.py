import threading

from loguru import logger
import zmq

from rtty_sdr.comms.broker import DEBUG_SOCKET
from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.comms.topics import TopicsRegistry
from rtty_sdr.dsp.protocol_decode import ProtocolDebug


class DebugSocket(threading.Thread):
    def __init__(self, registry: TopicsRegistry):
        super().__init__()
        self.__debugs: list[ProtocolDebug] = []
        self.__registry = registry

    def run(self):
        pubsub = PubSub(None, self.__registry, sub_addr=DEBUG_SOCKET)
        # context = zmq.Context()
        # socket = context.socket(zmq.SUB)
        # socket.setsockopt_string(zmq.SUBSCRIBE, "")
        # socket.connect(DEBUG_SOCKET)

        while True:
            topic, payload = pubsub.recv_message()
            logger.debug(f"msg sent {topic}")
            if topic == "dsp.debug":
                assert isinstance(payload, ProtocolDebug)
                self.__debugs.append(payload)
            elif topic == "system.shutdown":
                logger.debug("Shutting down debug socket")
                return

    def collect(self) -> ProtocolDebug:
        return ProtocolDebug.combine(self.__debugs)
