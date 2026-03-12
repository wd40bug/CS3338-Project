clear, clc, close all, clear Baudot, clear decodeBaudot

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

% Decoding
FilterBW = Baud * 1.2;
FilterOrder = 4;
WindowSize = round(nsamp / 10);
AnalyticalSignalOrder = 100;
EnvelopeThreshold = 0.10;
SilentFramesGracePeriod = 20;

reader = audioDeviceReader(Fs, WindowSize);
setup(reader);

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
protocolState = ProtocolState.Length;

bits = zeros(1,5);
chars = [];
index = 1;
silent_frames = 0;
currentBits = 0;
startMode = 'FIGS';

lengthChars = strings(1, 2);
data_length = 0;
dataChars = [];
checksumChars = strings(1,4);
callsignChars = strings(1,5);
charIndex = 1;


%Debugging
allAudioData = [];
first_frame_over_thresh = 0;
start_indicies = [];
data_indicies = [];

decodeBaudot([], 'FIGS');
% while length(chars) < 14 && (silent_frames < SilentFramesGracePeriod || first_frame_over_thresh == 0)
while protocolState ~= ProtocolState.Done
    frame = reader();
    allAudioData = [allAudioData; frame];
    frame_index = index;
    index = index + length(frame);
    markFiltered = bpMark(frame);
    spaceFiltered = bpSpace(frame);

    markMag = abs(envMark(markFiltered));
    spaceMag = abs(envSpace(spaceFiltered));

    diff = markMag - spaceMag;
    envPower = mean(abs(diff).^2);

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
        if first_frame_over_thresh == 0
            first_frame_over_thresh = frame_index;
        end
        silent_frames = 0;
    end


    for i = 1:length(diff)
        sample = diff(i);
        switch state
            case DecodeState.Idle
                if sample < 0
                    state = DecodeState.Data;
                    next_sample = 1.5 * nsamp + frame_index + i;
                    currentBits = 1;
                    start_indicies = [start_indicies, frame_index + i];
                end
            case DecodeState.Data
                if frame_index >= next_sample
                    data_indicies = [data_indicies, frame_index + 1];
                    bits(currentBits) = sample > 0;
                    currentBits = currentBits + 1;
                    next_sample = frame_index + i + nsamp;

                    if currentBits <= 5
                        continue;
                    end
                    c = decodeBaudot(bits);
                    state = DecodeState.Stop;
                    if isempty(c)
                        continue;
                    end
                    fprintf("%s", c);
                    % chars = [chars, c];
                    switch protocolState
                        case ProtocolState.Length
                            isDigit = (c >= '0' && c <= '9');
                            isHex = (c >= 'A' && c <= 'F');
                            if ~isDigit && ~isHex
                                protocolState = ProtocolState.Done;
                                continue;
                            end
                            lengthChars(charIndex) = c;
                            charIndex = charIndex + 1;
                            if charIndex <= 2
                                continue
                            end
                            data_digits = hex2dec(lengthChars);
                            data_length = data_digits(1) * 16 + data_digits(2);
                            if data_length > 0
                                dataChars = strings(1,data_length);
                                protocolState = ProtocolState.Data;
                            else
                                protocolState = ProtocolState.Checksum;
                            end
                            charIndex = 1;
                        case ProtocolState.Data
                            dataChars(charIndex) = c;
                            charIndex = charIndex + 1;
                            if charIndex <= data_length
                                continue;
                            end
                            protocolState = ProtocolState.Checksum;
                            charIndex = 1;
                        case ProtocolState.Checksum
                            checksumChars(charIndex) = c;
                            charIndex = charIndex + 1;
                            if charIndex - 1 < 4
                                continue;
                            end
                            protocolState = ProtocolState.Callsign;
                            charIndex = 1;
                        case ProtocolState.Callsign
                            callsignChars(charIndex) = c;
                            charIndex = charIndex + 1;
                            if charIndex - 1 < 6
                                continue;
                            end
                            protocolState = ProtocolState.Done;
                    end
                end
            case DecodeState.Stop
                if frame_index + i >= next_sample
                    state = DecodeState.Idle;
                end
        end
    end
end
fprintf("\n");

% Decode
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
        'BLANK', 'E', newline, 'A', ' ', 'S', 'I', 'U', ...         % 0 - 7
        char(13), 'D', 'R', 'J', 'N', 'F', 'C', 'K', ...        % 8 - 15
        'T', 'Z', 'L', 'W', 'H', 'Y', 'P', 'Q', ...             % 16 - 23
        'O', 'B', 'G', '', 'M', 'X', 'V', '' ...                % 24 - 31
    };

    figs_map = { ...
        'BLANK', '3', newline, '-', ' ', char(39), '8', '7', ...    % 0 - 7
        char(13), '$', '4', char(7), ',', '!', ':', '(', ...    % 8 - 15
        '5', '"', ')', '2', '#', '6', '0', '1', ...             % 16 - 23
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

%% Figures
if ~isempty(start_indicies)
    first_index = start_indicies(1) - 1000;
else
    first_index = first_frame_over_thresh;
end
signal = allAudioData(first_index:end);
reset(bpMark);
reset(bpSpace);
reset(envMark);
reset(envSpace);
release(envMark);
release(envSpace);
mark_env = abs(envMark(bpMark(signal)));
space_env = abs(envMark(bpSpace(signal)));
diff = mark_env - space_env;

% Envelope
figure;
plot(diff);
xline(start_indicies - first_index, 'r', "Start")
xline(data_indicies - first_index, 'b', "Data")

%% Save
audiowrite("out.wav", signal, Fs);