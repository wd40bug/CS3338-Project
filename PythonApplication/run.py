import multiprocessing as mp
import threading
import sys
import time
from typing import Final, List, Any

from loguru import logger

from rtty_sdr.broker import BrokerModule
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.dsp.DSP import DspModule
from rtty_sdr.ui.UI import MockUI


# --- Mocking the imported modules for demonstration ---
class MockThread(threading.Thread):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.__name: Final[str] = name

    def run(self) -> None:
        logger.info(f"Running: {self.__name}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


class MockProcess(mp.Process):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.__name = name

    def run(self) -> None:
        logger.info(f"Running: {self.__name}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


settings = SystemOpts.default(source='internal')
# ------------------------------------------------------


class AppRunner:
    """Orchestrates the startup and shutdown of all application components."""

    def __init__(
        self,
        processes: list[mp.Process],
        threads: list[threading.Thread],
    ) -> None:
        # Keep track of processes so we can cleanly terminate them later
        self.__ui = MockUI(settings)
        self.__broker = BrokerModule()
        self.__processes: Final[List[mp.Process]] = processes
        self.__threads: Final[list[threading.Thread]] = threads

    def run(self) -> None:
        """Starts the architecture and hands control over to the UI."""

        # 1. Start the ZeroMQ Broker first (I/O bound -> Thread)
        self.__broker.start()

        # Give the broker a fraction of a second to bind its IPC sockets
        time.sleep(0.1)

        for start in self.__processes + self.__threads:
            start.start()

        # 4. Start User Interface (Must be Main Thread)
        try:
            self.__ui.run()  # <--- Execution blocks here until the UI is closed
        finally:
            self.__broker.stop()
            logger.info("Cleaning up background processes...")
            for p in self.__processes:
                if p.is_alive():
                    logger.info(f"\tTerminating {p.name}...")
                    p.terminate()
                    p.join(timeout=2.0)

                    # Force kill if it hangs during termination
                    if p.is_alive():
                        p.kill()

            logger.info("Application exited cleanly.")

        return

if __name__ == "__main__":
    # Required for safe cross-platform multiprocessing, though
    # openSUSE handles standard fork() well.
    mp.set_start_method("spawn", force=True)

    runner = AppRunner(
        [DspModule(settings), MockProcess("error correction")], [MockThread("controller")]
    )
    sys.exit(runner.run())
