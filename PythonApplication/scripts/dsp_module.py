import time
from rtty_sdr.comms.broker import BrokerModule
from rtty_sdr.comms.messages import DebugMessage, ReceivedMessage, SendInternal, Shutdown
from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.dsp.protocol_decode import ProtocolDebug
from rtty_sdr.debug.debug_socket import DebugSocket
from rtty_sdr.dsp.DSP import DspModule
import matplotlib.pyplot as plt

from rtty_sdr.debug.state_changes import graph_states
from rtty_sdr.debug.squelch import plot_shaded_squelch
import threading

from loguru import logger

import sys

logger.remove(0)
logger.add(sys.stderr, level="TRACE")

msgs = ["HELLO", "WORLD", "!"]
settings = SystemOpts.default(source="internal", engine='goertzel')

broker = BrokerModule()
dsp = DspModule(settings)
debug_socket = DebugSocket()

broker.start()
debug_socket.start()
threading.Thread(target=dsp.run).start()

pubsub = PubSub()

time.sleep(1)
for msg in msgs:
    logger.info(f"Sending message: {msg}")
    pubsub.publish(SendInternal.create(msg, settings))

logger.info("Sent messages")

debug: list[ProtocolDebug] = []
recv_msgs: list[str] = []
num_messages = 0

#NOTE: Publishing from inside callbacks is only safe if thread=False
def on_timeout():
    logger.error(f"Timed out waiting for message: {num_messages + 1}")
    pubsub.publish(Shutdown())
    return "stop"

def on_receive(msg: ReceivedMessage):
    # msg.msg.msg LMAO
    global num_messages
    logger.info(f"Msg '{msg.msg.msg}'")
    recv_msgs.append(msg.msg.msg)
    num_messages += 1
    if num_messages == len(msgs):
        pubsub.publish(Shutdown())
        logger.info(f"Shutting down after receiving all {len(msgs)} messages")

def on_debug(msg: DebugMessage):
    debug.append(msg.debug)
    if msg.is_done:
        pubsub.publish(Shutdown())
        return "stop"

pubsub.set_timeout(1000, on_timeout)
pubsub.subscribe(ReceivedMessage, on_receive)
pubsub.subscribe(DebugMessage, on_debug)

pubsub.run_receive(thread=False)

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

# breakpoint()
