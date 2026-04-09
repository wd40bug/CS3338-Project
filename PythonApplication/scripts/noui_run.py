import sys
import threading
import time
from typing import Literal
import multiprocessing as mp

from loguru import logger
from rtty_sdr.comms.broker import BrokerModule
from rtty_sdr.comms.messages import DebugMessage, ReceivedMessage, Send, SendInternal, Settings, Shutdown
from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.controller.controller import ControllerModule
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.core.protocol import SendMessage
from rtty_sdr.debug.debug_socket import DebugSocket
from rtty_sdr.dsp.DSP import DspModule


import matplotlib.pyplot as plt
from rtty_sdr.debug.state_changes import graph_states
from rtty_sdr.debug.squelch import plot_shaded_squelch

logger.remove()
logger.add(sys.stderr, enqueue=True, level="TRACE")

if __name__ == "__main__":
    settings = SystemOpts.default(source="internal", engine="goertzel", pre_msg_stops=4)

    mp.set_start_method("spawn", force=True)

    broker = BrokerModule()
    debug_socket = DebugSocket()
    dsp = DspModule(settings)
    # dsp_thread = threading.Thread(target=dsp.run)
    controller = ControllerModule(settings)

    broker.start()
    time.sleep(0.2)
    debug_socket.start()
    dsp.start()
    controller.start()
    time.sleep(2)

    pubsub = PubSub(module_name="NOUI RUN")

    actions: list[
        tuple[Literal["send"], str] | tuple[Literal["change_settings"], SystemOpts]
    ] = [
        ("send", "Hello World"),
        ("send", "Message 2!")
    ]

    num_msgs = sum(1 for act in actions if act[0] == "send")

    for act in actions:
        if act[0] == "send":
            if settings.source == "internal":
                pubsub.publish(SendInternal.create(act[1], settings))
                logger.info(f"Sending internal msg: {act[1]}")
            else:
                pubsub.publish(Send(SendMessage.create(act[1], settings.callsign, settings.baudot)))
                logger.info(f"Sending msg: {act[1]}")
        else:
            settings = act[1]
            pubsub.publish(Settings(act[1]))
            logger.info(f"Changing settings")

    logger.info("Done with actions, receiving data")

    recv_msgs = []
    def on_timeout():
        logger.error(f"Timed out waiting for message: {len(recv_msgs) + 1}")
        pubsub.publish(Shutdown())
        return "stop"

    def on_receive(msg: ReceivedMessage):
        # msg.msg.msg LMAO
        logger.info(f"Msg '{msg.msg.msg}'")
        recv_msgs.append(msg.msg.msg)
        if len(recv_msgs) == num_msgs:
            pubsub.publish(Shutdown())
            logger.info(f"Shutting down after receiving all {num_msgs} messages")

    def on_debug(msg: DebugMessage):
        if msg.is_done:
            pubsub.publish(Shutdown())
            return "stop"

    pubsub.set_timeout(10000, on_timeout)
    pubsub.subscribe(ReceivedMessage, on_receive)
    pubsub.subscribe(DebugMessage, on_debug)

    pubsub.run_receive(thread=False)

    logger.info(f"Received messages: {recv_msgs}")

    pubsub.publish(Shutdown())
    debug_socket.join()
    dsp.join()
    controller.join()
    broker.stop()
    broker.join()

    summed_debug = debug_socket.collect()

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
    plt.show()

    logger.info("Shutting down")
