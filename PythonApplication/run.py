import multiprocessing as mp
import time
from typing import Final, Deque
import collections

from loguru import logger
import loguru

from rtty_sdr.comms.broker import BrokerModule
from rtty_sdr.controller.controller import ControllerModule
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.dsp.DSP import DspModule
from rtty_sdr.ui.TUI import RttyTerminal
from rtty_sdr.debug.debug_socket import DebugSocket

logger.remove(0)
logger.add("log.log", level="TRACE", mode="a", enqueue=True)
early_logs: Final[Deque[loguru.Message]] = collections.deque(maxlen=500)


def temp_memory_sink(message: loguru.Message) -> None:
    early_logs.append(message)


temp_handler_id = logger.add(
    temp_memory_sink, colorize=True, level="TRACE", enqueue=True
)

if __name__ == "__main__":
    settings = SystemOpts.default(
        source="internal", engine="goertzel", pre_msg_stops=20
    )

    # Required for safe cross-platform multiprocessing, though
    # openSUSE handles standard fork() well.
    mp.set_start_method("spawn", force=True)

    ui = RttyTerminal(settings)
    broker = BrokerModule()
    debug_socket = DebugSocket()
    dsp = DspModule(settings)
    controller = ControllerModule(settings)

    broker.start()
    time.sleep(0.2)
    debug_socket.start()
    controller.start()
    dsp.start()
    time.sleep(1)

    retcode = ui.run()

    logger.info(f"UI Exited with code: {retcode}")
    # breakpoint()

    debug_socket.join()
    dsp.join()
    controller.join()
    broker.stop()

    # breakpoint()
