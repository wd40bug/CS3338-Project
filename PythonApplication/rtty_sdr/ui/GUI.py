from datetime import datetime
from nicegui import run, ui
from rtty_sdr.core.options import SystemOpts, RTTYOpts
import copy
import time

messages: list[list[str, str, bool, bool, int]] = []
receiving = False
sending = False
err_correction = True
corrupt_msg = False
#cursysopts = SystemOpts()
curopts = RTTYOpts(baud=45.45, mark=2125, shift=170, pre_msg_stops=40, stop_bits = 1.5, post_msg_stops= 1)
optsarr: list[RTTYOpts] = []
sentarr: list[str] = []
recvarr: list[str] = []
senti = 0
recvi = 0

def send_msg(txt: str) -> None:
    time.sleep(2)

def rcv_msg() -> None:
    time.sleep(2)
#def send_optchanges(opts: systemopts) -> None:
    
@ui.page('/')
async def main() -> None:
    with ui.dialog() as dialog, ui.card().classes('w-150 h-250'):
        with ui.row().classes('w-full justify-end'):
            ui.button(icon = 'close', on_click = dialog.close, color = 'black').props('flat').set_background_color('white')

    def sentmsg_popup(num: int) -> None:
        with dialog.clear(), ui.card().classes('w-100 h-80'):
            with ui.row().classes('w-full'):
                ui.label('Sent Message Details').style('font-size: 2em')
                ui.space()
                ui.button(icon = 'close', on_click = dialog.close, color = 'black').props('flat').set_background_color('white')
            with ui.row():
                ui.label(f'Sent Message: {sentarr[num].upper()}')
            with ui.row():
                ui.label('Corrupted Message: N/A')
            with ui.row():
                ui.label(f'Baud Rate: {optsarr[num].baud}')
            with ui.row():
                ui.label(f'Mark Frequency: {optsarr[num].mark}')
            with ui.row():
                ui.label(f'Shift Frequency: {optsarr[num].shift}')
            with ui.row():
                ui.label(f'Pre-Message Stops: {optsarr[num].pre_msg_stops}')
            dialog.open()

    def rcvdmsg_popup(num: int) -> None:
        with dialog.clear(), ui.card().classes('w-120 h-80'):
            with ui.row().classes('w-full'):
                ui.label('Received Message Details').style('font-size: 2em')
                ui.space()
                ui.button(icon = 'close', on_click = dialog.close, color = 'black').props('flat').set_background_color('white')
            with ui.row():
                ui.label(f'Sent Message: {recvarr[num]}')
            with ui.row():
                ui.label('Corrupted Message: N/A')
            with ui.row():
                ui.label(f'Baud Rate: ')
            with ui.row():
                ui.label(f'Mark Frequency: ')
            with ui.row():
                ui.label(f'Shift Frequency: ')
            with ui.row():
                ui.label(f'Pre-Message Stops: ')
            dialog.open()

    def settings_popup():
        global curopts, err_correction, corrupt_msg

        def apply_changes():
            err_correction = errcorrin.value
            corrupt_msg = corruptin.value
            if(baudin.value != None):
                curopts.baud = baudin.value
            if(markin.value != None):
                curopts.mark = markin.value
            if(shiftin.value != None):
                curopts.shift = shiftin.value
            if(prestopin.value != None):
                curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            # if(prestopin.value != None):
            #     curopts.pre_msg_stops = prestopin.value
            #sendoptchanges()
            dialog.close()

        with dialog.clear(), ui.card().classes('w-100 h-160'):
            with ui.row().classes('w-full'):
                ui.label('Options').style('font-size: 2em')
                ui.space()
                ui.button(icon = 'close', on_click = dialog.close, color = 'black').props('flat').set_background_color('white')
            with ui.row():
                ui.label('Error Correction: ')
                errcorrin = ui.checkbox(value = True)
            with ui.row():
                ui.label('Corrupt Message: ')
                corruptin = ui.checkbox()
            with ui.row():
                ui.label('Baud Rate: ')
                baudin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = cursysopts, placeholder = f'{curopts.baud}').on('keydown.enter', lambda: apply_changes())
            with ui.row():
                ui.label('Mark Frequency: ')
                markin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.mark, placeholder = f'{curopts.mark}').on('keydown.enter', lambda: apply_changes())
            with ui.row():
                ui.label('Shift Frequency: ')
                shiftin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.shift, placeholder = f'{curopts.shift}').on('keydown.enter', lambda: apply_changes())
            with ui.row():
                ui.label('Pre-Message Stops: ')
                prestopin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, precision = 0 , placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            # with ui.row():
            #     ui.label('Post-Message Stops: ')
            #     poststopin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, precision = 0 , placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            # with ui.row():
            #     ui.label('Sampling Frequency: ')
            #     fsin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, precision = 0 , placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            # with ui.row():
            #     ui.label('Oversampling: ')
            #     oversampin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, precision = 0 , placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            # with ui.row():
            #     ui.label('Envelope Generator order: ')
            #     envelopgenin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, precision = 0 , placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            # with ui.row():
            #     ui.label('Envelope Generator Envelopes Order: ')
            #     engenenorderin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, precision = 0 , placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            # with ui.row():
            #     ui.label('Overlap Ratio: ')
            #     overlapratioin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            # with ui.row():
            #     ui.label('DFT Length: ')
            #     dftlenin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, precision = 0 , placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            # with ui.row():
            #     ui.label('Lower Threshold: ')
            #     lowthresin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            # with ui.row():
            #     ui.label('Upper Threshold: ')
            #     upthresin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            # with ui.row():
            #     ui.label('Squelch Order: ')
            #     squelchordin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, precision = 0 , placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            # with ui.row():
            #     ui.label('Squelch Envelopes Order: ')
            #     squelchenveordin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, precision = 0 , placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            # with ui.row():
            #     ui.label('Overall Filter Bandwidth Safety Margin: ')
            #     bwsmin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            # with ui.row():
            #     ui.label('Squelch Grace Percent: ')
            #     squelchperin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            # with ui.row():
            #     ui.label('Idle Bits:')
            #     idlbitin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            # with ui.row():
            #     ui.label('Engine: ')
            #     engin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            # with ui.row():
            #     ui.label('Source: ')
            #     sourcin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            # with ui.row():
            #     ui.label('Callsign: ')
            #     prestopin = ui.number(min = 0, validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            with ui.row():
                ui.label('Pre-Message Stops: ')
                prestopin = ui.input(validation={'Required': lambda v: v is not None}, value = curopts.pre_msg_stops, precision = 0 , placeholder = f'{curopts.pre_msg_stops}').on('keydown.enter', lambda: apply_changes())
            with ui.row():
                ui.button(text = 'Apply', on_click = apply_changes)
            dialog.open()

    def handle_msgclick(sent: bool, num: int):
        if sent == True:
            sentmsg_popup(num)
        else:
            rcvdmsg_popup(num)

    @ui.refreshable
    def chat_messages() -> None:
        if messages:
            for text, stamp, sent, spin, num in messages:
                with ui.row():
                    spinner1 = ui.spinner('radio', size = 'lg', color = 'green')
                    ui.space()
                    spinner2 = ui.spinner('radio', size = 'lg')
                    spinner1.set_visibility(receiving and spin)
                    spinner2.set_visibility(sending and spin)
                with ui.element('div').on('click', lambda n = num, s = sent: handle_msgclick(s,n)):
                    message = ui.chat_message(text=text, stamp=stamp, sent = sent)
                    message.set_visibility(not spin)
        else:
            ui.label('No messages yet').classes('mx-auto my-36')
        ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')

    async def handle_msg_rcv() -> None:
        global receiving, recvi
        receiving = 1
        stamp = datetime.now().strftime('%X')
        msg = ["", stamp, False, True, recvi]
        messages.append(msg)
        chat_messages.refresh()
        await run.cpu_bound(rcv_msg)
        receiving = 0
        msg[0] = f"This is a pretend message {recvi}"
        msg[3] = False
        recvarr.append(f"This is a pretend message {recvi}")
        recvi = recvi + 1
        chat_messages.refresh()

    async def text_enter() -> None:
        global sentarr, optsarr, curopts, sending, senti
        if text.value == "":
            return
        sentarr.append(text.value.upper())
        optsarr.append(copy.deepcopy(curopts))
        stamp = datetime.now().strftime('%X')
        sending = 1
        msg = [text.value.upper(), stamp, True, True, senti]
        messages.append(msg)
        chat_messages.refresh()
        await run.cpu_bound(send_msg, text.value)
        msg[3] = False
        sending = 0
        text.value = ''
        senti = senti + 1 
        chat_messages.refresh()
    
    ui.add_css(r'a:link, a:visited {color: inherit !important; text-decoration: none; font-weight: 500}')
    with ui.footer().classes('bg-white'), ui.column().classes('w-full max-w-3xl mx-auto my-6'):
        with ui.row().classes('w-full no-wrap items-center'):
            text = ui.input(placeholder='message').on('keydown.enter', text_enter).props('rounded outlined input-class=mx-3').classes('flex-grow')
            ui.button(icon = 'settings', on_click = settings_popup)
            ui.button(text="Pretend Receive", on_click = handle_msg_rcv)

    await ui.context.client.connected()  # chat_messages(...) uses run_javascript which is only possible after connecting

    with ui.column().classes('w-full max-w-2xl mx-auto items-stretch'):
        chat_messages()
