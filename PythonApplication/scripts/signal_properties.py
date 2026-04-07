import matplotlib.pyplot as plt
import scipy.signal as sig
import numpy as np

from rtty_sdr.core.options import SystemOpts
from rtty_sdr.debug.internal_signal import internal_signal
from rtty_sdr.core.baudot import BaudotEncoder


opts = SystemOpts.default(mark=50, shift=50, baud=10)
Fs = opts.signal.Fs

rtty = opts.rtty
message = "HI"

encoder = BaudotEncoder()

encoded = encoder.encode(message)

signal, t, annotations = internal_signal(encoded, opts.signal, 0.1)

fig = plt.figure()
plt.plot(t, signal)
plt.title(f"Time domain view of RTTY signal ({opts.rtty})")
plt.xlabel("Time (s)")
plt.ylabel("Value")
plt.ylim((-1.0, 1.4))
annotations.draw(fig.get_axes()[0], Fs=Fs)


num_per_segment = 256
num_overlap = 220
nfft = 512
beta = 5

# Create the Kaiser window
window = sig.windows.kaiser(num_per_segment, beta) # pyright: ignore [reportAttributeAccessIssue]

# Compute the STFT
STFT = sig.ShortTimeFFT(
    window, hop=(num_per_segment - num_overlap), fs=Fs, mfft=nfft, scale_to="magnitude"
)

Zxx = np.abs(STFT.stft(signal))
f = STFT.f
t = STFT.t(len(signal))

fig = plt.figure()
plt.imshow(Zxx, origin='lower', aspect='auto', 
           extent=STFT.extent(len(signal)), cmap='viridis')

plt.colorbar(label='Magnitude')
plt.title("STFT")
plt.ylabel('Frequency (Hz)')
plt.xlabel('Time (s)')
plt.ylim((rtty.mark - rtty.shift, rtty.space + rtty.shift))
annotations.draw(fig.axes[0], Fs=Fs)

plt.show()
