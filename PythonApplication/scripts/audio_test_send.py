from loguru import logger
from rtty_sdr.core.protocol import SendMessage
from rtty_sdr.core.options import SystemOpts
from rtty_sdr.debug.internal_signal import internal_signal
from rtty_sdr.core.baudot import BaudotEncoder

import sys
import sounddevice as sd

opts = SystemOpts.default()
message = "HI" if len(sys.argv) == 1 else sys.argv[1]

encoder = BaudotEncoder(initial_shift=opts.rtty.initial_shift)
send_message = SendMessage.create(message, "KJ5OEH", encoder)
logger.info(f"Sending: {send_message.encoding}")
encoded = send_message.codes
signal, t, annotations = internal_signal(encoded, opts.signal, 0.05)

sd.play(signal, opts.signal.Fs, blocking=True)
