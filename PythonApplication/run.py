import multiprocessing as mp
import sys
import time
from typing import Final, Deque
import collections

from loguru import logger
import loguru

from rtty_sdr.comms.broker import BrokerModule
from rtty_sdr.controller.controller import ControllerModule
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.dsp.DSP import DspModule
from rtty_sdr.debug.debug_socket import DebugSocket
from rtty_sdr.ui.GUI import RttyWebTerminal, ui

logger.remove()
logger.add(sys.stderr, level="TRACE", enqueue=True)
logger.add("log.log", level="TRACE", mode="a", enqueue=True)
early_logs: Final[Deque[loguru.Message]] = collections.deque(maxlen=500)


def temp_memory_sink(message: loguru.Message) -> None:
    early_logs.append(message)


temp_handler_id = logger.add(
    temp_memory_sink, colorize=True, level="TRACE", enqueue=True
)

opts = SystemOpts.default(source='internal')

@ui.page("/")
def index_page() -> None:
    opts: Final[SystemOpts] = SystemOpts.default(source="internal")
    # Kept early_logs in the instantiation just in case other parts of your architecture strictly pass it
    RttyWebTerminal(initial_settings=opts)

if __name__ == "__main__":
    # Required for safe cross-platform multiprocessing, though
    # openSUSE handles standard fork() well.
    mp.set_start_method("spawn", force=True)


    broker = BrokerModule()
    debug_socket = DebugSocket()
    dsp = DspModule(opts)
    # controller = ControllerModule(current_system_opts)

    broker.start()
    time.sleep(0.2)
    debug_socket.start()
    # controller.start()
    dsp.start()
    time.sleep(1)

    retcode = ui.run(reload=False, title="RTTY Chat", dark=False, port=8080)

    logger.info(f"UI Exited with code: {retcode}")
    # breakpoint()

    debug_socket.join()
    dsp.join()
    # controller.join()
    broker.stop()

    # breakpoint()
