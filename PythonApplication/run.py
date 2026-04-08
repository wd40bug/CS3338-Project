import multiprocessing as mp
import time
from typing import Final, Deque
import collections

from loguru import logger
import loguru

from rtty_sdr.comms.broker import BrokerModule
from rtty_sdr.comms.topics import TopicsRegistry
from rtty_sdr.controller.controller import ControllerModule
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.dsp.DSP import DspModule
from rtty_sdr.ui.TUI import RttyTerminal
from rtty_sdr.debug.debug_socket import DebugSocket
from rtty_sdr.debug.squelch import plot_shaded_squelch
from rtty_sdr.debug.state_changes import graph_states

logger.remove(0)
logger.add("log.log", level="TRACE", mode="w", enqueue=True)
early_logs: Final[Deque[loguru.Message]] = collections.deque(maxlen=500)


def temp_memory_sink(message: loguru.Message) -> None:
    early_logs.append(message)


temp_handler_id = logger.add(
    temp_memory_sink, colorize=True, level="TRACE", enqueue=True
)

if __name__ == "__main__":
    settings = SystemOpts.default(
        source="microphone", engine="goertzel", pre_msg_stops=20
    )

    # Required for safe cross-platform multiprocessing, though
    # openSUSE handles standard fork() well.
    mp.set_start_method("spawn", force=True)

    registry = TopicsRegistry()
    ui = RttyTerminal(registry, settings)
    broker = BrokerModule()
    debug_socket = DebugSocket(registry)
    dsp = DspModule(settings, registry)
    controller = ControllerModule(settings, registry)

    broker.start()
    time.sleep(0.2)
    debug_socket.start()
    dsp.start()
    controller.start()

    retcode = ui.run()

    logger.info(f"UI Exited with code: {retcode}")
    # breakpoint()

    debug_socket.join()
    dsp.join()
    controller.join()
    broker.stop()

    # code.interact(local=locals())

    # summed_debug = debug_socket.collect()
    #
    # fig, axs = plt.subplots(3, 1)
    # local_t = summed_debug.decode.indices / settings.signal.Fs
    # logger.debug(f"Shape of envelope is {summed_debug.decode.envelope.shape}")
    # axs[0].plot(local_t, summed_debug.decode.envelope)
    # summed_debug.decode.annotations.draw(axs[0], Fs=settings.signal.Fs)
    #
    # axs[1].plot(local_t, summed_debug.decode.envelope)
    # axs[1].set_title("With ProtocolState")
    # graph_states(local_t, axs[1], summed_debug.states)
    # axs[1].legend(bbox_to_anchor=(1.00, 0.5), loc="center left", borderaxespad=0.0)
    #
    # axs[2].plot(local_t, summed_debug.decode.envelope)
    # axs[2].set_title("With Squelch")
    # plot_shaded_squelch(local_t, fig.axes[2], summed_debug.decode.squelch)
    # axs[2].legend(bbox_to_anchor=(1.00, 0.5), loc="center left", borderaxespad=0.0)
    # plt.show()
