from typing import Deque, Final
from loguru import logger
import loguru
from rich.text import Text
from rich.align import Align
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Input, RichLog

from rtty_sdr.comms.messages import ReceivedMessage, Send, Shutdown, SendInternal
from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.core.protocol import RecvMessage, SendMessage
import collections

class RttyTerminal(App):
    BINDINGS: Final[list[tuple[str, str, str]]] = [  # type: ignore
        ("ctrl+q", "quit", "Quit")
    ]

    def __init__(
        self,
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

        self.__pubsub = PubSub(module_name="TUI")
        self.__pubsub.subscribe(ReceivedMessage, self.on_receive)
        self.__pubsub.subscribe(Shutdown, self.on_shutdown)

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
        self.__pubsub.run_receive()

    def __textual_sink(self, message: loguru.Message) -> None:
        if self.__is_shutting_down:
            return

        rich_text: Text = Text.from_ansi(message)

        self.call_from_thread(self.__sys_log.write, rich_text)

    def on_receive(self, msg: ReceivedMessage):
        self.call_from_thread(self.process_incoming_message, msg.msg)

    def on_shutdown(self, _: Shutdown):
        if not self.__is_shutting_down:
            logger.error("Received external shutdown signal, Crashing TUI")
            self.__is_shutting_down = True
            self.call_from_thread(self.exit, return_code=1)
        return "stop"

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
                    self.__settings.baudot,
                )
        if self.__settings.source == 'microphone':
            self.__pubsub.publish(
                Send(msg)
            )
        else:
            self.__pubsub.publish(
                SendInternal.create(message.value, self.__settings)
            )

        self.__input.value = ""

    async def action_quit(self) -> None:
        logger.info("User requested exit. System shutdown broadcasted.")

        self.__is_shutting_down = True
        self.__pubsub.publish(Shutdown())
        await super().action_quit()

    async def on_unmount(self) -> None:
        if self.__log_handler_id is not None:
            logger.remove(self.__log_handler_id)
            self.__log_handler_id = None
