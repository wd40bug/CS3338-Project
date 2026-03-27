from typing import Literal, Iterator

from rtty_sdr.dsp.sources import AudioSource
from rtty_sdr.dsp.analysis import DecodeDebug, DecodeDebugBuilder
from rtty_sdr.dsp.engines import DemodulatorEngine
from rtty_sdr.core.options import SystemOpts

type DecodeYield = Literal["reset"] | tuple[int, DecodeDebug]

def decode_stream(
    source: AudioSource, engine: DemodulatorEngine, opts: SystemOpts
) -> Iterator[DecodeYield]:
    countdown: None | int = None
    state: Literal["no_signal", "idle", "start", "data", "stop"] = "start"
    current_word: list[bool] = []

    builder = DecodeDebugBuilder()

    while True:
        raw_audio = source.read_chunk()
        if raw_audio is None:
            return

        samples, squelch_arr = engine.process(raw_audio)
        
        # Give the chunk to the builder
        builder.load_frame(raw_audio, samples, squelch_arr)

        for i, (sample, _) in enumerate(zip(samples, squelch_arr)):
            # TODO: squelch logic with sq_val

            if countdown is not None and countdown > 0:
                countdown -= 1
                continue

            match state:
                case "no_signal" | "idle":
                    pass
                case "start":
                    if sample < 0:
                        builder.start_bit(i)
                        state = "data"
                        countdown = round(1.5 * opts.nsamp)
                        current_word.clear()
                case "data":
                    current_word.append(sample > 0)
                    builder.data_bit(i)
                    countdown = opts.nsamp
                    if len(current_word) == 5:
                        state = "stop"
                case "stop":
                    code = sum(
                        bit * (2**j) for j, bit in enumerate(reversed(current_word))
                    )
                    
                    yield (code, builder.build(i))
                    
                    state = "start"
                    countdown = None

        # Loop finished, save remaining unbuilt data and advance the absolute clock
        builder.commit_frame()
