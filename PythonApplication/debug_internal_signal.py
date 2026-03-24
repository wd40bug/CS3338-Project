import scipy.signal as sg
import numpy as np
import numpy.typing as npt
from RTTY_options import RTTYOpts
from debug_annotations import DebugAnnotations

dtype = np.float32

def time_to_index(start, end, Fs) -> npt.NDArray[dtype]:
    return np.arange(start, end, 1 / Fs)

def index_to_time(start, end, Fs) -> npt.NDArray[dtype]:
    return np.arange(start, end) / Fs

# TODO: make closer to actualy signal generation
def internal_signal(
    message: list[int], Fs: int, opts: RTTYOpts
) -> tuple[npt.NDArray[dtype], npt.NDArray[dtype], DebugAnnotations]:

    start_bits = []
    stop_bits = []
    data_bits = []

    t = time_to_index(0, opts.seconds_per_bit, Fs)
    signal0 = sg.square(2 * np.pi * opts.space * t)
    signal1 = sg.square(np.sin(2 * np.pi * opts.mark * t))

    t_stop = time_to_index(
        0, opts.seconds_per_bit * opts.stop_bits, Fs
    )
    signal_stop = sg.square(2 * np.pi * opts.mark * t_stop)

    signal = np.array([])

    # Pre message bits
    t_pre_message = time_to_index(
        0,
        opts.seconds_per_bit * opts.pre_msg_stops,
        Fs
    )
    signal = np.concat((signal, sg.square(2 * np.pi * opts.mark * t_pre_message)))

    # Characters
    for char in message:
        # Start bit
        start_bits.append(len(signal))
        signal = np.concat((signal, signal0))
        # Data bits
        for i in reversed(range(0, opts.data_bits)):
            bit = char >> i & 1
            data_bits.append(len(signal) + opts.nsamp(Fs) // 2)
            signal = np.concat((signal, signal1 if bit else signal0))
        stop_bits.append(len(signal))
        signal = np.concat((signal, signal_stop))
    return (
        signal,
        index_to_time(0, len(signal), Fs),
        DebugAnnotations(start_bits, stop_bits, data_bits),
    )
