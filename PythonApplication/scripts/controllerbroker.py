from loguru import logger
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.core.protocol import SendMessage
from rtty_sdr.controller.espcom import EspComms
from rtty_sdr.controller.espcom import ToESP
import time

time.sleep(10)

opts = SystemOpts.default(pre_msg_stops=20)

msg1 = SendMessage.create("hi", "KJ5OEH", opts.baudot)
msg2 = SendMessage.create("hi again", "KJ5OEH", opts.baudot)

logger.info(f"First message: {msg1.encoding}")
logger.info(f"Second message: {msg2.encoding}")

toesp1 = ToESP(msg1.codes, opts.rtty)
toesp2 = ToESP(msg2.codes, opts.rtty)

comms = EspComms()

comms.send_receive(toesp1)
comms.send_receive(toesp2)
