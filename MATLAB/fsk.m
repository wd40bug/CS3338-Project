%% Prelude
clear, clc, close all
Mark = 2125;
Shift = 170;
Space = Mark + Shift;
Baud = 45.45;
M = 2; % Binary FSK
Fc = Mark + Shift / 2;
Fs = 8000;
snr_db = 0;

% SNR
samples = 1000;
%% Generate Signal
function [signal] = RTTY(data, mark, shift, baud, Fs)
    Fc = mark + shift / 2;
    nsamp = round(Fs / baud);
    baseband = fskmod(data, 2, shift, nsamp, Fs, 'discont');
    t = (0:length(baseband)-1)' / Fs;
    % signal = real(baseband .* exp(1j * 2 * pi * Fc * t));
    signal = sign(real(baseband .* exp(1j * 2 * pi * Fc * t)));
end
data = [1;0;1;0;1;0;1;0;1;0];
% data = randi([0 1], 50, 1);
y = RTTY(data, Mark, Shift, Baud, Fs);
%% Spectrum analysis
figure;
pwelch(y, [], [], [], Fs);
title("RTTY signal without noise");
%% Additive White Gaussian Noise
noisySignal = awgn(y, snr_db, 'measured');
%% Analyze noisy
figure;
pwelch(noisySignal, [], [], [], Fs);
title(['RTTY Spectrum with ', num2str(snr_db), ' dB SNR']);
%% Recover
function [recovered] = inverseRTTY(Signal, Mark, Shift, Baud, Fs)
    Fc = Mark + Shift / 2;
    nsamp = round(Fs / Baud);
    t = (0:length(Signal)-1)' / Fs;
    % Downshift
    downshifted = Signal .* exp(-1j * 2 * pi * Fc * t);
    % Demodulate
    recovered = fskdemod(downshifted, 2, Shift, nsamp, Fs);
end
recoveredData = inverseRTTY(noisySignal, Mark, Shift, Baud, Fs);
%% Verify
n = 1:length(data);
figure;

subplot(2,1,1);
stairs(data);
xlabel('Sample Index');
ylabel('Value');
title('Original');
ylim([-0.1, 2]);
xlim([1,length(data)]);
grid on;

subplot(2,1,2);
stairs(recoveredData);
xlabel('Sample Index');
ylabel('Value');
title('Recovered');
ylim([-0.1, 2]);
xlim([1,length(data)]);
grid on;
%% White noise SNR ratio effect
snrs = -50:1:0;
errors_white = zeros(length(snrs), 2);
fprintf("Beginning white noise analysis\n");
parfor i = 1:length(snrs)
    snr = snrs(i);
    data = randi([0 1], samples, 1);
    signal = RTTY(data, Mark, Shift, Baud, Fs);
    noisySignal = awgn(signal, snr, 'measured');
    recovered = inverseRTTY(noisySignal, Mark, Shift, Baud, Fs);
    errors_white(i, :) = [sum((data == 0) & (recovered == 1));sum((data==1) & (recovered==0))];
end
%% Pink noise SNR ratio effect
fprintf("Beginning pink noise analysis\n");
errors_pink = zeros(length(snrs), 2);
function [noisySignal] = pinkNoise(Signal, SNR_db)
    noise = pinknoise(size(Signal), 'like', Signal);
    signalPower = mean(Signal.^2);
    noisePower = mean(noise.^2);
    snr_linear = 10^(SNR_db / 10);
    scale = sqrt(signalPower / (noisePower * snr_linear));
    scaled_noise = noise .* scale;
    noisySignal = scaled_noise + Signal;
end
parfor i = 1:length(snrs)
    snr = snrs(i);
    data = randi([0 1], samples, 1);
    signal = RTTY(data, Mark, Shift, Baud, Fs);
    % Noise
    noisySignal = pinkNoise(signal, snr);
    % Recover
    recovered = inverseRTTY(noisySignal, Mark, Shift, Baud, Fs);
    errors_pink(i, :) = [sum((data == 0) & (recovered == 1));sum((data==1) & (recovered==0))];
end
%% Plot
figure;
errors_percent_white = errors_white / samples * 100;
bar(snrs, errors_percent_white, 'stacked');
title("White noise SNR biterr%");
ylabel("Biterr %");
xlabel("SNR (dB)");
legend("0 to 1 errors", "1 to 0 errors");
figure;
errors_percent_pink = errors_pink / samples * 100;
bar(snrs, errors_percent_pink', 'stacked');
title("Pink noise SNR biterr%");
ylabel("Biterr %");
xlabel("SNR (dB)");
legend("0 to 1 errors", "1 to 0 errors");
%% Resolution
resolutions = 1:1:16;

signal_min = -1;
signal_max = 1;
resolution_errors_white = zeros(1, length(resolutions) * length(snrs));
resolution_errors_pink = zeros(1, length(resolutions) * length(snrs));
parfor k = 1:length(resolutions) * length(snrs)
    [i,j] = ind2sub([length(resolutions), length(snrs)], k);
    resolution = resolutions(i);
    snr = snrs(j);
    data = randi([0 1], samples, 1);
    signal = RTTY(data, Mark, Shift, Baud, Fs);
    % Noise
    white_noisy = awgn(signal, snr, 'measured');
    pink_noisy = pinkNoise(signal, snr);
    % Clip
    white_noisy = clip(white_noisy, signal_min+eps, signal_max-eps);
    pink_noisy = clip(pink_noisy, signal_min+eps, signal_max-eps);
    % Quantize
    warning('off', 'fixed:fi:overflow');
    q = quantizer('fixed', 'floor', 'saturate', [resolution resolution]);
    white_noisy = quantize(q,white_noisy);
    pink_noisy = quantize(q,pink_noisy);
    % Recover
    recovered_white = inverseRTTY(white_noisy, Mark, Shift, Baud, Fs);
    recovered_pink = inverseRTTY(pink_noisy, Mark, Shift, Baud, Fs);
    % Error rates
    resolution_errors_white(k) = biterr(data, recovered_white) / samples * 100;
    resolution_errors_pink(k) = biterr(data, recovered_pink) / samples * 100;
end
resolution_errors_white = reshape(resolution_errors_white, [length(resolutions), length(snrs)]);
resolution_errors_pink = reshape(resolution_errors_pink, [length(resolutions), length(snrs)]);
function graph_helper1(white,pink, y, x, ytitle, yunit, xtitle, xunit)
    mainMap = flipud(autumn(255));
    customMap = [0 1 0; mainMap];
    figure;
    ax1 = subplot(1,2,1);
    imagesc(x, y, white);
    set(gca, 'YDir', 'normal');
    c = colorbar;
    colormap(customMap);
    title(sprintf("Biterr%%\n vs %s and %s (White Noise)", ytitle, xtitle));
    ylabel(c, 'Bit Errors (%)', 'FontSize', 12, 'Rotation', 270, 'VerticalAlignment', 'bottom');
    ylabel(sprintf("%s (%s)", ytitle, yunit));
    xlabel(sprintf("%s (%s)", xtitle, xunit));
    ax2 = subplot(1,2,2);
    imagesc(x, y, pink);
    set(gca, 'YDir', 'normal');
    c = colorbar;
    colormap(customMap);
    title(sprintf("Biterr%%\n vs %s and %s (Pink Noise)", ytitle, xtitle));
    ylabel(c, 'Bit Errors (%)', 'FontSize', 12, 'Rotation', 270, 'VerticalAlignment', 'bottom');
    ylabel(sprintf("%s (%s)", ytitle, yunit));
    xlabel(sprintf("%s (%s)", xtitle, xunit));
    linkprop([ax1, ax2], 'CLim');
    linkaxes([ax1, ax2], 'x');
    linkaxes([ax1, ax2], 'y');
end
graph_helper1(resolution_errors_white, resolution_errors_pink, resolutions, snrs, "Resolution", "bit", "SNR", "dB");
%% Sampling Rate and Baud

% graph_helper1(resolutions, resolution_errors, samples, snr_db, "Resolution");
% Returns a row matrix of the following form
% [
% white 0->1,
% white 1->0,
% pink  0->1,
% pink  1->0
%]
function [white, pink] = run_with_params(Mark, Shift, Baud, Samples, sampling_rate, snr_db)
    data = randi([0 1], Samples, 1);
    signal = RTTY(data, Mark, Shift, Baud, sampling_rate);
    % Noise
    white_noisy = awgn(signal, snr_db, 'measured');
    pink_noisy = pinkNoise(signal, snr_db);
    % Recover
    recovered_white = inverseRTTY(white_noisy, Mark, Shift, Baud, sampling_rate);
    recovered_pink = inverseRTTY(pink_noisy, Mark, Shift, Baud, sampling_rate);
    % Error rates
    white = biterr(data, recovered_white);
    pink = biterr(data, recovered_pink);
end
% Sampling
sampling_rates = Space*2:5000:100000;
sampling_errors_white = zeros(1, length(sampling_rates) * length(snrs));
sampling_errors_pink = zeros(1, length(sampling_rates) * length(snrs));
parfor k = 1:length(sampling_rates) * length(snrs)
    [i,j] = ind2sub([length(sampling_rates), length(snrs)], k);
    sampling_rate = sampling_rates(i);
    snr = snrs(j);
    [sampling_errors_white(k),sampling_errors_pink(k)] = run_with_params(Mark, Shift, Baud, samples, sampling_rate, snr);
end
sampling_errors_white = reshape(sampling_errors_white, [length(sampling_rates), length(snrs)]);
sampling_errors_pink = reshape(sampling_errors_pink, [length(sampling_rates), length(snrs)]);
graph_helper1(sampling_errors_white, sampling_errors_pink, sampling_rates, snrs, "Sampling Rate", "Hz", "SNR", "dB");
% Baud
baud_rates = 1:1:200;
baud_errors_white = zeros(1, length(baud_rates) * length(snrs));
baud_errors_pink = zeros(1, length(baud_rates) * length(snrs));
parfor k = 1:length(baud_rates) * length(snrs)
    [i,j] = ind2sub([length(baud_rates), length(snrs)], k);
    baud_rate = baud_rates(i);
    snr = snrs(j);
    [baud_errors_white(k), baud_errors_pink(k)] = run_with_params(Mark, Shift, baud_rate, samples, Fs, snr);
end
baud_errors_white = reshape(baud_errors_white, [length(baud_rates), length(snrs)]);
baud_errors_pink = reshape(baud_errors_pink, [length(baud_rates), length(snrs)]);
graph_helper1(baud_errors_white, baud_errors_pink, baud_rates, snrs, "Baud Rate", "baud", "SNR", "dB");