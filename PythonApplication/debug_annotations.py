from dataclasses import dataclass
from typing import Literal
from matplotlib.axes import Axes
import matplotlib.pyplot as plt


@dataclass
class DebugAnnotations:
    start_bits: list[int]
    stop_bits: list[int]
    data_bits: list[int]

    @staticmethod
    def __draw_all(
        ax: Axes,
        axis: Literal["x", "y"],
        vals: list[float] | list[int],
        label: str,
        Fs: int | None = None,
        **kwargs,
    ) -> None:
        if Fs is not None:
            vals = [ val / Fs for val in vals ];
        for val in vals:
            if axis == "x":
                ax.axvline(x=val, **kwargs)
                ax.text(
                    val,
                    1,
                    label,
                    color=kwargs["color"],
                    ha="right",
                    va="top",
                    rotation=90,
                    fontweight='bold',
                    transform=plt.gca().get_xaxis_transform(),
                )
            else:
                ax.axhline(y=val, **kwargs)

    def draw(self, ax: Axes, Fs: int | None = None) -> None:
        self.__draw_all(ax, "x", self.start_bits, "Start Bit", Fs, color="r", linestyle="--")
        self.__draw_all(ax, 'x', self.data_bits, "Data", Fs, color='purple', linestyle="--")
        self.__draw_all(ax, 'x', self.stop_bits, "Stop", Fs, color='black', linestyle="--")
