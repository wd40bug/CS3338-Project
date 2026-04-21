from types import MappingProxyType
from typing_extensions import get_args
import msgspec
from typing import ClassVar, Literal, Self

from rtty_sdr.core.options import SignalOpts, SystemOpts
from rtty_sdr.core.protocol import RecvMessage, SendMessage
import numpy as np
import numpy.typing as npt

from rtty_sdr.debug.internal_signal import internal_signal
from rtty_sdr.dsp.protocol_decode import ProtocolDebug


class Send(msgspec.Struct, frozen=True):
    topic: ClassVar[Literal["ui.send_message"]] = "ui.send_message"
    msg: SendMessage


class SendInternal(msgspec.Struct, frozen=True):
    topic: ClassVar[Literal["ui.send_internal"]] = "ui.send_internal"
    signal: npt.NDArray[np.float64]

    @classmethod
    def create(cls, msg: str, opts: SystemOpts) -> Self:
        to_send = SendMessage.create(msg, opts.callsign, opts.baudot)
        signal, _, _ = internal_signal(to_send.codes, opts.signal)
        return cls(signal=signal)

    @classmethod
    def create_with_msg(cls, msg: SendMessage, opts: SignalOpts) -> Self:
        signal, _, _ = internal_signal(msg.codes, opts)
        return cls(signal=signal)


class Receiving(msgspec.Struct, frozen=True):
    topic: ClassVar[Literal["dsp.receiving"]] = "dsp.receiving"


class LostSignal(msgspec.Struct, frozen=True):
    topic: ClassVar[Literal["dsp.lost_signal"]] = "dsp.lost_signal"


class ReceivedMessage(msgspec.Struct, frozen=True):
    topic: ClassVar[Literal["dsp.received"]] = "dsp.received"
    msg: RecvMessage

class FinalMessage(msgspec.Struct, frozen=True):
    topic: ClassVar[Literal["errcorr.final"]] = "errcorr.final"
    msg: RecvMessage


class DebugMessage(msgspec.Struct, frozen=True):
    topic: ClassVar[Literal["dsp.debug"]] = "dsp.debug"
    debug: ProtocolDebug
    is_done: bool


class Shutdown(msgspec.Struct, frozen=True):
    topic: ClassVar[Literal["system.shutdown"]] = "system.shutdown"


class Settings(msgspec.Struct, frozen=True):
    topic: ClassVar[Literal["ui.settings"]] = "ui.settings"
    settings: SystemOpts


class Sent(msgspec.Struct, frozen=True):
    topic: ClassVar[Literal["controller.sent"]] = "controller.sent"


type AnyMessage = (
    Send
    | Sent
    | Receiving
    | LostSignal
    | ReceivedMessage
    | FinalMessage
    | SendInternal
    | Shutdown
    | Settings
    | DebugMessage
)

# breakpoint()
topics_map: MappingProxyType[str, type[AnyMessage]] = MappingProxyType(
    {ty.topic: ty for ty in get_args(AnyMessage.__value__)}
)
