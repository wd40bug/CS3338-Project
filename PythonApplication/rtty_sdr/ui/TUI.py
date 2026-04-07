from typing import Deque, assert_never, Final
from loguru import logger
import loguru
from rich.text import Text
from rich.align import Align
from textual import work
from textual.app import App, ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Input, RichLog, Static

from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.comms.topics import TopicsRegistry
from rtty_sdr.core.baudot import BaudotEncoder
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.core.protocol import RecvMessage, SendMessage
from rtty_sdr.debug.internal_signal import InternalSignalMsg, internal_signal
import collections

class RttyTerminal(App):
    BINDINGS: Final[list[tuple[str, str, str]]] = [  # type: ignore
        ("ctrl+q", "quit", "Quit")
    ]

    def __init__(
        self,
        registry: TopicsRegistry,
        inital_settings: SystemOpts,
        early_logs: Deque[loguru.Message] | None = None,
    ) -> None:
        super().__init__()

        self.__message_log: RichLog = RichLog(highlight=True, markup=False)
        self.__message_log.can_focus = False
        self.__sys_log: RichLog = RichLog(highlight=True, markup=True)
        self.__sys_log.can_focus = False
        self.__input: Input = Input(
            placeholder="Type message to transmit (Enter to send)..."
        )

        registry.register("ui.send_internal", InternalSignalMsg)
        registry.register("ui.send_message", SendMessage)
        registry.register("system.shutdown", None)
        registry.register("ui.settings", SystemOpts)
        self.__registry = registry
        self.__tx_pubsub = PubSub([], registry)
        self.__settings = inital_settings
        self.__log_handler_id: int | None = None
        self.__is_shutting_down: bool = False
        self.__early_logs: Final[Deque[loguru.Message]] = (
            early_logs if early_logs is not None else collections.deque()
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical():
                yield self.__message_log
                yield self.__input

            yield self.__sys_log
        yield Footer()

    async def on_mount(self) -> None:
        while self.__early_logs:
            message = self.__early_logs.popleft()
            rich_text: Text = Text.from_ansi(message)
            self.__sys_log.write(rich_text)

        self.__log_handler_id = logger.add(
            self.__textual_sink,
            colorize=True,
            enqueue=True,
            level="TRACE"
        )
        logger.debug("TUI mounted")

        self.listen_for_incoming()

    def __textual_sink(self, message: loguru.Message) -> None:
        if self.__is_shutting_down:
            return

        rich_text: Text = Text.from_ansi(message)

        self.call_from_thread(self.__sys_log.write, rich_text)

    @work(exclusive=True, thread=True)
    def listen_for_incoming(self) -> None:
        pubsub = PubSub(
            ["dsp.received", "controller.sent", "system.shutdown", "dsp.receiving"],
            self.__registry,
        )
        while True:
            topic, payload = pubsub.recv_message()
            if topic == "dsp.received":
                assert isinstance(payload, RecvMessage)
                self.call_from_thread(self.process_incoming_message, payload)
            elif topic == "dsp.receiving":
                # TODO: spinner
                pass
            elif topic == "controller.sent":
                # TODO: spinner
                pass
            elif topic == "system.shutdown":
                if not self.__is_shutting_down:
                    logger.error("Received external shutdown signal, Crashing TUI")
                    self.__is_shutting_down = True
                    self.call_from_thread(self.exit, return_code=1)
                return

    def process_incoming_message(self, message: RecvMessage):
        rich_author: Text = Text(message.callsign + ":")
        rich_msg: Text = Text("        " + message.msg, style="dark_orange")
        self.__message_log.write(rich_author)
        self.__message_log.write(rich_msg)

    # Textual magically knows this is the callback
    async def on_input_submitted(self, message: Input.Submitted) -> None:
        if not message.value:
            return

        rich_author = Text("YOU:")
        rich_msg = Text(message.value + "        ", style="bright_cyan")
        aligned_author = Align.right(rich_author)
        aligned_msg = Align.right(rich_msg)
        self.__message_log.write(aligned_author)
        self.__message_log.write(aligned_msg)
        msg = SendMessage.create(
                    message.value,
                    self.__settings.callsign,
                    BaudotEncoder(self.__settings.rtty.initial_shift),
                )
        if self.__settings.source == 'microphone':
            self.__tx_pubsub.publish_message(
                "ui.send_message",
                msg
            )
        else:
            signal, _, _ = internal_signal(msg.codes, self.__settings.signal, 0.2)
            self.__tx_pubsub.publish_message(
                'ui.send_internal',
                InternalSignalMsg(signal)
            )

        self.__input.value = ""

    async def action_quit(self) -> None:
        logger.info("User requested exit. System shutdown broadcasted.")

        self.__is_shutting_down = True
        self.__tx_pubsub.publish_message("system.shutdown", None)
        await super().action_quit()

    async def on_unmount(self) -> None:
        if self.__log_handler_id is not None:
            logger.remove(self.__log_handler_id)
            self.__log_handler_id = None
