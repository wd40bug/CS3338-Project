clear, clc, close all, clear Baudot
% Generate RTTY
function [signal] = RTTY_char(data, mark, shift, baud, Fs, stop_len, first)
    data = [0; data];
    Fc = mark + shift / 2;
    nsamp = round(Fs / baud);
    data_inverse = double(data == 0);
    baseband = fskmod(data_inverse, 2, shift, nsamp, Fs, 'discont');
    t = (0:length(baseband)-1)' / Fs;
    % signal = real(baseband .* exp(1j * 2 * pi * Fc * t));
    rtty_signal = sign(real(baseband .* exp(1j * 2 * pi * Fc * t)));
    n_stop = (0:nsamp * stop_len);
    stop = sign(cos(2 * pi * mark * n_stop / Fs))';
    if first
        signal = [stop; rtty_signal; stop];
    else
        signal = [rtty_signal; stop];
    end

end

function [bits] = Baudot(c)
    persistent is_letter;
    persistent letter_map;
    persistent figs_map;
    if isempty(is_letter)
        NL = newline;
        CR = char(13);
        is_letter = true;

        letter_map = containers.Map(...
            {'A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z',' ',NL,CR}, ...
            [ 3, 25, 14,  9,  1, 13, 26, 20,  6, 11, 15, 18, 28, 12, 24, 22, 23, 10,  5, 16,  7, 30, 19, 29, 21, 17,  4,  2, 8]);

        figs_map = containers.Map(...
            {'-','?',':','$','3','!','&','#','8','4','(',')','.',',','9','0','1','''','5','7',';','2','/','6','"',' ',NL,CR}, ...
            [ 3, 25, 14,  9,  1, 13, 26, 20,  6, 11, 15, 18, 28, 12, 24, 22,  23, 10, 16,  7, 30, 19, 29, 21, 17,  4,  2, 8]);
    end

    c = upper(c);

    % Special Shift Codes
    LTRS = '11111'; % 31
    FIGS = '11011'; % 27

    shift_str = '';

    if is_letter
        if isKey(letter_map, c)
            code = letter_map(c);
        elseif isKey(figs_map, c)
            is_letter = false;
            shift_str = FIGS;
            code = figs_map(c);
        else
            error("Character '%s' not supported", c);
        end
    else
        if isKey(figs_map, c)
            code = figs_map(c);
        elseif isKey(letter_map, c)
            is_letter = true;
            shift_str = LTRS;
            code = letter_map(c);
        else
            error("Character '%s' not supported", c);
        end
    end

    if ~isempty(shift_str)
        shift_str = ['0', shift_str, '1'];
    end
    code = [dec2bin(code, 5)];
    

    bits = [shift_str, code] == '1';
    bits = double(bits');
end

%% Example signal
Fs = 10000;
Baud = 10;
Mark = 50;
Shift = 50;
StopLen = 2;

message = sprintf('HI');
codes = arrayfun(@Baudot, message, UniformOutput=false)';
signal = [];
for i = 1:length(codes)
    first = i == 1;
    signal = [signal; RTTY_char(codes{i}, Mark, Shift, Baud, Fs, StopLen, first)];
end

%% Graph
figure;
plot(signal);
xline(2000, 'm', "Start", "LineWidth",2, FontSize=16);
xline(3500:1000:7500, 'r', "Data Bit", "LineWidth",2, FontSize=16);
xline(8000, 'b',"Stop", "LineWidth",2, FontSize=16);
xline(10000, 'm', "Start", "LineWidth",2, FontSize=16);
xline(11500:1000:15500, 'r', "Data Bit", "LineWidth",2, FontSize=16);
xline(16000, 'b', "Stop", "LineWidth",2, FontSize=16);
ylim([-1 1.3]);
title(...
    sprintf("RTTY Signal with Mark: %dHz, Space: %dHz, Baud: %d/s, Fs: %dHz",...
    Mark, Mark + Shift, Baud, Fs));
xlabel("Index");
ylabel("Amplitude")

%% More realistic signal
Fs = 10000;
Baud = 45.45;
Mark = 2125;
Shift = 170;
StopLen = 2;

message = sprintf('HI');
codes = arrayfun(@Baudot, message, UniformOutput=false)';
signal = [];
for i = 1:length(codes)
    first = i == 1;
    signal = [signal; RTTY_char(codes{i}, Mark, Shift, Baud, Fs, StopLen, first)];
end

%% Graph
figure;
stft(signal, Fs, 'Window', kaiser(256, 5), 'OverlapLength', 220, 'FFTLength', 512);
ylim([2 2.5])
StopTime = StopLen / Baud * 1000;
bitTime = 1/Baud * 1000;

starts = (0:bitTime * 6 + StopTime:length(codes) * (bitTime * 5 + StopTime)) + StopTime;
data_bits = (0:bitTime:bitTime * 4) + 1.5 * bitTime;
stops = starts + bitTime * 6;

xline(starts, 'm', "Start", LineWidth=2, FontSize=16);
xline(data_bits + starts(1), 'r', "Data Bit", LineWidth=2, FontSize=16 );
xline(data_bits + starts(2), 'r', "Data Bit", LineWidth=2, FontSize=16 );
xline(stops, 'b', "Stop", LineWidth=2, FontSize=16);
% xline(StopTime + 5 * bitTime, 'b', 'Stop', LineWidth=2, FontSize=16);