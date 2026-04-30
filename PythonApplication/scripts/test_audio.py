import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
from rtty_sdr.core.options import SystemOpts

# Initialize options to grab the sample rate
opts = SystemOpts.default(source="microphone", oversampling=2)
sample_rate: int = int(opts.signal.Fs)
duration: int = 10  # seconds to record

print(f"Recording for {duration} seconds...")

# sd.rec replaces the MicrophoneSource wrapper
# Channels is set to 1 (mono), which is standard for SDR/mic input
data: np.ndarray = sd.rec(
    frames=duration * sample_rate, 
    samplerate=sample_rate, 
    channels=1, 
    dtype=np.float32
)

# Block execution until the recording is fully finished
sd.wait()
print("Recording finished.")

print("Playing back...")
sd.play(data, sample_rate)
sd.wait()

# Note: sounddevice records float32 in the range [-1.0, 1.0]. 
# To save as an int16 WAV without distortion, we scale it by 32767 first.
# (If your original wrapper returned raw int16 frames natively, you can just 
# change the dtype above to np.int16 and skip this scaling step).
scaled_data: np.ndarray = (data * 32767).astype(np.int16)

write("out.wav", sample_rate, scaled_data)
print("Saved to out.wav")