from rtty_sdr.broker import BROKER_BACKEND, receive_message
import zmq

from rtty_sdr.core.protocol import ProtocolMessage


class MockUI():
    def __init__(self) -> None:
        self.__context = zmq.Context()

    def run(self) -> None:
        self.__sub_socket: zmq.Socket = self.__context.socket(zmq.SUB)
        self.__sub_socket.connect(BROKER_BACKEND)
        self.__sub_socket.subscribe("dsp.received")
        print("[UI] Started in Main Thread. Press Ctrl+C to exit.")
        try:
            while True:
                topic, payload = receive_message(self.__sub_socket)
                match topic:
                    case "dsp.receive":
                        if isinstance(payload, ProtocolMessage):
                            print(f"Received message: {payload.msg}")
                        else:
                            print(f"Received invalid data for dsp.receive")
                    case _:
                        pass
        except KeyboardInterrupt:
            print("\n[UI] Shutting down...")
