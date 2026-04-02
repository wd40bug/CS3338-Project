import threading
from rtty_sdr.core.protocol import ProtocolDebug, RecvMessage, SendMessage, protocol
from rtty_sdr.debug.annotations import DebugAnnotations
from rtty_sdr.debug.squelch import plot_shaded_squelch
from rtty_sdr.debug.state_changes import graph_states
from rtty_sdr.dsp.decode import decode_stream
from rtty_sdr.dsp.engines import EnvelopeEngine, GoertzelEngine
from rtty_sdr.dsp.poisonPill import PillQueue, QueuePoisonPill
from rtty_sdr.dsp.squelch import Squelch
from rtty_sdr.dsp.sources import MockSignalSource
from rtty_sdr.core.options import (
    DecodeCommon,
    GoertzelOpts,
    SignalOpts,
    SquelchOpts,
    SystemOpts,
    RTTYOpts,
    DecodeStreamOpts,
)
from rtty_sdr.debug.awgn import awgn
from rtty_sdr.debug.internal_signal import internal_signal
from rtty_sdr.core.baudot import BaudotDecoder, BaudotEncoder

import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt
import sys
from rtty_sdr.dsp.sources import MicrophoneSource
import queue

Fs = 8000
rtty = RTTYOpts(baud=45.45, mark=2125, shift=170, pre_msg_stops=1, stop_bits=2)
opts = SignalOpts(Fs=Fs, rtty=rtty)

chunk_size = opts.nsamp // 5
overlap_size = chunk_size // 2

decode = DecodeCommon(oversampling=5, signal=opts)
source = MicrophoneSource(decode)
engine = GoertzelEngine(GoertzelOpts(overlap_ratio=0.5, dft_len=256, decode=decode))

annotations = DebugAnnotations(np.array([]), np.array([]), np.array([]))
envelope: npt.NDArray[np.float64] = np.array([])
indices: npt.NDArray[np.int_] = np.array([])

squelch = Squelch(SquelchOpts(lower_thresh=0.2, upper_thresh=1, decode=decode))
decoder = BaudotDecoder()

num_msgs = 2

pill_queue: PillQueue = queue.Queue()
t = threading.Timer(10, lambda: pill_queue.put("stop"))

generator = decode_stream(
    source,
    squelch,
    engine,
    DecodeStreamOpts(
        squelch_grace_percent=0.25, idle_bits=2, none_friction=0.2, decode=decode
    ),
    QueuePoisonPill(pill_queue),
)

num_received = 0

t.start()

messages_received: list[RecvMessage | ProtocolDebug] = []
for received in protocol(generator, decoder):
    messages_received.append(received)
    if isinstance(received, RecvMessage):
        print(f"Received message: '{received.msg}'")
    t.cancel()
    t = threading.Timer(10, lambda: pill_queue.put("stop"))
    t.start()

for received in messages_received:
    debug: ProtocolDebug
    if isinstance(received, RecvMessage):
        debug = received.debug
    else:
        debug = received

    fig, axs = plt.subplots(3, 1)
    local_t = debug.decode.indices / Fs
    axs[0].plot(local_t, debug.decode.envelope)
    if isinstance(received, RecvMessage):
        axs[0].set_title(f"RTTY Message '{received.msg}' with annotations")
    else:
        axs[0].set_title(f"Incomplete RTTY Message with annotations")
    debug.decode.annotations.draw(axs[0], Fs=Fs)

    axs[1].plot(local_t, debug.decode.envelope)
    axs[1].set_title("With ProtocolState")
    graph_states(local_t, axs[1], debug.states)
    axs[1].legend(bbox_to_anchor=(1.00, 0.5), loc="center left", borderaxespad=0.0)

    axs[2].plot(local_t, debug.decode.envelope)
    axs[2].set_title("With Squelch")
    plot_shaded_squelch(local_t, fig.axes[2], debug.decode.squelch)
    axs[2].legend(bbox_to_anchor=(1.00, 0.5), loc="center left", borderaxespad=0.0)
    plt.show()
