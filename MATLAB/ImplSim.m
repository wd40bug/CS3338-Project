clear, clc, close all, clear Baudot

% Consts
Fs = 8000;
Mark = 2125;
Shift = 170;
Baud = 45.45;
StopLen = 1;
CharLen = 5;

% Derived
Space = Mark + Shift;
nsamp = Fs / Baud;

% Signal
message = sprintf('Hi');
pre_message_silence_duration = 0.01;
pre_message_no_send_duration = 0.5;
Squelsh = 0.8;

% Decoding
FilterBW = Baud * 1.2;
FilterOrder = 4;
WindowSize = round(nsamp / 10);
AnalyticalSignalOrder = 100;
EnvelopeThreshold = 0.50;
SilentFramesGracePeriod = 5;


%% Signal Creation

% Generate RTTY
function [signal] = RTTY(data, mark, shift, baud, Fs)
    Fc = mark + shift / 2;
    nsamp = round(Fs / baud);
    data_inverse = double(data == 0);
    baseband = fskmod(data_inverse, 2, shift, nsamp, Fs, 'discont');
    t = (0:length(baseband)-1)' / Fs;
    % signal = real(baseband .* exp(1j * 2 * pi * Fc * t));
    signal = sign(real(baseband .* exp(1j * 2 * pi * Fc * t)));
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
    code = ['0', dec2bin(code, 5), '1'];
    

    bits = [shift_str, code] == '1';
    bits = double(bits');
end

codes = arrayfun(@Baudot, message, UniformOutput=false);
bits = vertcat(codes{:});
bits = [1; bits];
disp(bits);

message_rtty = RTTY(bits, Mark, Shift, Baud, Fs);
signal = [zeros(pre_message_silence_duration * Fs, 1); message_rtty];
%% Add noise
signal = awgn(signal, 5, 'measured');

%% Decode signal

function [recovered] = inverseRTTY(Signal, Mark, Shift, Baud, Fs)
    Fc = Mark + Shift / 2;
    nsamp = round(Fs / Baud);
    t = (0:length(Signal)-1)' / Fs;
    % Downshift
    downshifted = Signal .* exp(-1j * 2 * pi * Fc * t);
    % Pad
    rem = mod(length(downshifted), nsamp);
    padded = [downshifted;zeros(nsamp - rem, 1)];
    % Demodulate
    recovered = fskdemod(padded, 2, Shift, nsamp, Fs);
end

reader = dsp.SignalSource(signal, 'SamplesPerFrame', WindowSize);

% Filters
% Design 4th-order Butterworth bandpass filters 
% (Note: butter(2,...) creates a 4th-order bandpass filter)

% --- Mark Filter Setup ---
[zMark, pMark, kMark] = butter(2, [Mark-50, Mark+50]/(Fs/2), 'bandpass');
[sosMark, gMark] = zp2sos(zMark, pMark, kMark);
bpMark = dsp.BiquadFilter('SOSMatrix', sosMark, 'ScaleValues', gMark);

% --- Space Filter Setup ---
[zSpace, pSpace, kSpace] = butter(2, [Space-50, Space+50]/(Fs/2), 'bandpass');
[sosSpace, gSpace] = zp2sos(zSpace, pSpace, kSpace);
bpSpace = dsp.BiquadFilter('SOSMatrix', sosSpace, 'ScaleValues', gSpace);

% Envelope Detectors
envMark = dsp.AnalyticSignal(AnalyticalSignalOrder);
envSpace = dsp.AnalyticSignal(AnalyticalSignalOrder);

% State machine variables
state = DecodeState.Idle;

symbolSampleCounter = 0;
bits = [];
index = 1;
silent_frames = 0;
currentBits = 0;

% Debugging
indicies = [];
index_of_envelope_abs = 0;
start_bits = [];
reads = [];
diff_powers = [];
diff_means = [];

while ~isDone(reader)
    frame = reader();
    frame_index = index;
    index = index + length(frame);
    markFiltered = bpMark(frame);
    spaceFiltered = bpSpace(frame);

    markMag = abs(envMark(markFiltered));
    spaceMag = abs(envSpace(spaceFiltered));

    diff = markMag - spaceMag;
    diffPower = mean(diff.^2);

    diff_powers = [diff_powers, diffPower];
    diff_means = [diff_means, mean(diff)];
    indicies = [indicies, frame_index];

    % Squelch
    if abs(mean(diff)) <= EnvelopeThreshold
        if silent_frames < SilentFramesGracePeriod
            silent_frames = silent_frames + 1;
        else
            % Reset state machine
            state = DecodeState.Idle;
            protocolState = ProtocolState.Length;
            fprintf("Lost signal at %d\n", frame_index);
        end
        continue;
    else
        if index_of_envelope_abs == 0
            index_of_envelope_abs = frame_index;
        end
        silent_frames = 0;
    end


    for i = 1:length(diff)
        sample = diff(i);
        switch state
            case DecodeState.Idle
                if sample < 0
                    fprintf("Detected start bit at %d\n", frame_index + i - 1);
                    start_bits = [start_bits, frame_index + i - 1];
                    state = DecodeState.Data;
                    next_sample = 1.5 * nsamp + frame_index + i;
                    currentBits = 0;
                end
            case DecodeState.Data
                if frame_index + i >= next_sample
                    reads = [reads, frame_index];
                    bits = [bits, sample > 0];
                    currentBits = currentBits + 1;
                    next_sample = frame_index + i + nsamp;

                    if currentBits == 5
                        disp(bits(end-5 + 1:end));
                        state = DecodeState.Stop;
                    end
                end
            case DecodeState.Stop
                if frame_index + i >= next_sample
                    state = DecodeState.Idle;
                end
        end
    end

end
%% Plot stuff
reset(bpMark);
reset(bpSpace);
reset(envMark);
reset(envSpace);
release(envMark);
release(envSpace);
mark_env = abs(envMark(bpMark(signal)));
space_env = abs(envMark(bpSpace(signal)));
diff = mark_env - space_env;
% Plot envelope
figure;
plot(diff);
title("Difference envelope (Mark - Space)")
ylabel("Amplitude")
xlabel("Index")
% With Threshold
figure;
plot(indicies, diff_means, '--o');
title("Difference envelope (Mark - Space) frame means with threshold lines")
ylabel("Amplitude")
xlabel("Index")
yline([EnvelopeThreshold, -EnvelopeThreshold], 'black', 'Threshold', 'LineWidth',2);
xline(index_of_envelope_abs, 'r', 'Signal detected', 'LineWidth', 2, 'LabelVerticalAlignment','bottom');
% With Data lines
figure;
plot(diff);
title("Difference envelope (Mark - Space) with data lines")
ylabel("Amplitude")
xlabel("Index")
xline(start_bits, 'r', "Start bit", 'LineWidth',2, 'FontSize',12, 'LabelVerticalAlignment','bottom');
xline(reads, 'b', "Data bit", 'LineWidth',2, 'FontSize',12, 'LabelVerticalAlignment','bottom');

%% Decode
function decodedText = decodeBaudot(bits, forceState)
    % DECODEBAUDOT Converts a list of bits into Baudot (ITA2) characters.
    %
    % Usage:
    %   text = decodeBaudot(bits)
    %   text = decodeBaudot(bits, 'LTRS') % Forces Letters state before decoding
    %   text = decodeBaudot(bits, 'FIGS') % Forces Figures state before decoding
    %
    % Inputs:
    %   bits       - A vector of 1s and 0s. Length should be a multiple of 5.
    %                (Evaluates 5-bit chunks with the first bit as the MSB).
    %   forceState - (Optional) String 'LTRS' or 'FIGS' to set current state.
    
    % Track state across multiple function calls
    persistent state;
    if isempty(state)
        state = 'LTRS'; % Default to Letters mode
    end
    
    % Handle optional state override
    if nargin > 1 && ~isempty(forceState)
        if strcmpi(forceState, 'LTRS') || strcmpi(forceState, 'FIGS')
            state = upper(forceState);
        else
            error('forceState must be either ''LTRS'' or ''FIGS''.');
        end
    end
    
    % If no bits were provided (e.g., user just wanted to set the state), exit
    if nargin == 0 || isempty(bits)
        decodedText = '';
        return;
    end
    
    % Ensure bits is a horizontal vector
    bits = bits(:)';
    
    % Pad with zeros if length is not a multiple of 5
    remBits = mod(length(bits), 5);
    if remBits ~= 0
        error('Length must be a multiple of 5, found %d', length(bits));
    end
    
    % Reshape into an N-by-5 matrix where each row is a character
    num_chars = length(bits) / 5;
    bit_matrix = reshape(bits, 5, num_chars)';
    
    % Convert 5-bit arrays to decimal (assuming MSB first)
    % e.g., [0 0 0 1 1] -> 0*16 + 0*8 + 0*4 + 1*2 + 1*1 = 3
    vals = bit_matrix * [16; 8; 4; 2; 1];
    
    % Define the ITA2 Character Maps (1-based index means index = value + 1)
    % Index 28 (val 27) is FIGS, Index 32 (val 31) is LTRS
    ltrs_map = { ...
        '', 'E', char(10), 'A', ' ', 'S', 'I', 'U', ...         % 0 - 7
        char(13), 'D', 'R', 'J', 'N', 'F', 'C', 'K', ...        % 8 - 15
        'T', 'Z', 'L', 'W', 'H', 'Y', 'P', 'Q', ...             % 16 - 23
        'O', 'B', 'G', '', 'M', 'X', 'V', '' ...                % 24 - 31
    };

    figs_map = { ...
        '', '3', char(10), '-', ' ', char(39), '8', '7', ...    % 0 - 7
        char(13), '$', '4', char(7), ',', '!', ':', '(', ...    % 8 - 15
        '5', '+', ')', '2', '#', '6', '0', '1', ...             % 16 - 23
        '9', '?', '&', '', '.', '/', ';', '' ...                % 24 - 31
    };

    % Decode the characters
    decodedText = '';
    for i = 1:num_chars
        val = vals(i);
        
        if val == 31
            state = 'LTRS';     % Shift to Letters
        elseif val == 27
            state = 'FIGS';     % Shift to Figures
        elseif val == 0
            continue;           % Null character, ignore
        else
            if strcmp(state, 'LTRS')
                decodedText = [decodedText, ltrs_map{val + 1}]; %#ok<AGROW>
            else
                decodedText = [decodedText, figs_map{val + 1}]; %#ok<AGROW>
            end
        end
    end
end
disp(decodeBaudot(bits));