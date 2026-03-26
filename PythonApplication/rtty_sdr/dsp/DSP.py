import numpy as np
import numpy.typing as npt

from typing import Final, Literal, Iterator

from rtty_sdr.dsp.sources import AudioSource
from rtty_sdr.dsp.engines import DemodulatorEngine
from rtty_sdr.core.options import SystemOpts


class RTTYDecoder:
    source: Final[AudioSource]
    engine: Final[DemodulatorEngine]
    opts: Final[SystemOpts]
    __state: Literal["idle"]

    def __init__(
        self, source: AudioSource, engine: DemodulatorEngine, opts: SystemOpts
    ) -> None:
        self.source = source
        self.engine = engine
        self.opts = opts

    def decode_stream(self) -> Iterator[int]:
        while True:
            # 1. Pull data from whatever source is plugged in
            raw_audio = self.source.read_chunk()

            # 2. Push it through whatever engine is plugged in
            states, squelch = self.engine.process(raw_audio)

            # 3. Iterate through the analyzed states
            for i in range(len(states)):
                if not squelch[i]:
                    self.reset_state()
                    continue

                # -> Insert your Mark-Hold, Start/Stop Bit framing,
                # -> and halfway-point sampling logic right here.

                # When a full 5-bit word is collected:
                # yield self.current_word

    def reset_state(self) -> None: ...
