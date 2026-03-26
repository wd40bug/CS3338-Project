import sys
import numpy as np
import numpy.typing as npt
from matplotlib.axes import Axes
from rtty_sdr.debug.annotations import line
from rtty_sdr.dsp.filters import SosFilter, PeakFilter
import scipy as sc

def plot_freq_response(
    ax: Axes, 
    filt: SosFilter, 
    markers: list[tuple[str, float]] | None = None,
    center_name="Center"
) -> None:
    """Plots the frequency response of an SosFilter on the given Axes."""
    markers = markers or []
    
    if isinstance(filt, PeakFilter):
        markers = [(center_name, filt.center)] + markers

    def to_mag_db(amp: npt.NDArray[np.complex128]) -> npt.NDArray[np.float64]:
        return 20 * np.log10(np.maximum(abs(amp), sys.float_info.epsilon))

    # Plot base response
    f, h = filt.frequency_response()
    ax.plot(f, to_mag_db(h))

    # Plot specific markers
    specific = []
    if markers:
        names, freqs = zip(*markers)
        _, amp = filt.frequency_response(freqs)
        mags = to_mag_db(amp)
        specific = list(zip(names, freqs, mags))

        for i, (name, freq, _) in enumerate(specific):
            color = "r" if i == 0 else "purple"
            line(ax, "x", [freq], name, color=color)

    # Build Title
    title_str = ", ".join(f"{name}: {val:.1f}dB" for name, _, val in specific)
    full_title = f"Frequency response of butterworth filter ({filt})"
    if title_str:
        full_title += f"\n{title_str}"
        
    ax.set_title(full_title)
    ax.set_ylabel("Magnitude (dB)")
    ax.set_xlabel("Frequency (Hz)")
