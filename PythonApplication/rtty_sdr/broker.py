import zmq
import threading
import time
from typing import Final, Any, Dict, Optional, Type, Mapping
from pydantic import BaseModel, ValidationError
import dataclasses

from rtty_sdr.core.module import Module
# Topics
# ui.settings
# ui.send
# ui.shutdown
# dsp.received
# dsp.receiving
# error_corr.corrected
# controller.sent

BROKER_FRONTEND: Final[str] = "ipc:///tmp/app_frontend.ipc"
BROKER_BACKEND: Final[str] = "ipc:///tmp/app_backend.ipc"

class BrokerModule(Module):
    def __init__(self) -> None:
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


def publish_message(
    pub_socket: zmq.Socket, 
    topic: str, 
    payload: Optional[Any] = None
) -> None:
    """
    Serializes and publishes a message over a ZeroMQ socket.
    
    Supports Pydantic BaseModels, standard Dataclasses, plain dictionaries, 
    or None (sends an empty JSON object).
    """
    payload_dict: Dict[str, Any] = {}

    if payload is not None:
        if isinstance(payload, BaseModel):
            # Safely extract data from a Pydantic model
            payload_dict = payload.model_dump()
            
        elif dataclasses.is_dataclass(payload) and not isinstance(payload, type):
            # Safely extract data from a standard dataclass
            # Note: Do not pass the class itself, pass the instantiated object
            payload_dict = dataclasses.asdict(payload)
            
        elif isinstance(payload, dict):
            # Pass dictionaries through directly
            payload_dict = payload
            
        else:
            raise TypeError(
                f"Unsupported payload type: {type(payload)}. "
                "Must be a Pydantic BaseModel, Dataclass, or Dict."
            )

    # Send the multipart message: [Topic, Data]
    pub_socket.send_string(topic, flags=zmq.SNDMORE)
    pub_socket.send_json(payload_dict)


import zmq
import dataclasses
from pydantic import BaseModel, ValidationError
from typing import Any, Dict, Tuple, Type, Optional

def __internal_receive_msg(
    sub_socket: zmq.Socket, 
    topic_map: Mapping[str, Type[Any]],
    flags: int
) -> Tuple[str, Optional[Any]]:
    """
    INTERNAL: Core receiving and validation logic. 
    Do not call this directly. Use receive_message or receive_message_nowait.
    """
    # 1. Receive data (Exceptions bubble up to the wrapper)
    topic: str = sub_socket.recv_string(flags=flags)
    raw_payload: Any = sub_socket.recv_json(flags=flags)

    # 2. Narrow type and validate
    if not isinstance(raw_payload, dict):
        print(f"[Network] Dropped payload for '{topic}': Expected dict, got {type(raw_payload).__name__}")
        return topic, None
    
    payload_dict: Dict[str, Any] = raw_payload
    expected_type: Optional[Type[Any]] = None
    
    for key in sorted(topic_map.keys(), key=len, reverse=True):
        if topic.startswith(key):
            expected_type = topic_map[key]
            break

    if expected_type is None:
        print(f"[Network] Warning: No type mapping found for topic '{topic}'")
        return topic, payload_dict

    # 3. Reconstruct payload
    try:
        if issubclass(expected_type, BaseModel):
            return topic, expected_type.model_validate(payload_dict)
        elif dataclasses.is_dataclass(expected_type) and not isinstance(expected_type, type):
            return topic, expected_type(**payload_dict)
        elif expected_type is dict:
            return topic, payload_dict
        elif expected_type is type(None):
            return topic, None
        else:
            raise TypeError(f"Unsupported mapped type: {expected_type}")
            
    except (ValidationError, TypeError) as e:
        print(f"[Network] Dropped malformed payload for '{topic}': {e}")
        return topic, None


# ==========================================
# PUBLIC API
# ==========================================

def receive_message(
    sub_socket: zmq.Socket, 
    topic_map: Mapping[str, Type[Any]]
) -> Tuple[str, Optional[Any]]:
    """
    Blocks until a multipart ZeroMQ message arrives, then reconstructs the Python object.
    """
    # Pass flags=0 for standard blocking behavior
    return __internal_receive_msg(sub_socket, topic_map, flags=0)


def receive_message_nowait(
    sub_socket: zmq.Socket, 
    topic_map: Mapping[str, Type[Any]]
) -> Optional[Tuple[str, Optional[Any]]]:
    """
    Non-blocking check for a multipart ZeroMQ message.
    Returns None if the network queue is empty.
    """
    try:
        # Pass the NOBLOCK flag to check instantly
        return __internal_receive_msg(sub_socket, topic_map, flags=zmq.NOBLOCK)
    except zmq.Again:
        # Catch the exception here so the calling module doesn't have to import zmq
        return None
