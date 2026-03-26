from rtty_sdr.dsp.engines import EnvelopeEngine
from rtty_sdr.dsp.sources import MockSignalSource
from rtty_sdr.core.options import SystemOpts, RTTYOpts
from rtty_sdr.debug.awgn import awgn
from rtty_sdr.debug.internal_signal import internal_signal
from rtty_sdr.core.baudot import BaudotEncoder

import numpy as np
import matplotlib.pyplot as plt

Fs = 8000
rtty = RTTYOpts(baud=45.45, mark=2125, shift=170, pre_msg_stops=1)
opts = SystemOpts(Fs, rtty)
message = "HI"
encoder = BaudotEncoder()
encoded = encoder.encode(message)
signal, t, annotations = internal_signal(encoded, opts)

signal = awgn(signal, 10)

chunk_size = opts.nsamp // 5

signal_source = MockSignalSource(signal, chunk_size)
envelope_engine = EnvelopeEngine(opts)

diff_env = []

try:
    while True:
        chunk = signal_source.read_chunk()
        env, _ = envelope_engine.process(chunk)
        diff_env = np.append(diff_env, env)
except StopIteration:
    pass

delay = envelope_engine.delay

fig = plt.figure()
plt.plot(t, diff_env)
annotations.draw(fig.axes[0], delay, Fs)
plt.show()
