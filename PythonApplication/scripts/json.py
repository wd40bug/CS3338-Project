from loguru import logger
from rtty_sdr.core.options import RTTYOpts, SystemOpts
from rtty_sdr.core.protocol import SendMessage
from rtty_sdr.core.baudot import BaudotEncoder
from rtty_sdr.controller.controller import ToESP, createJSON
from rtty_sdr.controller.serialcom import send_serial

msg = "hi"
encoder = BaudotEncoder()
send_message = SendMessage.create(msg, "KJ5OEH", encoder)
logger.info(f"Sending: {send_message.encoding}")
opts = SystemOpts.default().rtty

data = ToESP(opts, send_message)

json = createJSON(data)


send_serial(json)

logger.info(json)
