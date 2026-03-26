import numpy as np


def awgn(signal, snr_db):

    signal_power = np.mean(np.abs(signal) ** 2)

    snr_linear = 10 ** (snr_db / 10.0)

    noise_power = signal_power / snr_linear

    noise_std = np.sqrt(noise_power)

    if np.iscomplexobj(signal):
        noise = np.random.normal(
            0, noise_std / np.sqrt(2), signal.shape
        ) + 1j * np.random.normal(0, noise_std / np.sqrt(2), signal.shape)
    else:
        noise = np.random.normal(0, noise_std, signal.shape)

    noisy_signal = signal + noise
    return noisy_signal
