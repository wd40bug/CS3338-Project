from loguru import logger
import zmq
import threading
from typing import Final, Optional


BROKER_FRONTEND: Final[str] = "ipc:///tmp/app_frontend.ipc"
BROKER_BACKEND: Final[str] = "ipc:///tmp/app_backend.ipc"
DEBUG_SOCKET: Final[str] = "ipc:///tmp/app_backend_debug.ipc"


class BrokerModule(threading.Thread):
    """Thread to fascilitate PubSub"""
    def __init__(self) -> None:
        super().__init__()
        # Declare private variables, but do NOT initialize ZeroMQ objects here.
        # They must be created inside run() to guarantee they belong to the correct thread.
        self.__context: Optional[zmq.Context] = None
        self.__frontend: Optional[zmq.Socket] = None
        self.__backend: Optional[zmq.Socket] = None
        self.__debug: Optional[zmq.Socket] = None

    def run(self) -> None:
        """The main execution loop for the broker thread."""

        # 1. Initialize inside the target thread
        self.__context = zmq.Context()
        self.__frontend = self.__context.socket(zmq.SUB)
        self.__backend = self.__context.socket(zmq.PUB)
        self.__debug = self.__context.socket(zmq.PUB)

        assert isinstance(self.__context, zmq.Context)
        assert isinstance(self.__frontend, zmq.Socket)
        assert isinstance(self.__backend, zmq.Socket)
        assert isinstance(self.__debug, zmq.Socket)

        self.__frontend.setsockopt_string(zmq.SUBSCRIBE, "")
        self.__backend.setsockopt(zmq.LINGER, 0)
        self.__debug.setsockopt(zmq.LINGER, 0)

        try:
            # 2. Bind to the IPC endpoints
            self.__frontend.bind(BROKER_FRONTEND)
            self.__backend.bind(BROKER_BACKEND)
            self.__debug.bind(DEBUG_SOCKET)

            logger.info("Online. Routing traffic...")

            # 3. Start the proxy (Blocks forever until context is terminated)
            logger.info("Broker running")
            zmq.proxy(self.__frontend, self.__backend, self.__debug)

        except zmq.error.ContextTerminated:
            # This is intentionally triggered by the stop() method
            logger.info("Context terminated. Shutting down gracefully...")
        except Exception as e:
            logger.exception(f"Fatal error: {e}")
        finally:
            if self.__frontend is not None:
                self.__frontend.close(linger=0)

            if self.__backend is not None:
                self.__backend.close(linger=0)

            if self.__debug is not None:
                self.__debug.close(linger=0)

            logger.info("Offline.")

    def stop(self) -> None:
        """
        Thread-safe method to stop the proxy from the main thread
        """
        if self.__context is not None:
            self.__context.term()
