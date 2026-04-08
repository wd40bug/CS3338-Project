import time
from rtty_sdr.comms.broker import BrokerModule
from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.comms.topics import TopicsRegistry
from rtty_sdr.core.baudot import encode
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.core.protocol import RecvMessage, SendMessage
from rtty_sdr.dsp.protocol_decode import ProtocolDebug
from rtty_sdr.debug.debug_socket import DebugSocket
from rtty_sdr.dsp.DSP import DspModule
from rtty_sdr.debug.internal_signal import internal_signal, InternalSignalMsg
import matplotlib.pyplot as plt

import numpy as np
import numpy.typing as npt

from rtty_sdr.debug.state_changes import graph_states
from rtty_sdr.debug.squelch import plot_shaded_squelch
import threading

from loguru import logger

import sys

logger.remove(0)
logger.add(sys.stderr, level="TRACE")

msgs = ["HELLO", "WORLD", "!"]
settings = SystemOpts.default(source="internal", engine='goertzel')
registry = TopicsRegistry()
registry.register("ui.send_internal", InternalSignalMsg)
registry.register("system.shutdown", None)
registry.register("ui.settings", SystemOpts)

broker = BrokerModule()
dsp = DspModule(settings, registry)
debug_socket = DebugSocket(registry)

broker.start()
debug_socket.start()
threading.Thread(target=dsp.run).start()

pubsub = PubSub(["dsp.received", "dsp.debug", "dsp.done"], registry)

time.sleep(1)
total_signal: list[npt.NDArray[np.float64]] = []
for msg in msgs:
    send_message = SendMessage.create(msg, "KJ5OEH", settings.baudot)
    signal, _, _ = internal_signal(send_message.codes, settings.signal, 0.2)
    total_signal.append(signal)
    logger.trace(f"Signal of len {len(signal)} generated")
    pubsub.publish_message("ui.send_internal", InternalSignalMsg(signal))
logger.info("Sent messages")
signal = np.concatenate(total_signal)

debug: list[ProtocolDebug] = []
recv_msgs: list[str] = []
num_messages = 0
while True:
    recv = pubsub.recv_message_timeout(10_000)
    if recv is None:
        logger.error(f"Timed out waiting for message: {num_messages + 1}")
        pubsub.publish_message("system.shutdown", None)
        continue
    topic, msg = recv
    logger.info(f"Received {topic} msg")
    match topic:
        case "dsp.received":
            assert isinstance(msg, RecvMessage)
            logger.info(f"Msg '{msg.msg}'")
            recv_msgs.append(msg.msg)
            num_messages += 1
            if num_messages == len(msgs):
                pubsub.publish_message("system.shutdown", None)
                logger.info(f"Shutting down after receiving all {len(msgs)} messages")
        case "dsp.debug":
            assert isinstance(msg, ProtocolDebug)
            debug.append(msg)
        case "dsp.done":
            break;
        case _:
            raise RuntimeError(f"Received unsubscribed topic: {topic}")

summed_debug = ProtocolDebug.combine(debug)

fig, axs = plt.subplots(3, 1)
local_t = summed_debug.decode.indices / settings.signal.Fs
logger.debug(f"Shape of envelope is {summed_debug.decode.envelope.shape}")
axs[0].plot(local_t, summed_debug.decode.envelope)
summed_debug.decode.annotations.draw(axs[0], Fs=settings.signal.Fs)

axs[1].plot(local_t, summed_debug.decode.envelope)
axs[1].set_title("With ProtocolState")
graph_states(local_t, axs[1], summed_debug.states)
axs[1].legend(bbox_to_anchor=(1.00, 0.5), loc="center left", borderaxespad=0.0)

axs[2].plot(local_t, summed_debug.decode.envelope)
axs[2].set_title("With Squelch")
plot_shaded_squelch(local_t, fig.axes[2], summed_debug.decode.squelch)
axs[2].legend(bbox_to_anchor=(1.00, 0.5), loc="center left", borderaxespad=0.0)
logger.info(f"Final received messages were: {recv_msgs}")
plt.show()

logger.info("Shutting down")
broker.stop()
sys.exit(0)
