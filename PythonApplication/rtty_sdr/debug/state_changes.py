from enum import Enum
from typing import TypeVar, Final
import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt

from matplotlib.axes import Axes


class StateChanges[T]:
    def __init__(self, default: T):
        self.__state_changes = {0: default}
        self.__first = 0

    def change(self, index: int, state: T):
        assert index not in self.__state_changes
        self.__state_changes[index] = state

    def build(self, index: int, default: T) -> list[T]:
        first_state = self.__state_changes[self.__first]
        assert first_state is not None

        curr: T = first_state
        ret: list[T] = [
            (curr := self.__state_changes.get(i, curr))
            for i in range(self.__first, index + 1)
        ]

        self.__first = index + 1
        self.__state_changes[index + 1] = default
        return ret

def get_colors_from_colormap(n, colormap='viridis'):
    cmap = plt.get_cmap(colormap)
    colors = []
    for i in range(n):
        # Sample colors evenly from the colormap's range
        color = cmap(i / n)
        colors.append(color[:3]) # Get RGB values, ignore alpha
    return colors

T = TypeVar("T", bound=Enum)


def graph_states(t: npt.NDArray[np.float64], ax: Axes, states: list[T]):
    if not states:
        return
    states_np = np.array(states)
    enum_class: Final = states[0].__class__
    colors = get_colors_from_colormap(len(enum_class))
    for member, color in zip(enum_class, colors):
        ax.fill_between(
            t,
            0,
            1,
            where=(states_np == member),
            color=color,
            alpha=0.4,
            label=member.name,
            transform=ax.get_xaxis_transform(),
        )
