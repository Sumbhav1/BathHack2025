# main.py
import pyaudio
import numpy as np
import librosa
import time
import os

# Constants
FORMAT = pyaudio.paInt16  # Audio format (16-bit integers)
CHANNELS = 1             # Number of audio channels (mono)
RATE = 44100             # Sample rate (samples per second)
CHUNK = 1024             # Size of audio chunks (frames per buffer)
RECORD_SECONDS = 5       # Duration to record audio

# Initialize PyAudio
audio = pyaudio.PyAudio()

# Open audio stream
stream = audio.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

print("Recording...")

frames = []

# Record audio in chunks
for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
    try:
        data = stream.read(CHUNK, exception_on_overflow=False) # Read audio chunk
        frames.append(data)                                    # Append chunk to frames list
    except Exception as e:
        print(f"Error reading stream: {e}")
        break


print("Finished recording.")

# Stop and close the stream
stream.stop_stream()
stream.close()
audio.terminate()

# Convert frames to numpy array (example for further processing)
if frames:
    audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
    print(f"Audio data shape: {audio_data.shape}")
    
    # Normalize audio data to float32 range [-1, 1]
    audio_data = audio_data.astype(np.float32) / np.iinfo(np.int16).max
    
    # --- Extract Core Features for Pop Detection ---
    
    # 1. RMS Energy
    rms = librosa.feature.rms(y=audio_data)[0]
    print(f"RMS Energy shape: {rms.shape}")
    
    # 2. Zero Crossing Rate
    zcr = librosa.feature.zero_crossing_rate(audio_data)[0]
    print(f"Zero Crossing Rate shape: {zcr.shape}")
    
    # 3. Onset Strength Envelope
    onset_env = librosa.onset.onset_strength(y=audio_data, sr=RATE)
    print(f"Onset Strength Envelope shape: {onset_env.shape}")
    
    # (Optional: Keep onset detection if needed for labeling/evaluation later)
    # onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=RATE)
    # print(f"Number of onsets detected: {len(onsets)}") 
    
    # --- Align and Combine Features for AI Model ---
    
    # Find the minimum length among the features
    min_len = min(len(rms), len(zcr), len(onset_env))
    
    # Truncate features to the minimum length
    rms = rms[:min_len]
    zcr = zcr[:min_len]
    onset_env = onset_env[:min_len]
    
    # Stack features into a single matrix (frames x features)
    feature_matrix = np.vstack([rms, zcr, onset_env]).T
    
    print(f"Combined feature matrix shape: {feature_matrix.shape}") 
    
    # Save the feature matrix to a file
    save_path = os.path.join(os.path.expanduser('~'), 'Documents', 'audio_features.npy')
    os.makedirs(os.path.dirname(save_path), exist_ok=True)  # Ensure directory exists
    np.save(save_path, feature_matrix)
    print(f"Feature matrix saved to '{save_path}'")

else:
    print("No audio data recorded.")

# --- Placeholder for PySimpleGUI ---
# import PySimpleGUI as sg
# layout = [ [sg.Text("Audio Analysis Dashboard")],
#            [sg.Button("Exit")] ]
# window = sg.Window("Wavetool Clone", layout)
# while True:
#     event, values = window.read()
#     if event == sg.WIN_CLOSED or event == 'Exit':
#         break
# window.close()
