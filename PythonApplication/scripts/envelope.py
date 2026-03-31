from rtty_sdr.dsp.engines import EnvelopeEngine
from rtty_sdr.dsp.sources import MockSignalSource
from rtty_sdr.core.options import DecodeCommon, EnvelopeOpts, SignalOpts, RTTYOpts
from rtty_sdr.debug.awgn import awgn
from rtty_sdr.debug.internal_signal import internal_signal
from rtty_sdr.core.baudot import BaudotEncoder

import numpy as np
import matplotlib.pyplot as plt

Fs = 8000
rtty = RTTYOpts(baud=45.45, mark=2125, shift=170, pre_msg_stops=1)
opts = SignalOpts(Fs, rtty)
message = "HI"
encoder = BaudotEncoder()
encoded = encoder.encode(message)
signal, t, annotations = internal_signal(encoded, opts)

signal = awgn(signal, 10)

decode = DecodeCommon(5, opts)

signal_source = MockSignalSource(signal, decode)
envelope_engine = EnvelopeEngine(EnvelopeOpts(4, decode))

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
