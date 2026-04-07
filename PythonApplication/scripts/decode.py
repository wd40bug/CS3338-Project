from loguru import logger
from rtty_sdr.debug.annotations import DebugAnnotations
from rtty_sdr.debug.squelch import plot_shaded_squelch
from rtty_sdr.debug.state_changes import graph_states
from rtty_sdr.dsp.decode import DecodeState, decode_stream, Code
from rtty_sdr.dsp.engines import EnvelopeEngine, GoertzelEngine
from rtty_sdr.dsp.poisonPill import CommandsQueue, CommandsQueueQueue
from rtty_sdr.dsp.sources import MockSignalSource
from rtty_sdr.core.options import (
    SystemOpts,
)
from rtty_sdr.debug.awgn import awgn
from rtty_sdr.debug.internal_signal import internal_signal
from rtty_sdr.core.baudot import BaudotDecoder, BaudotEncoder

import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt
import queue

from rtty_sdr.dsp.squelch import Squelch

opts = SystemOpts.default()
message = "HI"
encoder = BaudotEncoder()
encoded = encoder.encode(message)
signal, t, annotations = internal_signal(encoded, opts.signal)

signal = awgn(signal, 10)

pill_queue: CommandsQueueQueue = queue.Queue()
signal_source = MockSignalSource(signal, opts.decode, None, pill_queue)
pills = CommandsQueue(pill_queue)
engine = GoertzelEngine(
    opts.goertzel
)
# engine = EnvelopeEngine(EnvelopeOpts(4, decode))

annotations = []
envelope: npt.NDArray[np.float64] = np.array([])
states: list[DecodeState] = []
squelch_vals: npt.NDArray[np.int_] = np.array([])

squelch = Squelch(
    opts.squelch
)
decoder = BaudotDecoder()

for resp, debug in decode_stream(
    signal_source,
    squelch,
    engine,
    opts.stream,
    pills,
):
    if isinstance(resp, Code):
        logger.info(f"Code: {resp.code} -> {decoder.decode(resp.code)}")
    else:
        logger.info(f"Code: {resp}")
    envelope = np.concat((envelope, debug.envelope))
    annotations.append(debug.annotations)
    states.extend(debug.states)
    squelch_vals = np.concat((squelch_vals, debug.squelch))

fig, axs = plt.subplots(3, 1)
axs[0].plot(t[: len(envelope)], envelope)
DebugAnnotations.combine(annotations).draw(axs[0], delay=squelch.delay, Fs=opts.signal.Fs)

axs[1].plot(t[: len(envelope)], envelope)
graph_states(t[: len(envelope)], axs[1], states)
axs[1].legend()

axs[2].plot(t[: len(envelope)], envelope)
plot_shaded_squelch(t[: len(envelope)], axs[2], squelch_vals)
plt.show()
