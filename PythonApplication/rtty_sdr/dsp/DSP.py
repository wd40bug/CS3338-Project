import multiprocessing
import queue
from rtty_sdr.core.baudot import BaudotDecoder, Shift
from rtty_sdr.dsp.decode import decode_stream
from rtty_sdr.dsp.engines import EnvelopeEngine, GoertzelEngine
from rtty_sdr.dsp.poisonPill import PillQueue, PoisonPill, QueuePoisonPill
import zmq
from typing import Iterator, assert_never

from rtty_sdr.core.protocol import ProtocolDebug, RecvMessage, protocol
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.dsp.squelch import Squelch
from rtty_sdr.broker import BROKER_BACKEND, BROKER_FRONTEND, receive_message_nowait, publish_message
from rtty_sdr.dsp.sources import MicrophoneSource


class DspModule(multiprocessing.Process):
    def __init__(self, default_settings: SystemOpts) -> None:
        super().__init__()
        self.__default_settings = default_settings

        self.topics = {
            "ui.settings": SystemOpts,
            "data.rx.raw": dict,  # Raw signal data
            "system.shutdown": type(None),  # Event with no payload
        }

    def run(self) -> None:
        print("[DSP] Running DSP Process")
        self.__context: zmq.Context = zmq.Context()
        self.__sub_socket: zmq.Socket = self.__context.socket(zmq.SUB)
        self.__sub_socket.connect(BROKER_BACKEND)
        self.__sub_socket.subscribe("ui.settings")
        self.__sub_socket.subscribe("ui.shutdown")
        self.__sub_socket.subscribe("ui.send_internal")

        self.__pub_socket: zmq.Socket = self.__context.socket(zmq.PUB)
        self.__pub_socket.connect(BROKER_FRONTEND)

        # decoder
        baudot_decoder = BaudotDecoder(initial_shift=Shift.FIGS)

        # Poison Pill
        pill_queue: PillQueue = queue.Queue()
        poison_pill = QueuePoisonPill(pill_queue)

        # Pipeline
        def create_pipeline(settings: SystemOpts, poison_pill: PoisonPill) -> Iterator[RecvMessage | ProtocolDebug]:
            source = MicrophoneSource(opts=settings.decode) #TODO: Internal source
            squelch = Squelch(opts=settings.squelch)
            engine = (
                GoertzelEngine(settings.goertzel)
                if settings.engine == "goertzel"
                else EnvelopeEngine(settings.envelope)
            )
            decode = decode_stream(source, squelch, engine, settings.stream, poison_pill)
            protocol_generator = protocol(decode, baudot_decoder)
            return protocol_generator

        pipeline = create_pipeline(self.__default_settings, poison_pill)

        while True:
            # The function blocks, receives, validates, and returns the strict type
            new_settings: SystemOpts | None = None
            while (
                msg := receive_message_nowait(self.__sub_socket)
            ) is not None:
                topic, payload = msg
                # Standard routing logic
                if topic == "ui.settings":
                    assert isinstance(payload, SystemOpts)
                    new_settings = payload
                elif topic == "ui.shutdown":
                    assert payload is None
                    break  # Exit the thread cleanly
                elif topic == "ui.send_internal":
                    #TODO: 
                    raise NotImplementedError("To be implemented")
                    pass
            if new_settings != None:
                pill_queue.put('stop')
                assert isinstance(next(pipeline), ProtocolDebug), "Pipeline was not killed" 
                #TODO: Do something with the ProtocolDebug we get here
                pipeline = create_pipeline(new_settings, poison_pill)

            msg = next(pipeline)
            #TODO: Handle using a static source where this is not unexpected
            assert not isinstance(msg, ProtocolDebug), "Pipeline terminated unexpectedly"
            print("[DSP] Received message")
            publish_message(self.__pub_socket, "dsp.received", msg)            

