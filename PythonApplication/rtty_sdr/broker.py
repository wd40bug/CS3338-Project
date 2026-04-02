import msgspec
import zmq
import threading
from typing import Final, Any, Dict, Optional, Type, Mapping, Literal
from pydantic import BaseModel, ValidationError
import msgpack
import dataclasses
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.core.protocol import RecvMessage, SendMessage
# Topics
# ui.settings
# ui.send
# ui.send_internal
# ui.shutdown
# dsp.received
# dsp.receiving (TODO)
# error_corr.corrected
# controller.sent

TOPICS: dict[str, type[msgspec.Struct] | Literal["no payload"]] = {
    "ui.settings": SystemOpts,
    "ui.send": SendMessage,
    "ui.shutdown": "no payload",
    "dsp.received": RecvMessage,
    "dsp.receiving": "no payload",
    "error_correction.corrected": RecvMessage,
    "controller.sent": "no payload",
}

DECODER_REGISTRY: dict[
    "str", msgspec.msgpack.Decoder[msgspec.Struct] | Literal["no payload"]
] = {
    topic: msgspec.msgpack.Decoder(t) if t != "no payload" else "no payload"
    for topic, t in TOPICS.items()
}

BROKER_FRONTEND: Final[str] = "ipc:///tmp/app_frontend.ipc"
BROKER_BACKEND: Final[str] = "ipc:///tmp/app_backend.ipc"


class BrokerModule(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        # Declare private variables, but do NOT initialize ZeroMQ objects here.
        # They must be created inside run() to guarantee they belong to the correct thread.
        self.__context: Optional[zmq.Context] = None
        self.__frontend: Optional[zmq.Socket] = None
        self.__backend: Optional[zmq.Socket] = None

    def run(self) -> None:
        """The main execution loop for the broker thread."""

        # 1. Initialize inside the target thread
        self.__context = zmq.Context()
        self.__frontend = self.__context.socket(zmq.XSUB)
        self.__backend = self.__context.socket(zmq.XPUB)

        assert isinstance(self.__context, zmq.Context)
        assert isinstance(self.__frontend, zmq.Socket)
        assert isinstance(self.__backend, zmq.Socket)

        try:
            # 2. Bind to the IPC endpoints
            self.__frontend.bind(BROKER_FRONTEND)
            self.__backend.bind(BROKER_BACKEND)

            print("[Broker] Online. Routing traffic...")

            # 3. Start the proxy (Blocks forever until context is terminated)
            zmq.proxy(self.__frontend, self.__backend)

        except zmq.error.ContextTerminated:
            # This is intentionally triggered by the stop() method
            print("[Broker] Context terminated. Shutting down gracefully...")
        except Exception as e:
            print(f"[Broker] Fatal error: {e}")
        finally:
            self.__cleanup()

    def stop(self) -> None:
        """
        Thread-safe method to stop the proxy from the main thread.
        Terminating the context raises zmq.ContextTerminated inside run().
        """
        if self.__context is not None:
            self.__context.term()

    def __cleanup(self) -> None:
        """Ensures all sockets are cleanly destroyed."""
        # Linger=0 drops pending messages immediately upon close to prevent hanging
        if self.__frontend is not None:
            self.__frontend.close(linger=0)

        if self.__backend is not None:
            self.__backend.close(linger=0)

        print("[Broker] Offline.")


encoder = msgspec.msgpack.Encoder()


def publish_message(
    pub_socket: zmq.Socket, topic: str, payload: Optional[msgspec.Struct]
) -> None:
    # Send the multipart message: [Topic, Data]
    pub_socket.send_string(topic, flags=zmq.SNDMORE)
    if payload is not None:
        packed = encoder.encode(payload)
    else:
        packed = encoder.encode({})
    pub_socket.send(packed)


def __internal_receive_msg(
    sub_socket: zmq.Socket, flags: int
) -> tuple[str, Optional[msgspec.Struct]]:
    """
    INTERNAL: Core receiving and validation logic.
    Do not call this directly. Use receive_message or receive_message_nowait.
    """
    # 1. Receive data (Exceptions bubble up to the wrapper)
    topic: str = sub_socket.recv_string(flags=flags)
    packed_payload: bytes = sub_socket.recv(flags=flags)

    if not topic in TOPICS:
        raise ValueError(f"Unknown topic: {topic}")

    decoder = DECODER_REGISTRY[topic]
    payload = None
    if decoder != 'no payload':
        payload = decoder.decode(packed_payload)

    return topic, payload


# ==========================================
# PUBLIC API
# ==========================================


def receive_message(
    sub_socket: zmq.Socket) -> tuple[str, Optional[msgspec.Struct]]:
    """
    Blocks until a multipart ZeroMQ message arrives, then reconstructs the Python object.
    """
    # Pass flags=0 for standard blocking behavior
    return __internal_receive_msg(sub_socket, flags=0)


def receive_message_nowait(
    sub_socket: zmq.Socket
) -> Optional[tuple[str, Optional[msgspec.Struct]]]:
    """
    Non-blocking check for a multipart ZeroMQ message.
    Returns None if the network queue is empty.
    """
    try:
        return __internal_receive_msg(sub_socket, flags=zmq.NOBLOCK)
    except zmq.Again:
        return None
