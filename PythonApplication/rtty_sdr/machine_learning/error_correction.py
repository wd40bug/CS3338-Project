from copy import replace
import multiprocessing
import queue
import threading

from loguru import logger

from rtty_sdr.comms.messages import FinalMessage, ReceivedMessage, Settings, Shutdown
from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.core.baudot import decode
from rtty_sdr.core.options import Shift, SystemOpts
from rtty_sdr.core.protocol import RecvMessage
from rtty_sdr.dsp.protocol_decode import LengthLen


def error_correction(in_codes: list[int], initial_shift: Shift) -> list[int]:
    # TODO: Nathan your stuff goes here
    return in_codes


class ErrorCorrection(multiprocessing.Process):
    def __init__(self, initial_settings: SystemOpts):
        super().__init__()
        self.__opts = initial_settings
        self.__pubsub: PubSub | None = None

    def run(self):
        self.__pubsub = PubSub(module_name="Error Correction")

        msg_queue: queue.Queue[RecvMessage] = queue.Queue()
        stop_event: threading.Event = threading.Event()

        def on_settings_change(msg: Settings):
            self.__opts = msg.settings

        def on_shutdown(_: Shutdown):
            stop_event.set()
            return "stop"

        def on_recv(msg: ReceivedMessage):
            msg_queue.put(msg.msg)

        self.__pubsub.subscribe(Settings, on_settings_change)
        self.__pubsub.subscribe(Shutdown, on_shutdown)
        self.__pubsub.subscribe(ReceivedMessage, on_recv)

        self.__pubsub.run_receive()

        while not stop_event.is_set():
            try:
                # Mostly just extracting the message and writing back the corrected one
                msg = msg_queue.get(timeout=0.1)
                logger.debug(f"Processing message: {msg}")
                if msg.valid_checksum or not self.__opts.error_correction:
                    self.__pubsub.publish(FinalMessage(msg))
                    continue
                msg_codes = msg.codes[
                    msg.msg_start_idx : msg.msg_start_idx + msg.msg_codes_len
                ]
                recovered_codes = error_correction(msg_codes, self.__opts.baudot.initial_shift)
                corrected_codes = msg.codes
                corrected_codes[
                    msg.msg_start_idx : msg.msg_start_idx + msg.msg_codes_len
                ] = recovered_codes
                decode_baudot_opts = replace(self.__opts.baudot, replace_invalid_with="�")
                corrected_msg, _ = decode(recovered_codes, decode_baudot_opts)

                corrected = RecvMessage.create(
                    corrected_msg,
                    msg.callsign,
                    corrected_codes,
                    msg.msg_codes_len,
                    msg.checksum,
                    received_codes=msg.codes
                )
                self.__pubsub.publish(FinalMessage(corrected))
            except queue.Empty:
                continue
        logger.info("Shutting down Error Correction")
