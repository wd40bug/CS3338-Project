# from dataclasses import dataclass, field
from enum import IntEnum
from typing import Final, Literal, ClassVar, Self

from msgspec import Struct
import sys


class RTTYOpts(Struct):
    stop_bits: float
    baud: float
    mark: int
    shift: int
    pre_msg_stops: int
    post_msg_stops: int

    data_bits: ClassVar[Final[int]] = 5
    
    @property
    def space(self):
        return self.mark + self.shift

    @property
    def seconds_per_bit(self) -> float:
        return 1 / self.baud

    @property
    def bits_per_character(self) -> float:
        return 1 + self.data_bits + self.stop_bits

    def __str__(self) -> str:
        return f"Mark: {self.mark}, Space: {self.space}, Baud: {self.baud}"


class SignalOpts(Struct):
    Fs: int
    rtty: RTTYOpts

    @property
    def nsamp(self):
        return round(self.Fs / self.rtty.baud)


class DecodeCommon(Struct):
    oversampling: int
    signal: SignalOpts

    @property
    def chunk_size(self) -> int:
        return self.signal.nsamp // self.oversampling

class Shift(IntEnum):
    LTRS = 31
    FIGS = 27

class BaudotOptions(Struct):
    initial_shift: Shift
    replace_invalid_with: str | None = None


class GoertzelOpts(Struct):
    overlap_ratio: float
    dft_len: int
    decode: DecodeCommon

    @property
    def overlap_size(self) -> int:
        return round(self.decode.chunk_size * self.overlap_ratio)


class EnvelopeOpts(Struct):
    order: int
    envelopes_order: int
    decode: DecodeCommon


class SquelchOpts(Struct):
    lower_thresh: float
    upper_thresh: float
    order: int
    envelopes_order: int
    bw_safety_margin: float
    decode: DecodeCommon


class DecodeStreamOpts(Struct):
    squelch_grace_percent: float
    idle_bits: float
    none_friction: float
    decode: DecodeCommon

    @property
    def squelch_grace_period(self) -> int:
        return round(self.squelch_grace_percent * self.decode.chunk_size)

    @property
    def idle_samples(self) -> int:
        return round(self.idle_bits * self.decode.chunk_size)


class SystemOpts(Struct):
    # Stem configs
    rtty: RTTYOpts
    signal: SignalOpts
    decode: DecodeCommon

    # Leaf configs
    envelope: EnvelopeOpts
    goertzel: GoertzelOpts
    squelch: SquelchOpts
    stream: DecodeStreamOpts
    baudot: BaudotOptions

    # System Options
    engine: Literal["goertzel", "envelope"]
    source: Literal["microphone", "internal"]
    callsign: str
    port: str | None
    error_correction: bool
    set_seed: int
    corruption: float
    num_iterations: int

    @classmethod
    def default(
        cls,
        stop_bits: float = 1.5,
        baud: float = 45.45,
        mark: int = 2125,
        shift: int = 170,
        pre_msg_stops: int = 5,
        post_msg_stops: int = 1,
        Fs: int = 8000,
        oversampling: int = 5,
        envelope_generator_order: int = 4,
        envelope_generator_envelopes_order: int = 4,
        overlap_ratio: float = 0.5,
        dft_len: int = 256,
        lower_thresh: float = 0.2,
        upper_thresh: float = 2,
        squelch_order: int = 4,
        squelch_envelopes_order: int = 4,
        bw_safety_margin: float = 2,
        squelch_grace_percent: float = 0.25,
        idle_bits: float = 2,
        none_friction: float = 0.1,
        initial_shift: Shift = Shift.LTRS,
        replace_invalid_with: str | None = None,
        engine: Literal["goertzel", "envelope"] = "goertzel",
        source: Literal["microphone", "internal"] = "microphone",
        callsign: str = "KJ5OEH",
        port: str = "/dev/ttyUSB0" if sys.platform == "linux" else "COM0",
        error_correction: bool = False,
        num_iterations: int = 1,
        corruption: float = 0,
        set_seed: int = 0,
    ) -> Self:
        rtty = RTTYOpts(
            stop_bits=stop_bits,
            baud=baud,
            mark=mark,
            shift=shift,
            pre_msg_stops=pre_msg_stops,
            post_msg_stops=post_msg_stops,
        )
        signal = SignalOpts(Fs=Fs, rtty=rtty)
        decode = DecodeCommon(
            oversampling=oversampling,
            signal=signal,
        )

        return cls(
            rtty=rtty,
            signal=signal,
            decode=decode,
            envelope=EnvelopeOpts(
                envelopes_order=envelope_generator_envelopes_order,
                decode=decode,
                order=envelope_generator_order,
            ),
            goertzel=GoertzelOpts(
                overlap_ratio=overlap_ratio, dft_len=dft_len, decode=decode
            ),
            squelch=SquelchOpts(
                lower_thresh=lower_thresh,
                upper_thresh=upper_thresh,
                decode=decode,
                order=squelch_order,
                envelopes_order=squelch_envelopes_order,
                bw_safety_margin=bw_safety_margin,
            ),
            stream=DecodeStreamOpts(
                squelch_grace_percent=squelch_grace_percent,
                idle_bits=idle_bits,
                decode=decode,
                none_friction=none_friction,
            ),
            baudot=BaudotOptions(
                initial_shift=initial_shift, replace_invalid_with=replace_invalid_with
            ),
            engine=engine,
            source=source,
            callsign=callsign,
            port=port,
            error_correction=error_correction,
            num_iterations=num_iterations,
            corruption=corruption,
            set_seed=set_seed
        )
