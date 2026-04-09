from datetime import datetime
from nicegui import ui
from rtty_sdr.core.options import RTTYOpts
import copy

messages: list[tuple[str, str, bool]] = []
msg_received = False
err_correction = True
corrupt_msg = False
curopts = RTTYOpts(baud=45.45, mark=2125, shift=170, pre_msg_stops=40)
optsarr: list[RTTYOpts] = []
sentarr: list[str] = []
recvarr: list[str] = []

#def handle_msg_rcv(received: ??):
#    display_txt(txt)

#def send_msg(txt: str) -> None:
#   send text and curopts

@ui.page('/')
async def main() -> None:
    
    with ui.dialog() as dialog, ui.card().classes('w-150 h-250'):
        with ui.row().classes('w-full justify-end'):
            ui.button(icon = 'close', on_click = dialog.close, color = 'black').props('flat').set_background_color('white')

    def sentmsg_popup(txt: str) -> None:
        with dialog.clear(), ui.card().classes('w-100 h-100'):
            with ui.row().classes('w-full'):
                ui.label('Sent Message Details').style('font-size: 2em')
                ui.space()
                ui.button(icon = 'close', on_click = dialog.close, color = 'black').props('flat').set_background_color('white')
            with ui.row():
                ui.label(f'Sent Message: {txt.upper()}')
            with ui.row():
                ui.label('Corrupted Message: N/A')
            with ui.row():
                ui.label(f'Baud Rate: {optsarr[sentarr.index(txt)].baud}')
            with ui.row():
                ui.label(f'Mark Frequency: {optsarr[sentarr.index(txt)].mark}')
            with ui.row():
                ui.label(f'Shift Frequency: {optsarr[sentarr.index(txt)].shift}')
            with ui.row():
                ui.label(f'Pre-Message Stops: {optsarr[sentarr.index(txt)].pre_msg_stops}')
            dialog.open()

    def rcvdmsg_popup() -> None:
        with dialog.clear(), ui.card().classes('w-100 h-100'):
            with ui.row().classes('w-full'):
                ui.label('Sent Message Details').style('font-size: 2em')
                ui.space()
                ui.button(icon = 'close', on_click = dialog.close, color = 'black').props('flat').set_background_color('white')
            with ui.row():
                ui.label('Sent Message: ')
            with ui.row():
                ui.label('Corrupted Message: ')
            with ui.row():
                ui.label('Baud Rate: ')
            with ui.row():
                ui.label('Mark Frequency: ')
            with ui.row():
                ui.label('Shift Frequency: ')
            with ui.row():
                ui.label('Pre-Message Stops: ')
            dialog.open()

    

    def settings_popup():
        global curopts

        def toggle_err() -> None:
            global err_correction
            err_correction = not err_correction

        def toggle_corrupt() -> None:
            global corrupt_msg
            corrupt_msg = not corrupt_msg
        
        def update_baud(num: float) -> None:
            global curopts
            curopts.baud = num
            baudin.value = ''
            baudin.props(f'placeholder={curopts.baud}')
            baudin.update()
        
        def update_mark(num: float) -> None:
            global curopts
            curopts.mark = num
            markin.value = ''
            markin.props(f'placeholder={curopts.mark}')
            markin.update()

        def update_shift(num: float) -> None:
            global curopts
            curopts.shift = num
            shiftin.value = ''
            shiftin.props(f'placeholder={curopts.shift}')
            shiftin.update()

        def update_pre_stop(num: int) -> None:
            global curopts
            curopts.pre_msg_stops = num
            prestopin.value = ''
            prestopin.props(f'placeholder={curopts.pre_msg_stops}')
            prestopin.update()
        
        with dialog.clear(), ui.card().classes('w-100 h-120'):
            with ui.row().classes('w-full'):
                ui.label('Options').style('font-size: 2em')
                ui.space()
                ui.button(icon = 'close', on_click = dialog.close, color = 'black').props('flat').set_background_color('white')
            with ui.row():
                ui.label('Error Correction: ')
                ui.checkbox(value = True, on_change = lambda: toggle_err())
            with ui.row():
                ui.label('Corrupt Message: ')
                ui.checkbox(on_change = lambda: toggle_corrupt())
            with ui.row():
                ui.label('Baud Rate: ')
                baudin = ui.input(placeholder = f'{curopts.baud}').on('keydown.enter', lambda: update_baud(float(baudin.value)))
            with ui.row():
                ui.label('Mark Frequency: ')
                markin = ui.input(placeholder = f'{curopts.mark}').on('keydown.enter', lambda: update_mark(float(markin.value)))
            with ui.row():
                ui.label('Shift Frequency: ')
                shiftin = ui.input(placeholder = f'{curopts.shift}').on('keydown.enter', lambda: update_shift(float(shiftin.value)))
            with ui.row():
                ui.label('Pre-Message Stops: ')
                prestopin = ui.input(placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: update_pre_stop(int(prestopin.value)))
            dialog.open()

    @ui.refreshable
    def chat_messages() -> None:
        if messages:
            for text, stamp, sent in messages:
                with ui.element('div').on('click', lambda t = text: sentmsg_popup(t)):
                    ui.chat_message(text=text, stamp=stamp, sent = sent)
        else:
            ui.label('No messages yet').classes('mx-auto my-36')
        ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')


    def display_txt(received_txt: str) -> None:
        stamp = datetime.now().strftime('%X')
        messages.append((received_txt, stamp, False))
        chat_messages.refresh()

    def text_enter() -> None:
        global sentarr, optsarr, curopts
        sentarr.append(text.value.upper())
        optsarr.append(copy.deepcopy(curopts))
        #send_msg(text.value)
        stamp = datetime.now().strftime('%X')
        messages.append((text.value.upper(), stamp, True))
        text.value = ''
        chat_messages.refresh()
    
    ui.add_css(r'a:link, a:visited {color: inherit !important; text-decoration: none; font-weight: 500}')
    with ui.footer().classes('bg-white'), ui.column().classes('w-full max-w-3xl mx-auto my-6'):
        with ui.row().classes('w-full no-wrap items-center'):
            text = ui.input(placeholder='message').on('keydown.enter', text_enter).props('rounded outlined input-class=mx-3').classes('flex-grow')
            ui.button(icon = 'settings', on_click = settings_popup)

    await ui.context.client.connected()  # chat_messages(...) uses run_javascript which is only possible after connecting

    with ui.column().classes('w-full max-w-2xl mx-auto items-stretch'):
        chat_messages()
