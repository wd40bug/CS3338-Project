import multiprocessing
import queue

from loguru import logger
from rtty_sdr.comms.messages import (
    DebugMessage,
    ReceivedMessage,
    SendInternal,
    Settings,
    Shutdown,
)
from rtty_sdr.core.catch_and_broadcast import catch_and_broadcast
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


class DspModule(multiprocessing.Process):
    def __init__(self, default_settings: SystemOpts) -> None:
        super().__init__()
        self.__default_settings = default_settings

    @staticmethod
    def __create_pipeline(
        settings: SystemOpts,
        commands_queue: CommandsQueueQueue,
        static_data_queue: queue.Queue[npt.NDArray[np.float64]],
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
        commands = CommandsQueue(commands_queue)
        decode = decode_stream(source, squelch, engine, settings.stream, commands)
        return protocol(decode, settings.baudot)

    @catch_and_broadcast
    def run(self) -> None:
        pubsub = PubSub(module_name="DSP")

        command_queue: CommandsQueueQueue = queue.Queue()
        static_data_queue: queue.Queue[npt.NDArray[np.float64]] = queue.Queue()

        def on_send_internal(msg: SendInternal):
            logger.trace(f"signal of len {len(msg.signal)} received")
            static_data_queue.put(msg.signal)

        def on_shutdown(_: Shutdown):
            command_queue.put(FullStopCommand())
            logger.info("Ending DSP process")
            return "stop"

        def on_settings_change(msg: Settings):
            command_queue.put(RestartCommand(new_settings=msg.settings))

        pubsub.subscribe(SendInternal, on_send_internal)
        pubsub.subscribe(Shutdown, on_shutdown)
        pubsub.subscribe(Settings, on_settings_change)

        # Spin up callback thread
        pubsub.run_receive()

        # Create pipeline
        pipeline = self.__create_pipeline(
            self.__default_settings, command_queue, static_data_queue
        )

        while True:
            item, debug = next(pipeline)
            if isinstance(item, RecvMessage):
                pubsub.publish(ReceivedMessage(item))
                pubsub.publish(DebugMessage(debug, is_done=False))
                logger.trace(
                    f"Received msg {item.msg} with signal len {len(debug.decode.signal)}"
                )
            elif isinstance(item, StoppedMsg):
                logger.trace(
                    f"Received command: {item.cmd.command} with signal len {len(debug.decode.signal)}"
                )
                match item.cmd.command:
                    case "restart":
                        assert isinstance(item.cmd, RestartCommand)
                        self.__settings = item.cmd.new_settings
                        pipeline = self.__create_pipeline(
                            self.__settings,
                            command_queue,
                            static_data_queue,
                        )
                        pubsub.publish(DebugMessage(debug, is_done=False))
                    case "stop":
                        pubsub.publish(DebugMessage(debug, is_done=True))
                        logger.trace("Dsp Runner ending")
                        return
                    case _:
                        assert_never(item.cmd.command)
