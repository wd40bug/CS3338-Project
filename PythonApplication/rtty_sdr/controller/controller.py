import queue
import threading
import time
from typing import Literal
from typing_extensions import Final

from loguru import logger
import msgspec
import serial

from rtty_sdr.comms.messages import Send, Sent, Settings, Shutdown
from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.core.options import RTTYOpts, SystemOpts

type ControllerCommand = Literal["stop", "refresh"]

class ToESP(msgspec.Struct, frozen=True):
    message: list[int]
    options: RTTYOpts

class ControllerModule(threading.Thread):
    def __init__(self, initial_settings: SystemOpts):
        super().__init__()
        self.__pubsub = PubSub(module_name="Controller")
        self.__pubsub.subscribe(Send, self.__on_send_message)
        self.__pubsub.subscribe(Settings, self.__on_settings)
        self.__pubsub.subscribe(Shutdown, self.__on_shutdown)
        self.__msgqueue: queue.Queue[list[int]] = queue.Queue()
        self.__commands_queue: queue.Queue[ControllerCommand] = queue.Queue()
        self.__opts = initial_settings
        self.__esp: serial.Serial = serial.Serial(baudrate=115200, timeout=5)
        self.__encoder = msgspec.json.Encoder()
        self.__attempt_connect()

    def __attempt_connect(self):
        if self.__esp.is_open:
            self.__esp.close()

        if not self.__opts.port or not self.__opts.port.strip():
            return

        self.__esp.port = self.__opts.port
        try:
            self.__esp.open()
            time.sleep(0.05)
            self.__esp.reset_input_buffer()
            time.sleep(0.2)
            logger.info(f"Successfully connected to ESP on {self.__opts.port}")
        except serial.SerialException:
            logger.debug(f"Invalid port {self.__opts.port}, not opening")
            self.__esp.port = None

    def __on_send_message(self, msg: Send):
        self.__msgqueue.put(msg.msg.codes)

    def __on_settings(self, msg: Settings):
        self.__opts = msg.settings
        self.__commands_queue.put("refresh")

    def __on_shutdown(self, _: Shutdown):
        self.__commands_queue.put("stop")
        self.join()
        logger.info("Ending Controller thread")
        return "stop"

    def run(self) -> None:
        self.__pubsub.run_receive()
        current_msg: ToESP | None = None
        needs_send: bool = False

        RECONNECT_INTERVAL: Final[float] = 2.0
        try:
            while True:
                if self.__esp.is_open:
                    try:
                        cmd = self.__commands_queue.get_nowait()
                    except queue.Empty:
                        cmd = None
                else:
                    try:
                        cmd = self.__commands_queue.get(timeout=RECONNECT_INTERVAL)
                    except queue.Empty:
                        cmd = None

                if cmd is not None:
                    if cmd == "refresh":
                        self.__attempt_connect()
                        self.__commands_queue.task_done()
                    else:
                        self.__commands_queue.task_done()
                        # Stop
                        break

                if not self.__esp.is_open:
                    # If no command was grabbed and the port is closed, attempt a reconnect
                    if cmd is None:
                        self.__attempt_connect()
                    continue

                if current_msg is None:
                    try:
                        msg = self.__msgqueue.get_nowait()
                        to_esp = ToESP(msg, self.__opts.rtty)
                        current_msg = to_esp
                        needs_send = True
                    except queue.Empty:
                        pass

                if needs_send and current_msg is not None:
                    try:
                        json = self.__encoder.encode(current_msg)
                        self.__esp.write(json)
                        logger.trace(f"Wrote to ESP: {json}")
                        needs_send = False
                    except serial.SerialException:
                        logger.warning("Serial write failed (device unplugged???)")
                        self.__esp.close()
                        continue

                try:
                    raw_line: bytes = self.__esp.readline()
                except serial.SerialException:
                    logger.warning("Serial read failed (device unplugged???)")
                    needs_send = True
                    self.__esp.close()
                    continue

                if not raw_line.endswith(b"\n"):
                    logger.warning("ESP timed out")
                    self.__esp.close()
                    needs_send = True
                    continue

                line = raw_line.decode(errors="ignore").strip()
                topic, _, content = line.partition(":")
                match topic:
                    case "DEBUG":
                        logger.debug(f"From ESP {content}")
                    case "TRACE":
                        logger.trace(f"From ESP {content}")
                    case "ERROR":
                        logger.error(f"FROM ESP {content}")
                    case "BEAT":
                        pass
                    case "DONE":
                        self.__pubsub.publish(Sent())
                        current_msg = None
                        self.__msgqueue.task_done()
                    case _:
                        logger.trace(f"Unexpected msg from ESP: {line}")
        finally:
            if self.__esp.is_open:
                self.__esp.close()
            logger.info("Controller thread exiting")
