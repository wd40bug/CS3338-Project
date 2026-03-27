from rtty_sdr.debug.annotations import DebugAnnotations
from rtty_sdr.dsp.decode import decode_stream
from rtty_sdr.dsp.engines import EnvelopeEngine, GoertzelEngine
from rtty_sdr.dsp.sources import MockSignalSource
from rtty_sdr.core.options import SystemOpts, RTTYOpts
from rtty_sdr.debug.awgn import awgn
from rtty_sdr.debug.internal_signal import internal_signal
from rtty_sdr.core.baudot import BaudotDecoder, BaudotEncoder

import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt

from rtty_sdr.dsp.squelch import Squelch

Fs = 8000
rtty = RTTYOpts(baud=45.45, mark=2125, shift=170, pre_msg_stops=1)
opts = SystemOpts(Fs, rtty)
message = "HI"
encoder = BaudotEncoder()
encoded = encoder.encode(message)
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

for ret in decode_stream(signal_source, squelch, engine, opts):
    assert ret != "reset"
    code, debug = ret
    print(f"Code: {code} -> {decoder.decode(code)}")
    index = np.concat((indices, debug.indices))
    envelope = np.concat((envelope, debug.envelope))
    annotations.join(debug.annotations)

fig = plt.figure()
plt.plot(t[:len(envelope)], envelope)
annotations.draw(fig.axes[0], delay=squelch.delay, Fs=Fs)
plt.show()
