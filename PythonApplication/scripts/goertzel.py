from rtty_sdr.debug.squelch import plot_shaded_squelch
from rtty_sdr.dsp.engines import GoertzelEngine
from rtty_sdr.dsp.sources import MockSignalSource
from rtty_sdr.debug.awgn import awgn
from rtty_sdr.debug.internal_signal import internal_signal
from rtty_sdr.core.options import SystemOpts, RTTYOpts
from rtty_sdr.core.baudot import BaudotEncoder

import matplotlib.pyplot as plt
import numpy as np

Fs = 8000
rtty = RTTYOpts(baud=45.45, mark=2125, shift=170, pre_msg_stops=1)
opts = SystemOpts(Fs, rtty)
message = "HI"
encoder = BaudotEncoder()
encoded = encoder.encode(message)
signal, t, annotations = internal_signal(encoded, opts)

chunk_size = opts.nsamp // 5
overlap_size = chunk_size // 2

powers = np.array([])
squelch = np.array([])

signal_power = np.array([])
noise_power = np.array([])
total_power = np.array([])
snr = np.array([])

signal = awgn(signal, 10)

signal_source = MockSignalSource(signal, chunk_size)
goertzel = GoertzelEngine(overlap_size, 256, opts)

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
