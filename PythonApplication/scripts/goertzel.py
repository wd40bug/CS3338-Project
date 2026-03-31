from rtty_sdr.dsp.engines import GoertzelEngine
from rtty_sdr.dsp.sources import MockSignalSource
from rtty_sdr.debug.awgn import awgn
from rtty_sdr.debug.internal_signal import internal_signal
from rtty_sdr.core.options import DecodeCommon, GoertzelOpts, RTTYOpts, SignalOpts
from rtty_sdr.core.baudot import BaudotEncoder

import matplotlib.pyplot as plt
import numpy as np

Fs = 8000
rtty = RTTYOpts(baud=45.45, mark=2125, shift=170, pre_msg_stops=1)
opts = SignalOpts(Fs, rtty)
message = "HI"
encoder = BaudotEncoder()
encoded = encoder.encode(message)
signal, t, annotations = internal_signal(encoded, opts)

powers = np.array([])
squelch = np.array([])

signal_power = np.array([])
noise_power = np.array([])
total_power = np.array([])
snr = np.array([])

signal = awgn(signal, 10)

decode = DecodeCommon(5, opts)

signal_source = MockSignalSource(signal, decode)
goertzel = GoertzelEngine(GoertzelOpts(0.5, 256, decode))

while True:
    chunk = signal_source.read_chunk()
    if chunk is None:
        break
    power, debug = goertzel.process(chunk)
    powers = np.append(powers, power)

fig = plt.figure()
# First plot
plt.plot(t, powers)
annotations.draw(fig.axes[0], Fs=Fs)
plt.title("Goertzel")
plt.ylabel("Magnitude")
plt.xlabel("Index")

plt.show()
