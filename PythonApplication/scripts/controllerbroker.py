from queue import Queue
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.core.protocol import SendMessage
from rtty_sdr.core.baudot import BaudotEncoder
from rtty_sdr.controller.controller import ToESP, send_receive


encoder = BaudotEncoder()

msg1 = SendMessage.create("hi", "KJ5OEH", encoder)
msg2 = SendMessage.create("hi again", "KJ5OEH", encoder)

opts = SystemOpts.default()

toesp1 = ToESP(opts.rtty, msg1)
toesp2 = ToESP(opts.rtty, msg2)

msgqueue = Queue()

msgqueue.put(toesp1)
msgqueue.put(toesp2)
msgqueue.put("done")

send_receive(msgqueue)


