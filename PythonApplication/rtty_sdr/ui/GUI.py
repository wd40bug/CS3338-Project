import asyncio
from datetime import datetime
from typing import Literal, cast
from typing import Deque, Final, Optional
from loguru import logger
import collections
from nicegui import ui, app
from nicegui.elements.chat_message import ChatMessage

from rtty_sdr.comms.messages import (
    FinalMessage,
    LostSignal,
    Receiving,
    Send,
    Shutdown,
    SendInternal,
    Sent,
)
from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.core.protocol import ProtocolMessage, RecvMessage, SendMessage
from rtty_sdr.ui.settings import SettingsMenu


class RttyWebGUI:
    def __init__(
        self,
        initial_settings: SystemOpts,
    ) -> None:
        self.__pubsub: Final[PubSub] = PubSub(module_name="WebUI")
        self.__is_shutting_down: bool = False

        self.__loop: asyncio.AbstractEventLoop | None = None

        self.__pending_send_spinners: Final[Deque[ui.spinner]] = collections.deque()
        self.__active_recv_indicator: ui.row | None = None

        # UI Elements
        self.__message_container: ui.column | None = None
        self.__input: ui.input | None = None
        self.__settings: SettingsMenu = SettingsMenu(initial_settings, self.__pubsub)

        # Bind PubSub events
        self.__pubsub.subscribe(Receiving, self.__on_receiving)
        self.__pubsub.subscribe(LostSignal, self.__on_signal_lost)
        self.__pubsub.subscribe(FinalMessage, self.__on_receive)
        self.__pubsub.subscribe(Shutdown, self.__on_shutdown)
        self.__pubsub.subscribe(Sent, self.__on_sent)

        # Build the UI
        self.__setup_ui()

        ui.context.client.on_connect(self.__on_mount)
        app.on_shutdown(self.__app_shutdown)

    def __setup_ui(self) -> None:
        # Header
        with ui.header(elevated=True).classes(
            "items-center justify-between bg-blue-grey-900"
        ):
            ui.label("RTTY SDR Chat").classes("text-h6 text-white font-bold")
            with ui.row():
                ui.button(
                    "Settings", icon="settings", on_click=self.__open_settings
                ).props("flat color=white")
                ui.button(
                    "Quit", icon="power_settings_new", on_click=self.__action_quit
                ).props("flat color=red")

        with ui.column().classes(
            "w-full max-w-5xl mx-auto h-[calc(100vh-80px)] p-4 no-wrap"
        ):
            self.__message_container = ui.column().classes(
                "w-full flex-grow overflow-y-auto bg-gray-100 p-4 rounded-lg border shadow-inner items-stretch"
            )

            with ui.row().classes("w-full items-center mt-4 no-wrap gap-2"):
                self.__input = (
                    ui.input(placeholder="Type message to transmit (Enter to send)...")
                    .classes("flex-grow")
                    .props("outlined rounded")
                    .on("keydown.enter", self.__send_message)
                )
                ui.button(icon="send", on_click=self.__send_message).classes(
                    "h-14 w-14 rounded-full"
                )

    async def __on_mount(self) -> None:
        logger.debug("Web TUI mounted")
        self.__pubsub.run_receive()
        self.__loop = asyncio.get_event_loop()

    def __on_receiving(self, _: Receiving) -> None:
        if self.__loop:
            self.__loop.call_soon_threadsafe(self.__render_receiving_indicator)

    def __render_receiving_indicator(self):
        if self.__message_container is None:
            return

        if self.__active_recv_indicator is not None:
            return

        with self.__message_container:
            self.__active_recv_indicator = ui.row().classes(
                "w-full items-center no-wrap text-gray-500"
            )
            with self.__active_recv_indicator:
                ui.spinner("radio", size="sm", color="green").classes("mr-2")
                ui.label("Incoming transmission...")

        self.__scroll_chat()

    def __on_signal_lost(self, _: LostSignal):
        if self.__loop:
            self.__loop.call_soon_threadsafe(self.__remove_receiving_spinner)

    def __remove_receiving_spinner(self):
        if self.__active_recv_indicator:
            self.__active_recv_indicator.delete()
            self.__active_recv_indicator = None

    def __on_receive(self, msg: FinalMessage) -> None:
        assert self.__loop is not None
        self.__loop.call_soon_threadsafe(self.__render_received_message, msg.msg)

    def __render_received_message(self, message: RecvMessage) -> None:
        if self.__message_container is None:
            return
        with self.__message_container:
            self.__remove_receiving_spinner()

            stamp = datetime.now()
            ui.chat_message(
                message.msg,
                name=message.callsign,
                sent=False,
                text_html=False,
                stamp=stamp.strftime("%Y-%m-%d %H:%M:%S"),
            ).on(
                "click",
                lambda e: self.__on_msg_clicked(
                    cast(ChatMessage, e.sender), message, stamp
                ),
            )
        self.__scroll_chat()

    def __on_msg_clicked(self, _: ChatMessage, meta: ProtocolMessage, stamp: datetime):
        sent = isinstance(meta, SendMessage)
        act = "Sent" if sent else "Received"
        logger.info("MSG CLICKED")
        with (
            ui.dialog() as dialog,
            ui.card().classes(f"min-w-[400px] {"bg-green-500" if not sent else ""}"),
        ):
            ui.label(f"{act} Message Details").classes("text-h5")
            ui.label(f"{act} on {stamp.strftime('%m/%d/%Y %I:%M%p')}")
            if sent:
                ui.label(f"Intended: {meta.original_codes}")
                ui.label(f"Sent: {meta.codes}")
            else:
                assert isinstance(meta, RecvMessage)
                ui.label(f"Received: {meta.received_codes if meta.received_codes is not None else meta.codes}")
                ui.label(f"Corrected: {meta.codes}")
                if meta.valid_checksum:
                    ui.label(f"Checksum Passed!")
                else:
                    ui.label(
                        f"Invalid Checksum! Calculated: {meta.calculated_checksum:04X} Found: {meta.checksum}"
                    )
            ui.label(f"Codes: {meta.codes}")
            dialog.open()

    def __on_sent(self, _: Sent) -> None:
        if self.__loop:
            self.__loop.call_soon_threadsafe(self.__resolve_sent_spinner)

    def __resolve_sent_spinner(self) -> None:
        if self.__pending_send_spinners:
            spinner = self.__pending_send_spinners.popleft()
            spinner.set_visibility(False)

    def __send_message(self) -> None:
        if not self.__input or not self.__input.value:
            return

        text_val: Final[str] = self.__input.value

        msg: Final[SendMessage] = SendMessage.create(
            text_val,
            self.__settings.opts.callsign,
            self.__settings.opts.baudot,
            self.__settings.opts.corruption
        )

        if self.__message_container:
            with (
                self.__message_container,
                ui.row().classes("w-full justify-end items-center no-wrap gap-2"),
            ):
                spinner = ui.spinner("radio", size="sm")
                self.__pending_send_spinners.append(spinner)
                stamp = datetime.now()
                ui.chat_message(
                    msg.msg,
                    name="YOU",
                    sent=True,
                    text_html=False,
                    stamp=stamp.strftime("%Y-%m-%d %H:%M:%S"),
                ).on(
                    "click",
                    lambda e: self.__on_msg_clicked(cast(ChatMessage, e), msg, stamp),
                )

        self.__scroll_chat()

        if self.__settings.opts.source == "microphone":
            self.__pubsub.publish(Send(msg))
        else:
            self.__pubsub.publish(SendInternal.create_with_msg(msg, self.__settings.opts.signal))
            spinner = self.__pending_send_spinners.pop()
            spinner.set_visibility(False)

        self.__input.value = ""

    def __scroll_chat(self) -> None:
        if self.__message_container:
            with self.__message_container:
                ui.run_javascript(
                    f"document.getElementById('c{self.__message_container.id}').scrollTop = "
                    f"document.getElementById('c{self.__message_container.id}').scrollHeight"
                )

    def __open_settings(self) -> None:
        self.__settings.render()

    def __action_quit(self) -> None:
        logger.info("User requested exit from Web UI. System shutdown broadcasted.")
        ui.run_javascript("window.close()")
        app.shutdown()

    def __app_shutdown(self) -> None:
        self.__is_shutting_down = True
        self.__pubsub.publish(Shutdown())

    def __on_shutdown(self, _: Shutdown) -> Optional[Literal["stop"]]:
        if not self.__is_shutting_down:
            logger.error("Received external shutdown signal, closing UI")
            self.__is_shutting_down = True
            assert self.__loop is not None
            self.__loop.call_soon_threadsafe(app.shutdown)
        return "stop"
