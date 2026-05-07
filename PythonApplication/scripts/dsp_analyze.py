from loguru import logger
import queue
import sys
import msgspec
from scipy.io.wavfile import read
import matplotlib.pyplot as plt
import scipy.signal as sig
import numpy as np
from pathlib import Path

from rtty_sdr.core.options import SystemOpts
from rtty_sdr.debug.annotations import line
from rtty_sdr.debug.squelch import plot_shaded_squelch
from rtty_sdr.debug.state_changes import graph_states
from rtty_sdr.dsp.commands import CommandsQueue
from rtty_sdr.dsp.decode import decode_stream
from rtty_sdr.dsp.engines import (
    EnvelopeEngine,
    EnvelopeEngineDebug,
    GoertzelDebug,
    GoertzelEngine,
)
from rtty_sdr.dsp.protocol_decode import ProtocolDebug, StoppedMsg, protocol
from rtty_sdr.dsp.sources import MockSignalSource
from rtty_sdr.dsp.squelch import Squelch

logger.remove()
logger.add(sys.stderr, level="TRACE")

file_name = sys.argv[1]
file_path = Path(file_name)
file_path = file_path.resolve()
logger.info(f"Reading file {file_name}")

Fs, raw_signal = read(file_name)

logger.info(
    f"Read {len(raw_signal)} samples at {Fs} samples/s ({(1 / Fs) * len(raw_signal)}s)"
)

with open(file_path.with_stem(f"settings-{file_path.stem}").with_suffix(".json"), "r") as f:
    decode = msgspec.json.Decoder(type=SystemOpts)
    opts = decode.decode(f.read())

assert Fs == opts.signal.Fs, (
    f"Sampling rates for the settings file do not match: {Fs} for the wav, {opts.signal.Fs} for the settings file"
)

pill_queue = queue.Queue()
source = MockSignalSource(raw_signal, opts.source_chunk_size, None, pill_queue)
squelch = Squelch(opts.squelch)
if opts.engine == "goertzel":
    engine = GoertzelEngine(opts.goertzel)
else:
    engine = EnvelopeEngine(opts.envelope)

decode_generator = decode_stream(
    source, squelch, engine, opts.stream, CommandsQueue(pill_queue)
)

received_messages = []
debugs = []

for received, debug in protocol(decode_generator, opts.baudot, engine.debug_t):
    received_messages.append(received)
    debugs.append(debug)

    if isinstance(received, StoppedMsg):
        logger.info("Finished")

full_debug = ProtocolDebug.combine(debugs, engine.debug_t)
assert np.all(full_debug.decode.signal == raw_signal), (
    f"raw signal doesn't equal decode raw signal"
)

local_t = (1 / Fs) * full_debug.decode.indices

# Short time fourier transform
num_per_segment = 256
num_overlap = 220
nfft = 512
beta = 5

# Create the Kaiser window
window = sig.windows.kaiser(num_per_segment, beta)  # pyright: ignore [reportAttributeAccessIssue]

# STFT object
STFT = sig.ShortTimeFFT(
    window, hop=(num_per_segment - num_overlap), fs=Fs, mfft=nfft, scale_to="magnitude"
)


# STFT for raw signal
fig = plt.figure()

## Calculate for raw signal
Zxx = np.abs(STFT.stft(raw_signal))
f = STFT.f
stft_t = STFT.t(len(raw_signal))

plt.imshow(
    Zxx,
    origin="lower",
    aspect="auto",
    extent=STFT.extent(len(raw_signal)),
    cmap="viridis",
    vmin=0,
    vmax=0.4,
)

plt.colorbar(label="Magnitude")
plt.title(
    f"STFT for raw signal: nfft = {nfft}, nsegment = {num_per_segment}, noverlap = {num_overlap}, kaiser window B = {beta}"
)
plt.ylabel("Frequency (Hz)")
plt.xlabel("Time (s)")
plt.ylim((opts.rtty.mark - opts.rtty.shift, opts.rtty.space + opts.rtty.shift))
# full_debug.decode.annotations.draw(fig.axes[0], Fs=Fs)

# magnitude spectrum for signal
fig = plt.figure()

plt.magnitude_spectrum(raw_signal, Fs=Fs)
plt.title("Magnitude Spectrum for input signal")

# magnitude spectrum after filtering
fig = plt.figure()

plt.magnitude_spectrum(full_debug.decode.filtered, Fs=Fs)
plt.title("Magnitude Spectrum after squelch bandpass")

# Spectrogram after squelch bandpass
fig = plt.figure()

Zxx = np.abs(STFT.stft(full_debug.decode.filtered))
f = STFT.f
stft_t = STFT.t(len(full_debug.decode.filtered))

plt.imshow(
    Zxx,
    origin="lower",
    aspect="auto",
    extent=STFT.extent(len(full_debug.decode.filtered)),
    cmap="viridis",
    vmin=0,
    vmax=0.4,
)

plt.colorbar(label="Magnitude")
plt.title(f"STFT for post-squelch bandpass")
plt.ylabel("Frequency (Hz)")
plt.xlabel("Time (s)")
plt.ylim((opts.rtty.mark - opts.rtty.shift, opts.rtty.space + opts.rtty.shift))

# Squelch graph
fig, axs = plt.subplots(2, 1)
axs[0].plot(local_t, full_debug.decode.squelch_debug.signal_envelope, label="signal")
axs[0].plot(local_t, full_debug.decode.squelch_debug.total_envelope, label="total")
axs[0].plot(local_t, full_debug.decode.squelch_debug.noise_envelope, label="noise")
axs[0].legend()
axs[0].set_title("Envelopes for squelch")
axs[0].set_ylabel("Power")
axs[0].set_xlabel("Time (s)")

axs[1].plot(local_t, 20 * np.log10(full_debug.decode.squelch_debug.snrs))
axs[1].set_title("Calculated SNR")
plot_shaded_squelch(local_t, axs[1], full_debug.decode.squelch)
line(
    axs[1],
    "y",
    [20 * np.log10(opts.squelch.upper_thresh)],
    "Upper Threshold",
    color="r",
)
line(
    axs[1],
    "y",
    [20 * np.log10(opts.squelch.lower_thresh)],
    "Lower Threshold",
    color="r",
)
axs[1].set_ylabel("Power (dB)")
axs[1].set_xlabel("Time (s)")
axs[1].legend()

# Envelope graph
fig, axs = plt.subplots(4, 1)
axs[0].plot(local_t, full_debug.decode.filtered)
axs[0].set_title("Filtered Signal")
axs[0].set_xlabel("Time (s)")
axs[0].set_ylabel("Value")

axs[1].magnitude_spectrum(
    full_debug.decode.squelch_debug.signal_envelope_debug.squared, Fs=Fs, scale="dB"
)
axs[1].set_title("Squared Magnitude Spectrum")

axs[2].magnitude_spectrum(full_debug.decode.squelch_debug.signal_envelope, Fs=Fs, scale="dB")
axs[2].set_title("Envelope magnitude spectrum")

axs[3].plot(local_t, full_debug.decode.squelch_debug.signal_envelope)
axs[3].set_title("Resulting Envelope")

# Engine
if opts.engine == "goertzel":
    assert isinstance(full_debug.decode.engine_debug, GoertzelDebug)
    fig, axs = plt.subplots(3, 1)
    axs[0].plot(local_t, full_debug.decode.engine_debug.mark_power)
    axs[0].set_title("Mark Power")
    axs[0].set_ylabel("Power")
    axs[0].set_xlabel("Time (s)")

    axs[1].plot(local_t, full_debug.decode.engine_debug.space_power)
    axs[1].set_title("Space Power")
    axs[1].set_ylabel("Power")
    axs[1].set_xlabel("Time (s)")

    axs[2].plot(local_t, full_debug.decode.envelope)
    axs[2].set_title("Total Power (Mark - Space)")
    axs[2].set_ylabel("Power")
    axs[2].set_xlabel("Time (s)")
else:
    assert isinstance(full_debug.decode.engine_debug, EnvelopeEngineDebug)
    fig, axs = plt.subplots(2, 1)

    Zxx = np.abs(STFT.stft(full_debug.decode.engine_debug.mark_filtered))
    f = STFT.f
    stft_t = STFT.t(len(full_debug.decode.engine_debug.mark_filtered))
    im = axs[0].imshow(
        Zxx,
        origin="lower",
        aspect="auto",
        extent=STFT.extent(len(full_debug.decode.engine_debug.mark_filtered)),
        cmap="viridis",
        vmin=0,
        vmax=0.4,
    )

    fig.colorbar(im, label="Magnitude", ax=axs[0])
    axs[0].set_title(f"STFT for filtered Mark")
    axs[0].set_ylabel("Frequency (Hz)")
    axs[0].set_xlabel("Time (s)")
    axs[0].set_ylim(
        (opts.rtty.mark - opts.rtty.shift, opts.rtty.space + opts.rtty.shift)
    )

    Zxx = np.abs(STFT.stft(full_debug.decode.engine_debug.space_filtered))
    f = STFT.f
    stft_t = STFT.t(len(full_debug.decode.engine_debug.space_filtered))
    im = axs[1].imshow(
        Zxx,
        origin="lower",
        aspect="auto",
        extent=STFT.extent(len(full_debug.decode.engine_debug.space_filtered)),
        cmap="viridis",
        vmin=0,
        vmax=0.4,
    )

    fig.colorbar(im, label="Magnitude", ax=axs[1])
    axs[1].set_title(f"STFT for filtered Space")
    axs[1].set_ylabel("Frequency (Hz)")
    axs[1].set_xlabel("Time (s)")
    axs[1].set_ylim(
        (opts.rtty.mark - opts.rtty.shift, opts.rtty.space + opts.rtty.shift)
    )

    fig, axs = plt.subplots(3, 1)
    axs[0].plot(local_t, full_debug.decode.engine_debug.mark_env)
    axs[0].set_title("Mark Envelope")
    axs[0].set_xlabel("Time (s)")
    axs[0].set_ylabel("Value")

    axs[1].plot(local_t, full_debug.decode.engine_debug.space_env)
    axs[1].set_title("Space Envelope")
    axs[1].set_xlabel("Time (s)")
    axs[1].set_ylabel("Value")
    
    axs[2].plot(local_t, full_debug.decode.envelope)
    axs[2].set_title("Difference Envelope (Mark - Space)")
    axs[2].set_xlabel("Time (s)")
    axs[2].set_ylabel("Value")

# Envelope Graphs

fig, axs = plt.subplots(3, 1)
axs[0].plot(local_t, full_debug.decode.envelope)
axs[0].set_title("Envelope with annotations")
full_debug.decode.annotations.draw(axs[0], Fs=opts.signal.Fs)

axs[1].plot(local_t, full_debug.decode.envelope)
axs[1].set_title("With ProtocolState")
graph_states(local_t, axs[1], full_debug.states)
axs[1].legend(bbox_to_anchor=(1.00, 0.5), loc="center left", borderaxespad=0.0)

axs[2].plot(local_t, full_debug.decode.envelope)
axs[2].set_title("With Squelch")
plot_shaded_squelch(local_t, fig.axes[2], full_debug.decode.squelch)
axs[2].legend(bbox_to_anchor=(1.00, 0.5), loc="center left", borderaxespad=0.0)

# Show all
plt.show()
