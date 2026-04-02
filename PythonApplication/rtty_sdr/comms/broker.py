import zmq
import threading
from typing import Final, Optional


BROKER_FRONTEND: Final[str] = "ipc:///tmp/app_frontend.ipc"
BROKER_BACKEND: Final[str] = "ipc:///tmp/app_backend.ipc"
DEBUG_SOCKET: Final[str] = "ipc:///tmp/app_backend_debug.ipc"


class BrokerModule(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
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

        try:
            # 2. Bind to the IPC endpoints
            self.__frontend.bind(BROKER_FRONTEND)
            self.__backend.bind(BROKER_BACKEND)
            self.__debug.bind(DEBUG_SOCKET)

            print("[Broker] Online. Routing traffic...")

            # 3. Start the proxy (Blocks forever until context is terminated)
            zmq.proxy(self.__frontend, self.__backend, self.__debug)

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
