import queue
import threading
import time
from typing import Literal

from loguru import logger
import msgspec
import serial

from rtty_sdr.comms.messages import Send, Sent, Settings, Shutdown
from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.controller.espcom import ToESP
from rtty_sdr.core.options import SystemOpts

type ControllerCommand = Literal["stop", "refresh"]


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
        self.__port_change()

    def __port_change(self):
        if self.__opts.port == self.__esp.port:
            return
        if self.__opts.port == "" and self.__esp.port is None:
            return

        if self.__esp.is_open:
            self.__esp.close()

        self.__esp.port = self.__opts.port
        try:
            self.__esp.open()
            time.sleep(0.05)
            self.__esp.reset_input_buffer()
            time.sleep(0.2)
        except serial.SerialException:
            logger.warning(f"Invalid port {self.__opts.port}, not opening")
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
        try:
            while True:
                if self.__esp.is_open:
                    try:
                        cmd = self.__commands_queue.get_nowait()
                    except queue.Empty:
                        cmd = None
                else:
                    cmd = self.__commands_queue.get()

                if cmd is not None:
                    if cmd == "refresh":
                        self.__port_change()
                        self.__commands_queue.task_done()
                        logger.debug(
                            f"Refreshed esp, it is now {'open' if self.__esp.is_open else 'closed'}"
                        )
                    else:
                        self.__commands_queue.task_done()
                        # Stop
                        break

                if not self.__esp.is_open:
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
                    self.__esp.close()
                    needs_send = True
                    continue

                if not raw_line.endswith(b"\n"):
                    logger.warning("ESP timed out")
                    self.__esp.close()
                    needs_send = True
                    continue

                topic, _, content = raw_line.partition(b":")
                topic_str = topic.decode(errors="ignore").strip()
                content_str = content.decode(errors="ignore").strip()
                match topic_str:
                    case "DEBUG":
                        logger.debug(f"From ESP {content_str}")
                    case "TRACE":
                        logger.trace(f"From ESP {content_str}")
                    case "ERROR":
                        logger.error(f"FROM ESP {content_str}")
                    case "BEAT":
                        pass
                    case "DONE":
                        self.__pubsub.publish(Sent())
                        current_msg = None
                        self.__msgqueue.task_done()
        finally:
            if self.__esp.is_open:
                self.__esp.close()
            logger.info("Controller thread exiting")
