import zmq

from rtty_sdr.comms.broker import BROKER_BACKEND, BROKER_FRONTEND
from typing import Any, Optional, get_origin
from rtty_sdr.comms.topics import TopicsRegistry
import msgspec

import numpy as np


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

    def __init__(self, subscribe_to: list[str], registry: TopicsRegistry) -> None:
        self.__context: zmq.Context = zmq.Context()
        self.__sub_socket: zmq.Socket = self.__context.socket(zmq.SUB)
        self.__sub_socket.connect(BROKER_BACKEND)
        for topic in subscribe_to:
            self.__sub_socket.subscribe(topic)

        self.__pub_socket: zmq.Socket = self.__context.socket(zmq.PUB)
        self.__pub_socket.connect(BROKER_FRONTEND)
        self.__decoder_registry = {
            topic: msgspec.msgpack.Decoder(
                registry.get(topic), dec_hook=self.decode_hook
            )
            for topic in subscribe_to
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

    def __recv_message_internal(self, flags: int):
        topic: str = self.__sub_socket.recv_string(flags=flags)
        if self.__sub_socket.getsockopt(zmq.RCVMORE):
            packed_payload: bytes = self.__sub_socket.recv(flags=flags)
            decoder = self.__decoder_registry[topic]
            payload = decoder.decode(packed_payload)
        else:
            payload = None

        self.__registry.validate(topic, payload)

        return topic, payload

    def recv_message_nowait(self) -> Optional[tuple[str, Optional[msgspec.Struct]]]:
        try:
            return self.__recv_message_internal(flags=zmq.NOBLOCK)
        except zmq.Again:
            return None

    def recv_message(self) -> tuple[str, Optional[msgspec.Struct]]:
        return self.__recv_message_internal(flags=0)
