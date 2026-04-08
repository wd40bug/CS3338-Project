import multiprocessing
import queue
import threading

from loguru import logger
from rtty_sdr.comms.topics import TopicsRegistry
from rtty_sdr.core.catch_and_broadcast import catch_and_broadcast
from rtty_sdr.debug.internal_signal import InternalSignalMsg
from rtty_sdr.dsp.decode import decode_stream
from rtty_sdr.dsp.engines import EnvelopeEngine, GoertzelEngine
from rtty_sdr.dsp.commands import (
    CommandsQueueQueue,
    FullStopCommand,
    Commands,
    CommandsQueue,
    RestartCommand,
)
from typing import Iterator, assert_never

from rtty_sdr.dsp.protocol_decode import ProtocolDebug, StoppedMsg, protocol
from rtty_sdr.core.protocol import RecvMessage
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.dsp.squelch import Squelch
from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.dsp.sources import MicrophoneSource, MockSignalSource

import numpy as np
import numpy.typing as npt

class RunDsp(threading.Thread):
    def __init__(
        self,
        initial_settings: SystemOpts,
        commands: Commands,
        static_data_queue: queue.Queue[npt.NDArray[np.float64]],
        registry: TopicsRegistry
    ):
        super().__init__()
        self.__commands = commands
        self.__static_data_queue = static_data_queue
        self.__settings = initial_settings
        self.__registry = registry

    @staticmethod
    def create_pipeline(
        settings: SystemOpts,
        commands: Commands,
        static_data_queue: queue.Queue[npt.NDArray[np.float64]]
    ) -> Iterator[tuple[RecvMessage | StoppedMsg, ProtocolDebug]]:
        source = (
            MicrophoneSource(opts=settings.decode)
            if settings.source == "microphone"
            else MockSignalSource(
                np.array([]), settings.decode, queue=static_data_queue
            )
        )
        squelch = Squelch(opts=settings.squelch)
        engine = (
            GoertzelEngine(settings.goertzel)
            if settings.engine == "goertzel"
            else EnvelopeEngine(settings.envelope)
        )
        decode = decode_stream(source, squelch, engine, settings.stream, commands)
        return protocol(decode, settings.baudot)

    @catch_and_broadcast
    def run(self) -> None:
        pubsub = PubSub([], self.__registry)
        pipeline = self.create_pipeline(
            self.__settings, self.__commands, self.__static_data_queue
        )
        while True:
            item, debug = next(pipeline)
            if isinstance(item, RecvMessage):
                pubsub.publish_message("dsp.received", item)
            pubsub.publish_message('dsp.debug', debug)
            logger.trace(f"Got a signal of len {len(debug.decode.envelope)}")
            if isinstance(item, StoppedMsg):
                match item.cmd.command:
                    case "restart":
                        assert isinstance(item.cmd, RestartCommand)
                        self.__settings = item.cmd.new_settings
                        pipeline = self.create_pipeline(
                            self.__settings, self.__commands, self.__static_data_queue
                        )
                    case "stop":
                        pubsub.publish_message('dsp.done', None)
                        logger.trace("Dsp Runner ending")
                        return
                    case _:
                        assert_never(item.cmd.command)


class DspModule(multiprocessing.Process):
    def __init__(self, default_settings: SystemOpts, registry: TopicsRegistry) -> None:
        super().__init__()
        self.__default_settings = default_settings
        registry.register("dsp.received", RecvMessage)
        registry.register("dsp.receiving", None)
        registry.register("dsp.debug", ProtocolDebug)
        registry.register("dsp.done", None)
        self.__registry = registry

    @catch_and_broadcast
    def run(self) -> None:
        logger.info("Running DSP Process")
        pubsub = PubSub(["ui.send_internal", "system.shutdown", "ui.settings"], self.__registry)

        # Pipeline Communication
        command_queue: CommandsQueueQueue = queue.Queue()
        commands = CommandsQueue(command_queue)
        static_data_queue: queue.Queue[npt.NDArray[np.float64]] = queue.Queue()

        pipeline_thread = RunDsp(self.__default_settings, commands, static_data_queue, self.__registry)
        pipeline_thread.start()

        while True:
            topic, payload = pubsub.recv_message()
            logger.trace(f"Received {topic} msg")
            if topic == "ui.settings":
                assert isinstance(payload, SystemOpts)
                command_queue.put(RestartCommand(new_settings=payload))
            elif topic == "system.shutdown":
                assert payload is None
                command_queue.put(FullStopCommand())
                pipeline_thread.join()
                logger.info("Ending DSP process")
                return
            elif topic == "ui.send_internal":
                assert isinstance(payload, InternalSignalMsg)
                logger.trace(f"signal of len {len(payload.signal)} received")
                static_data_queue.put(payload.signal)
