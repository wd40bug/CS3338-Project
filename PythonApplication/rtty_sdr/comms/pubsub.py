import zmq

from rtty_sdr.comms.broker import BROKER_BACKEND, BROKER_FRONTEND
from typing import Any, Optional, get_origin
from rtty_sdr.comms.topics import TopicsRegistry
import msgspec

import numpy as np
import math


class PubSub:
    # Topics
    # ui.settings
    # ui.send
    # ui.send_internal
    # ui.shutdown
    # dsp.received
    # dsp.receiving
    # error_corr.corrected
    # controller.sent

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
        subscribe_to: list[str] | None,
        registry: TopicsRegistry,
        pub_addr: str = BROKER_FRONTEND,
        sub_addr: str = BROKER_BACKEND,
    ) -> None:
        self.__context: zmq.Context = zmq.Context()
        self.__sub_socket: zmq.Socket = self.__context.socket(zmq.SUB)
        self.__sub_socket.connect(sub_addr)
        if subscribe_to is not None:
            for topic in subscribe_to:
                self.__sub_socket.subscribe(topic)
        else:
            self.__sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

        self.__pub_socket: zmq.Socket = self.__context.socket(zmq.PUB)
        self.__pub_socket.connect(pub_addr)
        self.__pub_socket.setsockopt(zmq.LINGER, 1000)
        if subscribe_to is not None:
            self.__decoder_registry = {
                topic: msgspec.msgpack.Decoder(
                    registry.get(topic), dec_hook=self.decode_hook
                )
                for topic in subscribe_to
                if registry.get(topic) is not None
            }
        else:
            self.__decoder_registry = {
                topic: msgspec.msgpack.Decoder(ty, dec_hook=self.decode_hook)
                for topic, ty in registry.TOPICS.items()
                if ty is not None
            }
        self.__encoder = msgspec.msgpack.Encoder(enc_hook=self.encode_hook)
        self.__registry = registry

    def publish_message(self, topic: str, payload: msgspec.Struct | None):
        self.__registry.validate(topic, payload)
        if payload is not None:
            packed = self.__encoder.encode(payload)
            self.__pub_socket.send_multipart([topic.encode("utf-8"), packed])
        else:
            self.__pub_socket.send_string(topic)

    def recv_message_timeout(
        self, timeout_ms: int | None = None
    ) -> Optional[tuple[str, Optional[msgspec.Struct]]]:
        poller = zmq.Poller()
        poller.register(self.__sub_socket)
        if poller.poll(timeout=timeout_ms):
            topic: str = self.__sub_socket.recv_string()
        else:
            return None

        if self.__sub_socket.getsockopt(zmq.RCVMORE):
            # TODO: Could implement blocking logic here, but since it's always sent back-to-back idk
            packed_payload: bytes = self.__sub_socket.recv()
            decoder = self.__decoder_registry[topic]
            payload = decoder.decode(packed_payload)
        else:
            payload = None

        self.__registry.validate(topic, payload)

        return topic, payload

    def recv_message(self) -> tuple[str, Optional[msgspec.Struct]]:
        recv = self.recv_message_timeout()
        assert recv is not None
        return recv
