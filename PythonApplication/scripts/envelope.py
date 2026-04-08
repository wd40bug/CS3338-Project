from rtty_sdr.dsp.engines import EnvelopeEngine
from rtty_sdr.dsp.sources import MockSignalSource
from rtty_sdr.core.options import DecodeCommon, EnvelopeOpts, Shift, SignalOpts, RTTYOpts, SystemOpts
from rtty_sdr.debug.awgn import awgn
from rtty_sdr.debug.internal_signal import internal_signal
from rtty_sdr.core.baudot import encode

import numpy as np
import matplotlib.pyplot as plt

Fs = 8000
opts = SystemOpts.default(initial_shift=Shift.LTRS)
message = "HI"
encoded, _ = encode(message, opts.baudot)
signal, t, annotations = internal_signal(encoded, opts.signal)

signal = awgn(signal, 10)

signal_source = MockSignalSource(signal, opts.decode)
envelope_engine = EnvelopeEngine(opts.envelope)

diff_env = np.array([])

while True:
    chunk = signal_source.read_chunk()
    if chunk is None:
        break
    env, _ = envelope_engine.process(chunk)
    diff_env = np.append(diff_env, env)

delay = envelope_engine.delay

fig = plt.figure()
plt.plot(t, diff_env)
annotations.draw(fig.axes[0], delay, Fs)
plt.title("Envelope")
plt.xlabel("Index")
plt.ylabel("Magnitude")
plt.show()
