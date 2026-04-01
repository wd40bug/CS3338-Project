from rtty_sdr.core.options import RTTYOpts
from rtty_sdr.core.protocol import SendMessage
from rtty_sdr.core.baudot import BaudotEncoder
from rtty_sdr.controller.controller import ToESP, createJSON
from rtty_sdr.controller.serialcom import send_serial

msg = "hi"
encoder = BaudotEncoder()
send_message = SendMessage(msg, "KJ5OEH", encoder)
print(f"Sending: {send_message.encoding}")
opts = RTTYOpts(baud=45.45, mark=2125, shift=170, pre_msg_stops=1)

data = ToESP(opts, send_message.codes)

json = createJSON(data)


send_serial(json)

print(json)
