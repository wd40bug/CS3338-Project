import matplotlib.pyplot as plt
from rtty_sdr.dsp.filters import LowPassFilter, PeakFilter
from rtty_sdr.debug.filter_response import plot_freq_response

Fs = 8000

BW_total = 170 + 45.45
BW_one = 1.2 * 45.45

both = PeakFilter(Fs, (2125 + 2295) / 2, BW_total, 4)
mark = PeakFilter(Fs, 2125, BW_one, 4)
space = PeakFilter(Fs, 2295, BW_one, 4)
envelope = LowPassFilter(Fs, 45.45 * 1.5, 4)

fig, ax = plt.subplots()
plot_freq_response(fig.axes[0], both,[("Mark", 2125), ("Space", 2295)])
plt.grid(True)
plt.ylim(top=50)



fig, axs = plt.subplots(2, 1)
plot_freq_response(axs[0], mark, [("Space", 2295)], center_name="Mark")
axs[0].grid(True)
axs[0].set_ylim(top=50)

plot_freq_response(axs[1], space, [("Mark", 2125)], center_name="Space")
axs[1].grid(True)
axs[1].set_ylim(top=50)

fig, ax = plt.subplots()
plot_freq_response(ax, envelope, [("Cutoff", 45.45 * 1.5)])
plt.grid(True)
plt.xlim((0, 500))
plt.ylim(bottom=-100)

plt.show()
