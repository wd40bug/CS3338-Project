from rtty_sdr.core.protocol import ProtocolDebug, RecvMessage, SendMessage, protocol
from rtty_sdr.debug.annotations import DebugAnnotations
from rtty_sdr.debug.squelch import plot_shaded_squelch
from rtty_sdr.debug.state_changes import graph_states
from rtty_sdr.dsp.decode import decode_stream
from rtty_sdr.dsp.engines import EnvelopeEngine, GoertzelEngine
from rtty_sdr.dsp.squelch import Squelch
from rtty_sdr.dsp.sources import MockSignalSource
from rtty_sdr.core.options import SystemOpts, RTTYOpts
from rtty_sdr.debug.awgn import awgn
from rtty_sdr.debug.internal_signal import internal_signal
from rtty_sdr.core.baudot import BaudotDecoder, BaudotEncoder

import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt
import sys

Fs = 8000
rtty = RTTYOpts(baud=45.45, mark=2125, shift=170, pre_msg_stops=1, stop_bits=2)
opts = SystemOpts(Fs, rtty)
message = "HI" if len(sys.argv) == 1 else sys.argv[1]

encoder = BaudotEncoder()
send_message = SendMessage(message, "KJ5OEH", encoder)
print(f"Sending: {send_message.encoding}")
encoded = send_message.codes
signal, t, annotations = internal_signal(encoded, opts, 0.05)

signal = awgn(signal, 10)

chunk_size = opts.nsamp // 5
overlap_size = chunk_size // 2

signal_source = MockSignalSource(signal, chunk_size)
# engine = GoertzelEngine(overlap_size, 256, opts)
engine = EnvelopeEngine(opts)

annotations = DebugAnnotations(np.array([]), np.array([]), np.array([]))
envelope: npt.NDArray[np.float64] = np.array([])
indices: npt.NDArray[np.int_] = np.array([])

squelch = Squelch(opts, 0.2, 1)
decoder = BaudotDecoder()

generator = decode_stream(signal_source, squelch, engine, opts, chunk_size // 4, chunk_size * 2)

for received in protocol(generator, decoder):
    debug: ProtocolDebug
    if isinstance(received, RecvMessage):
        print(f"Received: {received.encoding}")
        debug = received.debug
    else:
        debug = received

    fig, axs = plt.subplots(3,1)
    local_t = t[:len(debug.decode.envelope)]
    axs[0].plot(local_t, debug.decode.envelope)
    if isinstance(received, RecvMessage):
        axs[0].set_title(f"RTTY Message '{received.msg}' with annotations")
    else:
        axs[0].set_title(f"Incomplete RTTY Message with annotations")
    debug.decode.annotations.draw(axs[0], Fs=Fs)

    axs[1].plot(local_t, debug.decode.envelope)
    axs[1].set_title("With ProtocolState")
    graph_states(local_t, axs[1], debug.states)
    axs[1].legend(bbox_to_anchor=(1.00, 0.5), loc='center left', borderaxespad=0.)

    axs[2].plot(local_t, debug.decode.envelope)
    axs[2].set_title("With Squelch")
    plot_shaded_squelch(local_t, fig.axes[2], debug.decode.squelch)
    axs[2].legend(bbox_to_anchor=(1.00, 0.5), loc='center left', borderaxespad=0.)
    plt.show()
