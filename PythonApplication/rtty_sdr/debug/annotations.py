from dataclasses import dataclass
from typing import Literal
from matplotlib.transforms import Transform
from typing_extensions import Iterable
from matplotlib.axes import Axes
import matplotlib.pyplot as plt
import numpy as np

from rtty_sdr.debug.debug_types import DebugCombineable


def line(
    ax: Axes,
    axis: Literal["x", "y"],
    vals: Iterable[float | int],
    label: str,
    **kwargs,
) -> None:
    for val in vals:
        xval: float
        yval: float
        transform: Transform
        rotation: float
        ha: str
        if axis == "x":
            ax.axvline(x=val, **kwargs)
            xval = val
            yval = 1
            transform = ax.get_xaxis_transform()
            rotation = 90
            ha = "right"
        else:
            ax.axhline(y=val, **kwargs)
            xval = 0
            yval = val
            transform = ax.get_yaxis_transform()
            rotation = 0
            ha = "left"
        ax.text(
            xval,
            yval,
            label,
            color=kwargs.get("color"),
            ha=ha,
            va="top",
            rotation=rotation,
            fontweight="bold",
            transform=transform,
        )


@dataclass
class DebugAnnotations(DebugCombineable):
    start_bits: np.typing.NDArray[np.int_]
    stop_bits: np.typing.NDArray[np.int_]
    data_bits: np.typing.NDArray[np.int_]

    def draw(self, ax: Axes, delay: float = 0, Fs: int | None = None) -> None:
        Fs = Fs if Fs is not None else 1
        starts = np.add(self.start_bits, delay) / Fs
        datas = np.add(self.data_bits, delay) / Fs
        stops = np.add(self.stop_bits, delay) / Fs
        line(ax, "x", starts, "Start", color="r", linestyle="--")
        line(ax, "x", datas, "Data", color="purple", linestyle="--")
        line(ax, "x", stops, "Stop", color="black", linestyle="--")

    @classmethod
    def combine(cls, debugs: Iterable[DebugAnnotations]) -> DebugAnnotations:
        debug_list = list(debugs)

        if not debug_list:
            # Return an empty instance if the iterable is empty
            return cls(np.array([]), np.array([]), np.array([]))
        return cls(
            start_bits=np.concatenate([d.start_bits for d in debugs]),
            stop_bits=np.concatenate([d.stop_bits for d in debugs]),
            data_bits=np.concatenate([d.data_bits for d in debugs]),
        )
