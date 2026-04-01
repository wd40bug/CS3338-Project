from queue import Queue
from rtty_sdr.core.options import RTTYOpts
from rtty_sdr.core.protocol import SendMessage
from rtty_sdr.core.baudot import BaudotEncoder
from rtty_sdr.controller.controller import ToESP, send_receive


encoder = BaudotEncoder()

msg1 = SendMessage("hi", "KJ5OEH", encoder)
msg2 = SendMessage("hi again", "KJ5OEH", encoder)

opts = RTTYOpts(baud=45.45, mark=2125, shift=170, pre_msg_stops=40)

toesp1 = ToESP(opts, msg1.codes)
toesp2 = ToESP(opts, msg2.codes)

msgqueue = Queue()

msgqueue.put(toesp1)
msgqueue.put(toesp2)
msgqueue.put("done")

send_receive(msgqueue)


