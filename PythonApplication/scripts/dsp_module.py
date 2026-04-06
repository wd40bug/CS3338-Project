import time
from typing import assert_never
from rtty_sdr.comms.broker import BrokerModule
from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.comms.topics import TopicsRegistry
from rtty_sdr.core.baudot import BaudotEncoder
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.core.protocol import ProtocolDebug, RecvMessage, SendMessage
from rtty_sdr.debug.debug_socket import DebugSocket
from rtty_sdr.dsp.DSP import DspModule, RemainderMsg
from rtty_sdr.debug.internal_signal import internal_signal, InternalSignalMsg
import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt

from rtty_sdr.debug.state_changes import graph_states
from rtty_sdr.debug.squelch import plot_shaded_squelch
from threading import Thread

msg = "HELLO!"
settings = SystemOpts.default(source='internal')
registry = TopicsRegistry()
registry.register('ui.send_internal', InternalSignalMsg)
registry.register('ui.shutdown', None)
registry.register('ui.settings', SystemOpts)

broker = BrokerModule()
dsp = DspModule(settings, registry)
debug_socket = DebugSocket()

broker.start()
debug_socket.start()
Thread(target=dsp.run).start()

pubsub = PubSub(["dsp.received", "dsp.debug_remainder"], registry)

encoder = BaudotEncoder(settings.rtty.initial_shift)
send_message = SendMessage.create(msg, "KJ5OEH", encoder)
signal, t, annotations = internal_signal(send_message.codes, settings.signal, 0.2)
print(f"[SCRIPT] signal of len {len(signal)} generated")

time.sleep(1)
pubsub.publish_message("ui.send_internal", InternalSignalMsg(signal))
time.sleep(20)
pubsub.publish_message("ui.shutdown", None)
print("[SCRIPT] Sent messages")

debug: list[ProtocolDebug] = []
while True:
    topic, msg = pubsub.recv_message()
    print(f"[SCRIPT] Received {topic} msg")
    match topic:
        case "dsp.received":
            assert isinstance(msg, RecvMessage)
            debug.append(msg.debug)
            pubsub.publish_message("ui.shutdown", None)
            print(f"Msg '{msg.msg}'")
        case "dsp.debug_remainder":
            assert isinstance(msg, RemainderMsg)
            debug.append(msg.debug)
            if msg.is_done:
                break
        case _:
            raise RuntimeError(f"Received unsubscribed topic: {topic}")

summed_debug = ProtocolDebug.combine(debug)

fig, axs = plt.subplots(3, 1)
local_t = t[: len(summed_debug.decode.envelope)]
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
plt.show()
