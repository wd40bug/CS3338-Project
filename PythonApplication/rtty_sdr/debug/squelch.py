from matplotlib.axes import Axes
import numpy as np
import numpy.typing as npt


def plot_shaded_squelch(x: npt.NDArray[np.float64], ax: Axes, squelch: npt.NDArray[np.int_]):
    ax.fill_between(
        x,
        ax.get_ylim()[0],
        ax.get_ylim()[1],
        where=(squelch==1),
        color='black',
        alpha=0.2,
        label="Squelched region"
    )
