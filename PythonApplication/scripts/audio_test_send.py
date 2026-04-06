from loguru import logger
from rtty_sdr.core.protocol import SendMessage
from rtty_sdr.core.options import SystemOpts, RTTYOpts
from rtty_sdr.debug.internal_signal import internal_signal
from rtty_sdr.core.baudot import BaudotEncoder

import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt
import sys
import sounddevice as sd

Fs = 8000
rtty = RTTYOpts(baud=45.45, mark=2125, shift=170, pre_msg_stops=1, stop_bits=2, post_msg_stops=1)
opts = SystemOpts(Fs, rtty)
message = "HI" if len(sys.argv) == 1 else sys.argv[1]

encoder = BaudotEncoder()
send_message = SendMessage(message, "KJ5OEH", encoder)
logger.info(f"Sending: {send_message.encoding}")
encoded = send_message.codes
signal, t, annotations = internal_signal(encoded, opts, 0.05)

sd.play(signal, Fs, blocking=True)
