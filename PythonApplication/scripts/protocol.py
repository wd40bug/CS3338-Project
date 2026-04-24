import queue

from loguru import logger
from rtty_sdr.core.protocol import RecvMessage, SendMessage
from rtty_sdr.debug.annotations import DebugAnnotations
from rtty_sdr.debug.squelch import plot_shaded_squelch
from rtty_sdr.debug.state_changes import graph_states
from rtty_sdr.dsp.decode import decode_stream
from rtty_sdr.dsp.engines import EnvelopeEngine, GoertzelEngine
from rtty_sdr.dsp.protocol_decode import protocol
from rtty_sdr.dsp.commands import CommandsQueueQueue, CommandsQueue
from rtty_sdr.dsp.squelch import Squelch
from rtty_sdr.dsp.sources import MockSignalSource
from rtty_sdr.core.options import SystemOpts

from rtty_sdr.debug.awgn import awgn
from rtty_sdr.debug.internal_signal import internal_signal

import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt
import sys

logger.remove()
logger.add(sys.stderr, level="TRACE")

opts = SystemOpts.default()
message = "HI" if len(sys.argv) == 1 else sys.argv[1]

send_message = SendMessage.create(message, "KJ5OEH", opts.baudot)
logger.info(f"Sending: {send_message}")
encoded = send_message.codes
signal, t, annotations = internal_signal(encoded, opts.signal, 0.05)

signal = awgn(signal, 10)

pill_queue: CommandsQueueQueue = queue.Queue()
pills = CommandsQueue(pill_queue)
signal_source = MockSignalSource(signal, opts.decode, None, pill_queue)

engine = GoertzelEngine(opts.goertzel)
# engine = EnvelopeEngine(opts.envelope)

annotations = DebugAnnotations(np.array([]), np.array([]), np.array([]))
envelope: npt.NDArray[np.float64] = np.array([])
indices: npt.NDArray[np.int_] = np.array([])

squelch = Squelch(opts.squelch)

generator = decode_stream(
    signal_source,
    squelch,
    engine,
    opts.stream,
    pills,
)

for received, debug in protocol(generator, opts.baudot):
    if isinstance(received, RecvMessage):
        logger.info(f"Received: {received}")

    fig, axs = plt.subplots(3, 1)
    local_t = t[: len(debug.decode.envelope)]
    axs[0].plot(local_t, debug.decode.envelope)
    if isinstance(received, RecvMessage):
        axs[0].set_title(f"RTTY Message '{received.msg}' with annotations")
    else:
        axs[0].set_title(f"Incomplete RTTY Message with annotations")
    debug.decode.annotations.draw(axs[0], Fs=opts.signal.Fs)

    axs[1].plot(local_t, debug.decode.envelope)
    axs[1].set_title("With ProtocolState")
    graph_states(local_t, axs[1], debug.states)
    axs[1].legend(bbox_to_anchor=(1.00, 0.5), loc="center left", borderaxespad=0.0)

    axs[2].plot(local_t, debug.decode.envelope)
    axs[2].set_title("With Squelch")
    plot_shaded_squelch(local_t, fig.axes[2], debug.decode.squelch)
    axs[2].legend(bbox_to_anchor=(1.00, 0.5), loc="center left", borderaxespad=0.0)
    plt.show()
