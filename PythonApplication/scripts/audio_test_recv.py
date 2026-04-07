import threading

from loguru import logger
from rtty_sdr.core.protocol import ProtocolDebug, RecvMessage, StoppedMsg, protocol
from rtty_sdr.debug.annotations import DebugAnnotations
from rtty_sdr.debug.squelch import plot_shaded_squelch
from rtty_sdr.debug.state_changes import graph_states
from rtty_sdr.dsp.decode import decode_stream
from rtty_sdr.dsp.engines import EnvelopeEngine, GoertzelEngine
from rtty_sdr.dsp.poisonPill import CommandsQueue, CommandsQueueQueue, FullStopCommand
from rtty_sdr.dsp.squelch import Squelch
from rtty_sdr.dsp.sources import MockSignalSource
from rtty_sdr.core.options import (
    SystemOpts,
    DecodeCommon
)
from rtty_sdr.core.baudot import BaudotDecoder

import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt
import sys
from rtty_sdr.dsp.sources import MicrophoneSource
import queue

opts = SystemOpts.default()

decode = DecodeCommon(oversampling=5, signal=opts.signal)
source = MicrophoneSource(decode)
engine = GoertzelEngine(opts.goertzel)

annotations = DebugAnnotations(np.array([]), np.array([]), np.array([]))
envelope: npt.NDArray[np.float64] = np.array([])
indices: npt.NDArray[np.int_] = np.array([])

squelch = Squelch(opts.squelch)
decoder = BaudotDecoder()

num_msgs = 2

pill_queue: CommandsQueueQueue = queue.Queue()
t = threading.Timer(10, lambda: pill_queue.put(FullStopCommand()))

generator = decode_stream(
    source,
    squelch,
    engine,
    opts.stream,
    CommandsQueue(pill_queue),
)

num_received = 0

t.start()

messages_received: list[RecvMessage | StoppedMsg] = []
for received in protocol(generator, decoder):
    messages_received.append(received)
    if isinstance(received, RecvMessage):
        logger.info(f"Received message: '{received.msg}'")
    t.cancel()
    t = threading.Timer(10, lambda: pill_queue.put(FullStopCommand()))
    t.start()

for received in messages_received:
    debug: ProtocolDebug
    debug = received.debug

    fig, axs = plt.subplots(3, 1)
    local_t = debug.decode.indices / opts.signal.Fs
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
