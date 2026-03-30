from rtty_sdr.core.protocol import SendMessage, protocol
from rtty_sdr.debug.annotations import DebugAnnotations
from rtty_sdr.debug.squelch import plot_shaded_squelch
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
rtty = RTTYOpts(baud=45.45, mark=2125, shift=170, pre_msg_stops=1)
opts = SystemOpts(Fs, rtty)
message = "HI" if len(sys.argv) == 1 else sys.argv[1]

encoder = BaudotEncoder()
send_message = SendMessage(message, "KJ5OEH", encoder)
print(f"Sending: {send_message.encoding}")
encoded = send_message.codes
signal, t, annotations = internal_signal(encoded, opts)

signal = awgn(signal, 10)

chunk_size = opts.nsamp // 5
overlap_size = chunk_size // 2

signal_source = MockSignalSource(signal, chunk_size)
engine = GoertzelEngine(overlap_size, 256, opts)

annotations = DebugAnnotations(np.array([]), np.array([]), np.array([]))
envelope: npt.NDArray[np.float64] = np.array([])
indices: npt.NDArray[np.int_] = np.array([])

squelch = Squelch(opts, 0.2, 1)
decoder = BaudotDecoder()

generator = decode_stream(signal_source, squelch, engine, opts)

for received in protocol(generator, decoder):
    print(f"Received: {received.encoding}")
    fig = plt.figure()
    plt.plot(t[:len(received.debug.decode.envelope)], received.debug.decode.envelope)
    plot_shaded_squelch(t[:len(received.debug.decode.envelope)], fig.axes[0], received.debug.decode.squelch)
    received.debug.decode.annotations.draw(fig.axes[0], Fs=Fs)
    plt.show()
