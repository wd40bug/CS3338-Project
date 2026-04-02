import threading

import zmq

from rtty_sdr.comms.broker import DEBUG_SOCKET


class DebugSocket(threading.Thread):
    def __init__(self):
        super().__init__()

    def run(self):
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.setsockopt_string(zmq.SUBSCRIBE, "")
        socket.connect(DEBUG_SOCKET)

        while True:
            topic = socket.recv_string()
            if socket.getsockopt(zmq.RCVMORE):
                _ = socket.recv()
            else:
                payload = None
            
            print(f"[DEBUG] msg sent {topic}")
