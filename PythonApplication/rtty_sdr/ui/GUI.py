import asyncio
from typing import Literal
import collections
from typing import Deque, Final, Any, Optional
from loguru import logger
import loguru
from nicegui import ui, app

# Assuming these imports match your local project structure
from rtty_sdr.comms.messages import ReceivedMessage, Send, Shutdown, SendInternal, Sent
from rtty_sdr.comms.pubsub import PubSub
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.core.protocol import RecvMessage, SendMessage
from rtty_sdr.ui.settings import SettingsMenu


class RttyWebTerminal:
    def __init__(
        self,
        initial_settings: SystemOpts,
    ) -> None:
        self.__pubsub: Final[PubSub] = PubSub(module_name="WebUI")
        self.__is_shutting_down: bool = False

        self.__loop: asyncio.AbstractEventLoop | None = None

        # UI Elements
        self.__message_container: ui.column | None = None
        self.__input: ui.input | None = None
        self.__settings: SettingsMenu = SettingsMenu(initial_settings)

        # Bind PubSub events
        self.__pubsub.subscribe(ReceivedMessage, self.__on_receive)
        self.__pubsub.subscribe(Shutdown, self.__on_shutdown)
        self.__pubsub.subscribe(Sent, self.__on_sent)

        # Build the UI
        self.__setup_ui()

        ui.context.client.on_connect(self.__on_mount)

    def __setup_ui(self) -> None:
        # Header
        with ui.header(elevated=True).classes("items-center justify-between bg-blue-grey-900"):
            ui.label("RTTY SDR Chat").classes("text-h6 text-white font-bold")
            with ui.row():
                ui.button("Settings", icon="settings", on_click=self.__open_settings).props("flat color=white")
                ui.button("Quit", icon="power_settings_new", on_click=self.__action_quit).props("flat color=red")

        # Main Layout: Centered Chat View
        with ui.column().classes("w-full max-w-5xl mx-auto h-[calc(100vh-80px)] p-4 no-wrap"):
            
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
                ui.button(icon="send", on_click=self.__send_message).classes("h-14 w-14 rounded-full")

    async def __on_mount(self) -> None:
        logger.debug("Web TUI mounted")
        self.__pubsub.run_receive()
        self.__loop = asyncio.get_event_loop()

    def __on_receive(self, msg: ReceivedMessage) -> None:
        assert self.__loop is not None
        self.__loop.call_soon_threadsafe(self.__render_received_message, msg.msg)

    def __render_received_message(self, message: RecvMessage) -> None:
        if self.__message_container is None:
            return
        with self.__message_container:
            ui.chat_message(message.msg, name=message.callsign, sent=False, text_html=False)
        self.__scroll_chat()

    def __on_sent(self, _: Sent) -> None:
        # Hook for sent confirmation (e.g., removing a loading spinner)
        pass

    def __send_message(self) -> None:
        if not self.__input or not self.__input.value:
            return

        text_val: Final[str] = self.__input.value

        if self.__message_container:
            with self.__message_container:
                ui.chat_message(text_val, name="YOU", sent=True, text_html=False)
        self.__scroll_chat()

        msg: Final[SendMessage] = SendMessage.create(
            text_val,
            self.__settings.opts.callsign,
            self.__settings.opts.baudot,
        )

        if self.__settings.opts.source == "microphone":
            self.__pubsub.publish(Send(msg))
        else:
            self.__pubsub.publish(SendInternal.create(text_val, self.__settings.opts))

        self.__input.value = ""

    def __scroll_chat(self) -> None:
        if self.__message_container:
            with self.__message_container:
                ui.run_javascript(
                    f"document.getElementById('c{self.__message_container.id}').scrollTop = "
                    f"document.getElementById('c{self.__message_container.id}').scrollHeight"
                )

    def __open_settings(self) -> None:
        # with ui.dialog() as dialog, ui.card().classes("min-w-[400px]"):
        #     ui.label("RTTY Settings").classes("text-h5 font-bold mb-4")
        #     
        #     baud = ui.number("Baud Rate", value=self.__settings.rtty.baud).classes("w-full mb-2")
        #     mark = ui.number("Mark Frequency", value=self.__settings.rtty.mark).classes("w-full mb-2")
        #     shift = ui.number("Shift Frequency", value=self.__settings.rtty.shift).classes("w-full mb-2")
        #     pre_stops = ui.number("Pre-Message Stops", value=self.__settings.rtty.pre_msg_stops).classes("w-full mb-4")
        #
        #     def apply_and_close() -> None:
        #         if baud.value: self.__settings.rtty.baud = baud.value
        #         if mark.value: self.__settings.rtty.mark = int(mark.value)
        #         if shift.value: self.__settings.rtty.shift = int(shift.value)
        #         if pre_stops.value: self.__settings.rtty.pre_msg_stops = int(pre_stops.value)
        #         
        #         logger.info(f"Updated settings: Baud={baud.value}, Mark={mark.value}, Shift={shift.value}")
        #         dialog.close()
        #
        #     with ui.row().classes("w-full justify-end mt-2"):
        #         ui.button("Cancel", on_click=dialog.close).props("flat color=grey")
        #         ui.button("Apply", on_click=apply_and_close).props("color=primary")
        #
        # dialog.open()
        self.__settings.render()

    def __action_quit(self) -> None:
        logger.info("User requested exit from Web UI. System shutdown broadcasted.")
        self.__is_shutting_down = True
        self.__pubsub.publish(Shutdown())
        ui.run_javascript('window.close()')
        app.shutdown()

    def __on_shutdown(self, _: Shutdown) -> Optional[Literal['stop']]:
        if not self.__is_shutting_down:
            logger.error("Received external shutdown signal, closing UI")
            self.__is_shutting_down = True
            assert self.__loop is not None
            self.__loop.call_soon_threadsafe(app.shutdown)
        return "stop"
