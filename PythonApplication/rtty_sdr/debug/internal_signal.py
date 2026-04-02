import msgspec
import scipy.signal as sg
import numpy as np
import numpy.typing as npt

from rtty_sdr.core.options import SignalOpts
from rtty_sdr.debug.annotations import DebugAnnotations


def internal_signal(
    message: list[int], opts: SignalOpts, prepend_silence_s: float = 0
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], DebugAnnotations]:
    # Ensure input is strictly typed as an integer array
    msg: npt.NDArray[np.int_] = np.array(message, dtype=np.int_)
    N: int = len(msg)

    # Create a 2D array of bits Nx5
    shifts: npt.NDArray[np.int_] = np.arange(4, -1, -1)
    masks: npt.NDArray[np.int_] = 1 << shifts
    # Cast the boolean result back to integers for consistency
    data_bits_2d: npt.NDArray[np.int_] = ((msg[:, None] & masks) > 0).astype(np.int_)

    # Add start and stop bits (Forced to int_ to prevent float64 upcasting)
    start_bits: npt.NDArray[np.int_] = np.zeros((N, 1), dtype=np.int_)
    stop_bits: npt.NDArray[np.int_] = np.ones((N, 1), dtype=np.int_)
    framed_2d: npt.NDArray[np.int_] = np.hstack((start_bits, data_bits_2d, stop_bits))

    # Flatten
    message_stream: npt.NDArray[np.int_] = framed_2d.flatten()

    # Calculate bit durations (Forced to int so np.repeat doesn't crash)
    samples_per_bit: int = int(opts.nsamp)
    samples_per_stop: int = int(opts.nsamp * opts.rtty.stop_bits)

    # Create repeat template (Forced to int_)
    bit_durations: npt.NDArray[np.int_] = np.array(
        [samples_per_bit] * 6 + [samples_per_stop], dtype=np.int_
    )
    template: npt.NDArray[np.int_] = np.tile(bit_durations, N)

    # Apply template
    message_symbols: npt.NDArray[np.int_] = np.repeat(message_stream, template)

    # Add pre and post-message stops
    pre_message_samples: int = int(
        opts.rtty.stop_bits * opts.rtty.pre_msg_stops * opts.nsamp
    )
    post_message_samples: int = int(
        opts.rtty.stop_bits * opts.rtty.post_msg_stops * opts.nsamp
    )
    pre_message_symbols: npt.NDArray[np.int_] = np.ones(
        pre_message_samples, dtype=np.int_
    )
    post_message_symbols: npt.NDArray[np.int_] = np.ones(
        post_message_samples, dtype=np.int_
    )
    # Note: np.concatenate is generally safer across numpy versions than np.concat
    symbols: npt.NDArray[np.int_] = np.concatenate(
        (pre_message_symbols, message_symbols, post_message_symbols)
    )
    total_samples: int = len(symbols)

    # Locate transitions
    transitions: npt.NDArray[np.int_] = np.where(symbols[:-1] != symbols[1:])[0] + 1

    # Build the resets
    resets: npt.NDArray[np.int_] = np.zeros(total_samples, dtype=np.int_)
    resets[transitions] = transitions
    block_starts: npt.NDArray[np.int_] = np.maximum.accumulate(resets)

    # Fucking brilliant
    sample_indices: npt.NDArray[np.int_] = np.arange(total_samples, dtype=np.int_)
    t_local: npt.NDArray[np.float64] = (sample_indices - block_starts) / opts.Fs

    # Map frequencies and modulate
    f_array: npt.NDArray[np.float64] = np.where(
        symbols == 1, opts.rtty.mark, opts.rtty.space
    )
    modulated_signal: npt.NDArray[np.float64] = sg.square(2 * np.pi * f_array * t_local)

    # Calculate annotation labels
    frame_len = opts.rtty.bits_per_character * samples_per_bit
    frame_starts: npt.NDArray[np.int_] = pre_message_samples + np.round(
        np.arange(N, dtype=np.int_) * frame_len
    ).astype(np.int_)

    start_indices: npt.NDArray[np.int_] = frame_starts
    stop_indices: npt.NDArray[np.int_] = (
        frame_starts
        + int(opts.rtty.bits_per_character - opts.rtty.stop_bits) * opts.nsamp
    )
    data_offsets = np.arange(1, 6, dtype=np.int_) * samples_per_bit + (
        samples_per_bit // 2
    )
    data_indices = (frame_starts[:, None] + data_offsets).flatten()

    # Prepend silence
    silence_len = int(prepend_silence_s * opts.Fs)
    final_signal = np.concat((np.zeros(silence_len), modulated_signal))

    return (
        final_signal,
        np.arange(silence_len + total_samples) / opts.Fs,
        DebugAnnotations(
            start_indices + silence_len,
            stop_indices + silence_len,
            data_indices + silence_len,
        ),
    )

class InternalSignalMsg(msgspec.Struct, frozen=True):
    signal: npt.NDArray[np.float64]
