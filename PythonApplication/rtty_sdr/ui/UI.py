import time
from rtty_sdr.broker import (
    BROKER_BACKEND,
    BROKER_FRONTEND,
    publish_message,
    receive_message,
)
import zmq

from rtty_sdr.core.baudot import BaudotEncoder, Shift
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.core.protocol import ProtocolMessage, SendMessage
from rtty_sdr.debug import internal_signal
from rtty_sdr.debug.internal_signal import InternalSignalMsg, internal_signal


class MockUI:
    def __init__(self, initial_settings: SystemOpts) -> None:
        self.__context = zmq.Context()
        self.__settings = initial_settings

    def run(self) -> None:
        self.__sub_socket: zmq.Socket = self.__context.socket(zmq.SUB)
        self.__sub_socket.connect(BROKER_BACKEND)
        self.__sub_socket.subscribe("dsp.received")

        self.__pub_socket: zmq.Socket = self.__context.socket(zmq.PUB)
        self.__pub_socket.connect(BROKER_FRONTEND)

        print("[UI] Started in Main Thread. Press Ctrl+C to exit.")
        time.sleep(2)
        msg = "HI"
        encoder = BaudotEncoder(Shift.FIGS)
        protocol_msg = SendMessage.create(msg, "KJ5OEH", encoder)
        _, signal, _ = internal_signal(
            protocol_msg.codes, self.__settings.signal, prepend_silence_s=0
        )
        publish_message(
            self.__pub_socket, "ui.send_internal", InternalSignalMsg(signal)
        )
        print("[UI] Sent ui.send_internal msg")
        try:
            while True:
                topic, payload = receive_message(self.__sub_socket)
                match topic:
                    case "dsp.receive":
                        if isinstance(payload, ProtocolMessage):
                            print(f"Received message: {payload.msg}")
                        else:
                            print("Received invalid data for dsp.receive")
                    case _:
                        pass
        except KeyboardInterrupt:
            print("\n[UI] Shutting down...")
