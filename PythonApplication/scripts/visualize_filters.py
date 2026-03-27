import matplotlib.pyplot as plt
from rtty_sdr.dsp.filters import PeakFilter
from rtty_sdr.debug.filter_response import plot_freq_response

Fs = 8000

BW_total = 2 * 170 + 2 * 45.45
BW_one = 1.2 * 45.45

both = PeakFilter(Fs, (2125 + 2295) / 2, BW_total, 4)
mark = PeakFilter(Fs, 2125, BW_one, 4)
space = PeakFilter(Fs, 2295, BW_one, 4)

fig, ax = plt.subplots()
plot_freq_response(fig.axes[0], both,[("Mark", 2125), ("Space", 2295)])
plt.grid(True)
plt.ylim(top=50)

fig, ax = plt.subplots()
plot_freq_response(fig.axes[0], mark, [("Space", 2295)], center_name="Mark")
plt.grid(True)
plt.ylim(top=50)

fig, ax = plt.subplots()
plot_freq_response(fig.axes[0], space, [("Mark", 2125)], center_name="Space")
plt.grid(True)
plt.ylim(top=50)

plt.show()
