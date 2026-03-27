from rtty_sdr.debug.squelch import plot_shaded_squelch
from rtty_sdr.dsp.squelch import Squelch
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

signal = awgn(signal, 5)

chunk_size = opts.nsamp // 5

signal_source = MockSignalSource(signal, chunk_size)
squelch = Squelch(opts, 0.5, 1)

sqs = np.array([])

sig_env = np.array([])
tot_env = np.array([])
noise_env = np.array([])
snrs = np.array([])

while (chunk:=signal_source.read_chunk()) is not None:
    _, sq, debug = squelch.process(chunk)
    sqs = np.append(sqs, sq)

    sig_env = np.append(sig_env, debug.signal_envelope)
    tot_env = np.append(tot_env, debug.total_envelope)
    noise_env = np.append(noise_env, debug.noise_envelope)
    snrs = np.append(snrs, debug.snrs)

fig, axs = plt.subplots(2, 1)
axs[0].plot(t, sig_env, label="signal")
axs[0].plot(t, tot_env, label="total")
axs[0].plot(t, noise_env, label="noise")
axs[0].legend()
axs[0].set_title("Envelopes for squelch")

axs[1].plot(t, snrs)
axs[1].set_title("Calculated SNR")
plot_shaded_squelch(t, axs[1], sqs)
plt.show()
