import threading
from loguru import logger
import sys
import queue
import matplotlib.pyplot as plt
import msgspec
from scipy.io.wavfile import write

from rtty_sdr.core.options import SystemOpts
from rtty_sdr.core.protocol import RecvMessage
from rtty_sdr.debug.squelch import plot_shaded_squelch
from rtty_sdr.debug.state_changes import graph_states
from rtty_sdr.dsp.commands import CommandsQueue, CommandsQueueQueue, FullStopCommand
from rtty_sdr.dsp.decode import decode_stream
from rtty_sdr.dsp.engines import EnvelopeEngine, GoertzelEngine
from rtty_sdr.dsp.protocol_decode import ProtocolDebug, StoppedMsg, protocol
from rtty_sdr.dsp.sources import MicrophoneSource
from rtty_sdr.dsp.squelch import Squelch

logger.remove()
logger.add(sys.stderr, level="TRACE")

opts = SystemOpts.default(
    source="microphone", engine="goertzel", bw_safety_margin=1, squelch_envelope_margin=0.5
)

source = MicrophoneSource(opts.decode, opts.source_chunk_size)
squelch = Squelch(opts.squelch)
if opts.engine == "goertzel":
    engine = GoertzelEngine(opts.goertzel)
else:
    engine = EnvelopeEngine(opts.envelope)
pill_queue: CommandsQueueQueue = queue.Queue()
generator = decode_stream(
    source, squelch, engine, opts.stream, CommandsQueue(pill_queue)
)

t = threading.Timer(30, lambda: pill_queue.put(FullStopCommand()))
ms = threading.Timer(1, lambda: logger.info("Start sending now"))

file_name = input("What file name should I use? ")
num_messages = int(input("How many messages are you expecting? "))
input("Press enter to begin...")

t.start()
ms.start()

received_msgs: list[RecvMessage | StoppedMsg] = []
debugs: list[ProtocolDebug] = []
for received, debug in protocol(generator, opts.baudot, engine.debug_t):
    received_msgs.append(received)
    debugs.append(debug)
    if len(received_msgs) == num_messages:
        pill_queue.put(FullStopCommand())

    if isinstance(received, RecvMessage):
        logger.info(f"Received message: {received.msg}")
    elif isinstance(received, StoppedMsg):
        logger.info("Stopping")
    t.cancel()
    t = threading.Timer(5, lambda: pill_queue.put(FullStopCommand()))
    t.start()

logger.info(
    f"Received: {[msg.msg for msg in received_msgs if isinstance(msg, RecvMessage)]}"
)
full_debug = ProtocolDebug.combine(debugs, engine.debug_t)

write(file_name + ".wav", opts.signal.Fs, full_debug.decode.signal)
with open(f"settings-{file_name}.json", "wb") as f:
    f.write(msgspec.json.encode(opts))

for received, debug in zip(received_msgs, debugs):
    fig, axs = plt.subplots(3, 1)
    local_t = debug.decode.indices / opts.signal.Fs
    axs[0].plot(local_t, debug.decode.envelope)
    if isinstance(received, RecvMessage):
        axs[0].set_title(f"RTTY Message '{received.msg}' with annotations")
    else:
        axs[0].set_title(f"Incomplete RTTY Message with annotations")
    debug.decode.annotations.draw(axs[0], Fs=opts.signal.Fs)

    axs[1].plot(local_t, debug.decode.envelope)
    axs[1].set_title("With ProtocolState")
    graph_states(local_t, axs[1], debug.states)
    axs[1].legend(bbox_to_anchor=(1.00, 0.5), loc="center left", borderaxespad=0.0)

    axs[2].plot(local_t, debug.decode.envelope)
    axs[2].set_title("With Squelch")
    plot_shaded_squelch(local_t, fig.axes[2], debug.decode.squelch)
    axs[2].legend(bbox_to_anchor=(1.00, 0.5), loc="center left", borderaxespad=0.0)
    plt.show()
