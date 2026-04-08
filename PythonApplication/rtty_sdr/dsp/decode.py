from enum import IntEnum, auto
from typing import Annotated, Literal, Iterator, Iterable

import numpy as np
import numpy.typing as npt
from dataclasses import dataclass

from pydantic import BaseModel, Field
from rtty_sdr.debug.state_changes import StateChanges
from rtty_sdr.dsp.commands import Command, Commands
from rtty_sdr.dsp.sources import AudioSource
from rtty_sdr.dsp.engines import DemodulatorEngine
from rtty_sdr.core.options import DecodeStreamOpts
from rtty_sdr.dsp.squelch import Squelch
from rtty_sdr.debug.annotations import DebugAnnotations
from rtty_sdr.debug.debug_types import DebugCombineable
import time


class Code(BaseModel):
    code: int
    kind: Literal["code"] = "code"


class Commanded(BaseModel):
    command: Command
    kind: Literal["command"] = "command"


class LostSignal(BaseModel):
    kind: Literal["lost_signal"] = "lost_signal"


type DecodeYieldType = Annotated[
    Code | LostSignal | Commanded, Field(discriminator="kind")
]
type DecodeYield = tuple[DecodeYieldType, DecodeDebug]


class DecodeState(IntEnum):
    NO_SIGNAL = auto()
    IDLE = auto()
    START = auto()
    DATA = auto()
    STOP = auto()


def decode_stream(
    source: AudioSource,
    squelch: Squelch,
    engine: DemodulatorEngine,
    opts: DecodeStreamOpts,
    pill: Commands,
) -> Iterator[DecodeYield]:
    signal_opts = opts.decode.signal
    countdown: None | int = None
    state: DecodeState = DecodeState.NO_SIGNAL
    current_word: list[bool] = []

    builder = DecodeDebugBuilder(state)

    squelch_count = 0
    idle_len = 0

    while True:
        raw_audio = source.read_chunk()
        cmd = pill.check()
        if cmd is not None:
            if cmd.command == "stop" or cmd.command == "restart":
                yield (Commanded(command=cmd), builder.finish())
                return
            else:
                raise ValueError(f"Unknown command: {cmd[0]}")

        if raw_audio is None:
            time.sleep(opts.none_friction)
            continue

        filtered_audio, squelch_arr, _ = squelch.process(raw_audio)

        samples, _ = engine.process(filtered_audio)

        # Give the chunk to the builder
        builder.load_frame(raw_audio, samples, squelch_arr)

        for i, (sample, sq) in enumerate(zip(samples, squelch_arr)):
            if countdown is not None and countdown > 0:
                countdown -= 1
                continue

            # Squelch
            if sq:
                squelch_count += 1
                if squelch_count > opts.squelch_grace_period:
                    if state != DecodeState.NO_SIGNAL and state != DecodeState.IDLE:
                        # Lost signal, reset protocol
                        yield (LostSignal(), builder.build(i, DecodeState.NO_SIGNAL))
                    state = DecodeState.NO_SIGNAL
                continue
            else:
                squelch_count = 0

            match state:
                case DecodeState.NO_SIGNAL:
                    if not sq:
                        state = DecodeState.IDLE
                        builder.change_state(i, state)
                case DecodeState.IDLE:
                    if sample > 0:
                        idle_len += 1
                        if idle_len >= opts.idle_samples:
                            state = DecodeState.START
                            builder.change_state(i, state)
                    else:
                        idle_len = 0
                case DecodeState.START:
                    if sample < 0:
                        builder.start_bit(i)
                        state = DecodeState.DATA
                        builder.change_state(i, state)
                        countdown = round(1.5 * signal_opts.nsamp)
                        current_word.clear()
                case DecodeState.DATA:
                    current_word.append(sample > 0)
                    builder.data_bit(i)
                    countdown = signal_opts.nsamp
                    if len(current_word) == 5:
                        state = DecodeState.STOP
                        builder.change_state(i, state)
                case DecodeState.STOP:
                    code = sum(
                        bit * (2**j) for j, bit in enumerate(reversed(current_word))
                    )
                    state = DecodeState.START
                    yield (Code(code=code), builder.build(i, state))
                    countdown = None

        # Loop finished, save remaining unbuilt data and advance the absolute clock
        builder.commit_frame()


@dataclass(frozen=True)
class DecodeDebug(DebugCombineable):
    indices: npt.NDArray[np.int_]
    signal: npt.NDArray[np.float64]
    envelope: npt.NDArray[np.float64]
    squelch: npt.NDArray[np.int_]
    annotations: DebugAnnotations
    states: list[DecodeState]

    @classmethod
    def combine(cls, debugs: Iterable[DecodeDebug]) -> DecodeDebug:
        debug_list = list(debugs)

        if not debug_list:
            # Return an empty instance if the iterable is empty
            return cls(
                np.array([]),
                np.array([]),
                np.array([]),
                np.array([]),
                DebugAnnotations(np.array([]), np.array([]), np.array([])),
                [],
            )

        # Concat the arrays
        return cls(
            indices=np.concatenate([d.indices for d in debug_list]),
            signal=np.concatenate([d.signal for d in debug_list]),
            envelope=np.concatenate([d.envelope for d in debug_list]),
            squelch=np.concatenate([d.squelch for d in debug_list]),
            annotations=DebugAnnotations.combine([d.annotations for d in debug_list]),
            states=[state for d in debugs for state in d.states],
        )


@dataclass
class StreamData:
    signal: npt.NDArray[np.float64]
    envelope: npt.NDArray[np.float64]
    squelch: npt.NDArray[np.int_]

    def __len__(self) -> int:
        return len(self.signal)

    def __getitem__(self, key: slice | int) -> StreamData:
        return StreamData(self.signal[key], self.envelope[key], self.squelch[key])


class DecodeDebugBuilder:
    def __init__(self, default_state: DecodeState) -> None:
        self.__start_index: int = 0
        self.__accumulated_data: list[StreamData] = []

        # Annotations
        self.__start_bit: int | None = None
        self.__data_bits: list[int] = []
        self.__state_changes: StateChanges[DecodeState] = StateChanges(default_state)

        # Current frame state
        self.__frame_index: int = 0
        self.__frame_consumed: int = 0
        self.__frame_data: StreamData | None = None

    def load_frame(
        self,
        signal: npt.NDArray[np.float64],
        envelope: npt.NDArray[np.float64],
        squelch: npt.NDArray[np.int_],
    ) -> None:
        assert self.__frame_data is None, "Previous frame was not committed!"
        self.__frame_consumed = 0
        self.__frame_data = StreamData(signal, envelope, squelch)

    def start_bit(self, i: int) -> None:
        self.__start_bit = self.__frame_index + i

    def data_bit(self, i: int) -> None:
        self.__data_bits.append(i + self.__frame_index)

    def change_state(self, i: int, new_state: DecodeState) -> None:
        self.__state_changes.change(i + self.__frame_index, new_state)

    def commit_frame(self) -> None:
        if self.__frame_data:
            if self.__frame_consumed < len(self.__frame_data):
                self.__accumulated_data.append(
                    self.__frame_data[self.__frame_consumed :]
                )

            self.__frame_index += len(self.__frame_data)
            self.__frame_data = None  # Clear for the assert in load_frame

    def finish(self) -> DecodeDebug:
        return self.build(-1, DecodeState.NO_SIGNAL, stop_bit=False)

    def build(self, i: int, state: DecodeState, stop_bit: bool = True) -> DecodeDebug:
        if self.__frame_data:
            self.__accumulated_data.append(
                self.__frame_data[self.__frame_consumed : i + 1]
            )

        start_bits = (
            np.array([self.__start_bit])
            if self.__start_bit is not None
            else np.array([])
        )

        signal_arr = (
            np.concatenate([d.signal for d in self.__accumulated_data])
            if self.__accumulated_data
            else np.array([])
        )
        envelope_arr = (
            np.concatenate([d.envelope for d in self.__accumulated_data])
            if self.__accumulated_data
            else np.array([])
        )
        squelch_arr = (
            np.concatenate([d.squelch for d in self.__accumulated_data])
            if self.__accumulated_data
            else np.array([])
        )

        ret = DecodeDebug(
            np.arange(self.__start_index, self.__frame_index + i + 1),
            signal_arr,
            envelope_arr,
            squelch_arr,
            DebugAnnotations(
                start_bits,
                np.array([i + self.__frame_index]) if stop_bit else np.array([]),
                np.array(self.__data_bits),
            ),
            self.__state_changes.build(i + self.__frame_index, state),
        )
        assert (
            len(ret.indices)
            == len(ret.signal)
            == len(ret.envelope)
            == len(ret.squelch)
            == len(ret.states)
        ), (
            f"Values mismatched. Expected all to be equal:\nindicies: {len(ret.indices)}\nsignal: {len(ret.signal)}\nenvelope: {len(ret.envelope)}\nsquelch: {len(ret.squelch)}\nstates: {len(ret.states)}\n"
        )

        self.__start_index = i + self.__frame_index + 1
        self.__accumulated_data.clear()
        self.__start_bit = None
        self.__data_bits.clear()
        self.__frame_consumed = i + 1

        return ret
