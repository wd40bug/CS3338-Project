from rtty_sdr.dsp.engines import GoertzelEngine
from rtty_sdr.dsp.sources import MockSignalSource
from rtty_sdr.debug.awgn import awgn
from rtty_sdr.debug.internal_signal import internal_signal
from rtty_sdr.core.options import Shift, SystemOpts
from rtty_sdr.core.baudot import encode

import matplotlib.pyplot as plt
import numpy as np

opts = SystemOpts.default(initial_shift=Shift.LTRS, pre_msg_stops=1, overlap_ratio=1)
message = "HI"
encoded, _ = encode(message, opts.baudot)
signal, t, annotations = internal_signal(encoded, opts.signal)

powers = np.array([])
squelch = np.array([])

signal_power = np.array([])
noise_power = np.array([])
total_power = np.array([])
snr = np.array([])

signal = awgn(signal, 10)


signal_source = MockSignalSource(signal, opts.source_chunk_size)
goertzel = GoertzelEngine(opts.goertzel)

while True:
    chunk = signal_source.read_chunk()
    if chunk is None:
        break
    power, debug = goertzel.process(chunk)
    powers = np.append(powers, power)

fig = plt.figure()
# First plot
plt.plot(t, powers)
annotations.draw(fig.axes[0], Fs=opts.signal.Fs)
plt.title("Goertzel")
plt.ylabel("Magnitude")
plt.xlabel("Index")

plt.show()
