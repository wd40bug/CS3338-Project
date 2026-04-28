import time
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.dsp.sources import MicrophoneSource
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write

opts = SystemOpts.default(source="microphone")

source = MicrophoneSource(opts.decode)

t0 = time.time()

frames = []

while time.time() - t0 < 10:
    chunk = source.read_chunk()
    if chunk is not None:
        frames.append(chunk)

data = np.concat(frames)
sd.play(data, opts.signal.Fs)
sd.wait()
write("out.wav", opts.signal.Fs, data)
