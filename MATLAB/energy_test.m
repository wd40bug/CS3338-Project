clear, clc, close all
% --- Simplified Parseval's Theorem Proof (No Noise) ---

% 1. Setup Parameters
fs = 16000;              % Sampling frequency (Hz)
N = 1000;               % Number of samples (exactly 1 second)
t = (0:N-1) / fs;       % Time vector
desired_width = 101;
binwidth = 2 * floor(desired_width / 2) + 1;

% 2. Create the Clean Signal (No Noise)
target_freq = 973;
amplitude = 2.0;
signal = amplitude * sin(2 * pi * target_freq * t);

fprintf('--- Power Calculation Comparison ---\n');

% --- TIME DOMAIN CALCULATION ---
% Total power is the mean square of the signal
P_time = mean(signal.^2);
fprintf('Total Power (Time Domain):   %.4f\n', P_time);

% --- FREQUENCY DOMAIN CALCULATION (GOERTZEL) ---
k = round((target_freq / fs) * N + 1);

bins = (1:binwidth) - (binwidth-1) / 2 - 1;
bin_indicies = bins + k;

% Run Goertzel for just the target frequency bin
dft_val = goertzel(signal(:), bin_indicies);

% Calculate power for this single real frequency bin
P_goertzel = 2 * (abs(dft_val).^2) / (N^2);
P_goertzel = sum(P_goertzel);
fprintf('Target Power (Goertzel):     %.4f\n\n', P_goertzel);

% --- PROOF CHECK ---
% Using a small tolerance (1e-10) to account for standard floating-point precision
if abs(P_time - P_goertzel) < 1e-10
    fprintf('SUCCESS: Time domain perfectly matches Goertzel calculation!\n');
else
    fprintf('ERROR: Power mismatch.\n');
end