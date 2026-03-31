from rtty_sdr.debug.annotations import DebugAnnotations
from rtty_sdr.debug.squelch import plot_shaded_squelch
from rtty_sdr.debug.state_changes import graph_states
from rtty_sdr.dsp.decode import DecodeState, decode_stream
from rtty_sdr.dsp.engines import EnvelopeEngine, GoertzelEngine
from rtty_sdr.dsp.sources import MockSignalSource
from rtty_sdr.core.options import (
    DecodeCommon,
    DecodeStreamOpts,
    EnvelopeOpts,
    GoertzelOpts,
    RTTYOpts,
    SignalOpts,
    SquelchOpts,
)
from rtty_sdr.debug.awgn import awgn
from rtty_sdr.debug.internal_signal import internal_signal
from rtty_sdr.core.baudot import BaudotDecoder, BaudotEncoder

import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt

from rtty_sdr.dsp.squelch import Squelch

Fs = 8000
rtty = RTTYOpts(baud=45.45, mark=2125, shift=170, pre_msg_stops=1, post_msg_stops=1)
opts = SignalOpts(Fs, rtty)
message = "HI"
encoder = BaudotEncoder()
encoded = encoder.encode(message)
signal, t, annotations = internal_signal(encoded, opts)

signal = awgn(signal, 10)

decode = DecodeCommon(oversampling=5, signal=opts)

signal_source = MockSignalSource(signal, decode)
engine = GoertzelEngine(GoertzelOpts(0.5, 256, decode))
# engine = EnvelopeEngine(EnvelopeOpts(4, decode))

annotations = []
envelope: npt.NDArray[np.float64] = np.array([])
states: list[DecodeState] = []
squelch_vals: npt.NDArray[np.int_] = np.array([])

squelch = Squelch(SquelchOpts(0.2, 1, decode))
decoder = BaudotDecoder()

for code, debug in decode_stream(
    signal_source,
    squelch,
    engine,
    DecodeStreamOpts(0.25, 2, decode),
):
    if code != "reset" and code != "end":
        print(f"Code: {code} -> {decoder.decode(code)}")
    else:
        print(f"Code: {code}")
    envelope = np.concat((envelope, debug.envelope))
    annotations.append(debug.annotations)
    states.extend(debug.states)
    squelch_vals = np.concat((squelch_vals, debug.squelch))

fig, axs = plt.subplots(3, 1)
axs[0].plot(t[: len(envelope)], envelope)
DebugAnnotations.combine(annotations).draw(axs[0], delay=squelch.delay, Fs=Fs)

axs[1].plot(t[: len(envelope)], envelope)
graph_states(t[: len(envelope)], axs[1], states)
axs[1].legend()

axs[2].plot(t[: len(envelope)], envelope)
plot_shaded_squelch(t[: len(envelope)], axs[2], squelch_vals)
plt.show()
