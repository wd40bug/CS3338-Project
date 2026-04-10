import threading
from typing import Callable

from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.comms.topics import TopicsRegistry
from rtty_sdr.core.protocol import RecvMessage


class RecvThread(threading.Thread):
    def __init__(
        self,
        registry: TopicsRegistry,
        recv_callback: Callable[[RecvMessage], None],
        receiving_callback: Callable[[], None],
        sent_callback: Callable[[], None],
        shutdown_callback: Callable[[], None],
    ) -> None:
        super().__init__()
        self.__registry = registry
        self.__recv_callback = recv_callback
        self.__receiving_callback = receiving_callback
        self.__sent_callback = sent_callback

    def run(self):
        pubsub = PubSub(["dsp.received", "system.shutdown"], self.__registry)
        ...


class UIComms:
    def __init__(
        self, registry: TopicsRegistry, recv_callback: Callable[[RecvMessage], None]
    ) -> None: ...
