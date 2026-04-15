import inspect
import threading
import time
from typing import (
    Final,
    Callable,
    TypeAlias,
    TypeVar,
    get_origin,
    Any,
    cast,
    Self,
    Optional,
    Literal,
)
from loguru import logger
import numpy as np

import msgspec
import zmq
from rtty_sdr.comms.broker import BROKER_BACKEND, BROKER_FRONTEND
from rtty_sdr.comms.messages import AnyMessage, Shutdown, topics_map

T = TypeVar("T", bound=AnyMessage)

type CallbackAny = Callable[[AnyMessage], Optional[Literal["stop"]]]
type CallbackSpecific[T] = Callable[[T], Optional[Literal["stop"]]]


class PubSub:
    @staticmethod
    def decode_hook(type: Any, obj: Any) -> Any:
        origin = get_origin(type) or type

        if origin is np.ndarray:
            return np.array(obj)

    @staticmethod
    def encode_hook(obj: Any) -> Any:
        if isinstance(obj, np.ndarray):
            # Convert array to a list for JSON compatibility
            return obj.tolist()
        raise TypeError(f"Objects of type {type(obj).__name__} are unsupported")

    def __init__(
        self,
        pub_addr: str = BROKER_FRONTEND,
        sub_addr: str = BROKER_BACKEND,
        module_name: str = "Unknown",
    ) -> None:
        self.__callbacks: Final[dict[type[AnyMessage], list[CallbackAny]]] = {}
        self.__encoder: Final[msgspec.msgpack.Encoder] = msgspec.msgpack.Encoder(
            enc_hook=self.encode_hook
        )
        self.__context = zmq.Context()
        self.__pub_socket: zmq.Socket = self.__context.socket(zmq.PUB)
        self.__pub_socket.connect(pub_addr)
        self.__pub_socket.setsockopt(zmq.LINGER, 1000)

        self.__sub_addr = sub_addr

        self.__module = module_name

        self.__timeout_ms = None
        self.__on_timeout: Callable[[], Optional[Literal["stop"]]] = lambda: None
        time.sleep(0.2)

    def set_timeout(
        self,
        timeout_ms: int | None,
        callback: Callable[[], Optional[Literal["stop"]]] | None = None,
    ):
        self.__on_timeout = callback if callback is not None else lambda: None
        self.__timeout_ms = timeout_ms

    def subscribe(self, msg_type: type[T], callback: CallbackSpecific[T]):
        if msg_type not in self.__callbacks:
            self.__callbacks[msg_type] = []

        # Trust me that this function will only ever be called with T, not AnyMessage
        erased_callback = cast(CallbackAny, callback)
        self.__callbacks[msg_type].append(erased_callback)

    def subscribe_all(self, callback: CallbackSpecific[AnyMessage]):
        for _, ty in topics_map.items():
            self.subscribe(ty, callback)

    def subscribe_some(self, msg_types: list[type[T]], callback: CallbackSpecific[T]):
        for ty in msg_types:
            self.subscribe(ty, callback)

    def __run_receive_internal(self):
        logger.trace(
            f"module: {self.__module} receiving {[ty.topic for ty in self.__callbacks.keys()]}"
        )
        sub_socket = self.__context.socket(zmq.SUB)
        decoders: dict[str, msgspec.msgpack.Decoder[AnyMessage]] = {
            topic: msgspec.msgpack.Decoder(dec_hook=self.decode_hook, type=ty)
            for topic, ty in topics_map.items()
            if ty in self.__callbacks
        }
        for ty in self.__callbacks.keys():
            sub_socket.subscribe(ty.topic)
        sub_socket.subscribe(Shutdown.topic)

        sub_socket.connect(self.__sub_addr)

        poller: zmq.Poller = zmq.Poller()
        poller.register(sub_socket)
        while True:
            if poller.poll(timeout=self.__timeout_ms):
                parts = sub_socket.recv_multipart()
            else:
                ret = self.__on_timeout()
                if ret == "stop":
                    return
                continue
            assert len(parts) == 2
            topic = parts[0].decode()
            payload = parts[1]

            if topic == Shutdown.topic and Shutdown not in self.__callbacks:
                # Exit the thread
                logger.warning(
                    f"Shutting down pubsub without notifying owner ({self.__module})"
                )
                self.publish(Shutdown())
                break

            assert topic in topics_map, (
                f"topic: {topic} not in topics_map: {topics_map.keys()}"
            )

            logger.trace(f"module {self.__module} received {topic}")

            expected_type = topics_map[topic]
            assert topic in decoders, (
                f"topic: {topic} is not in decoders: {decoders.keys()}"
            )
            decoder = decoders[topic]

            msg = decoder.decode(payload)
            assert isinstance(msg, expected_type)

            assert expected_type in self.__callbacks, (
                f"type: {expected_type.__name__} is not in callbacks"
            )
            callbacks = self.__callbacks[expected_type]

            for callback in callbacks:
                ret = callback(msg)
                if ret == "stop":
                    return
            if topic == Shutdown.topic:
                logger.warning(
                    f"Shutdown received, but not ending pubsub recv thread in {self.__module}"
                )

    def run_receive(self, thread: bool = True):
        if thread:
            threading.Thread(target=self.__run_receive_internal, name=f"{self.__module}: run receive").start()
        else:
            self.__run_receive_internal()

    def publish(self, msg: AnyMessage):
        logger.trace(f"Module {self.__module} sent {msg.topic}")
        packed = self.__encoder.encode(msg)
        self.__pub_socket.send_multipart([msg.topic.encode(), packed])
