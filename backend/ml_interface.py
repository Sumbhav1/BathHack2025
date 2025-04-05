import time
import numpy as np
import librosa
import os # Added for path manipulation
from datetime import datetime # Added for unique filenames
import librosa.onset # Explicitly import if needed, though librosa.feature.onset should work
from joblib import load
import random

# Constants
RATE = 16000  # New Sample rate (Hz) - MUST MATCH audio_handler.py
BUFFER_DURATION_SECONDS = 2  # New Duration to buffer audio before processing (seconds)
TARGET_SAMPLES = int(BUFFER_DURATION_SECONDS * RATE)
ml_model = load('ML_MODEL/audio_popping_classifier_model.joblib') #Load ML model

# Ensure the temporary directory exists
TEMP_FEATURE_DIR = os.path.join(os.path.dirname(__file__), '..', 'temp', 'ml_features')
os.makedirs(TEMP_FEATURE_DIR, exist_ok=True)

def extract_features_from_chunk(audio_chunk, sr):
    """
    Extracts RMS, ZCR, Onset Strength, Spectral Centroid, and Spectral Flatness from an audio chunk.

    Args:
        audio_chunk (np.ndarray): The 1D audio data (should be normalized if desired).
        sr (int): The sample rate.

    Returns:
        np.ndarray: A 2D numpy array (num_frames, 5) where each row represents a time frame
                    and columns represent different features.
                    Features (columns): [RMS, ZCR, Onset Strength, Spectral Centroid, Spectral Flatness]
                    Returns None if an error occurs or the chunk is too short.
    """
    try:
        # Define consistent analysis parameters
        n_fft = 2048
        hop_length = 512 # Default hop_length for many librosa features

        # Check if audio chunk is long enough for FFT
        if len(audio_chunk) < n_fft:
            print(f"Warning: Audio chunk length ({len(audio_chunk)}) is shorter than n_fft ({n_fft}). Skipping feature extraction.")
            return None

        # 1. RMS Energy (returns shape (1, n_frames), get [0] for 1D)
        rms = librosa.feature.rms(y=audio_chunk, frame_length=n_fft, hop_length=hop_length)[0]

        # 2. Zero-Crossing Rate (returns shape (1, n_frames), get [0] for 1D)
        zcr = librosa.feature.zero_crossing_rate(y=audio_chunk, frame_length=n_fft, hop_length=hop_length)[0]

        # 3. Onset Strength (returns 1D array)
        onset_strength = librosa.onset.onset_strength(y=audio_chunk, sr=sr, hop_length=hop_length)

        # 4. Spectral Centroid (returns shape (1, n_frames), get [0] for 1D)
        spectral_centroid = librosa.feature.spectral_centroid(y=audio_chunk, sr=sr, n_fft=n_fft, hop_length=hop_length)[0]

        # 5. Spectral Flatness (returns shape (1, n_frames), get [0] for 1D)
        spectral_flatness = librosa.feature.spectral_flatness(y=audio_chunk, n_fft=n_fft, hop_length=hop_length)[0]

        # Ensure all features have the same number of frames (columns)
        # Use the length of RMS as the target, as it's usually consistent
        target_frames = rms.shape[0]

        # Resize other features if necessary (simple resize, might truncate/repeat)
        onset_strength = np.resize(onset_strength, target_frames)
        spectral_centroid = np.resize(spectral_centroid, target_frames)
        spectral_flatness = np.resize(spectral_flatness, target_frames)
        zcr = np.resize(zcr, target_frames) # Also resize ZCR just in case

        # Stack the 1D feature arrays vertically to create the 2D matrix (5, num_frames)
        features = np.vstack((rms, zcr, onset_strength, spectral_centroid, spectral_flatness))

        # Transpose the matrix to shape (num_frames, 5)
        features = features.T

        # Verify shape is (N, 5)
        if features.shape[1] != 5:
             print(f"Error: Feature matrix has unexpected shape: {features.shape}")
             return None # Or raise an error

        return features

    except Exception as e:
        print(f"Error extracting features: {e}")
        return None


# Modified function signature to include source_id
def buffer_and_analyze_audio(source_id, ml_input_queue, ml_output_queue, warning_queue):
    """
    Buffers audio chunks for a specific source, extracts features, interacts with ML model,
    and sends tagged warnings.

    Args:
        source_id: An identifier for the audio source (e.g., (device_index, channel_index)).
        ml_input_queue: Queue to receive audio chunks for this source.
        ml_output_queue: Queue for potential ML output (currently unused).
        warning_queue: Shared queue to put tagged warnings (source_id, message).
    """
    print(f"ML Interface [{source_id}]: Starting... Buffering for {BUFFER_DURATION_SECONDS} seconds.")
    # Placeholder: Load or connect to your actual ML model here
    # ml_model = load_my_model()

    audio_buffer = []
    buffered_samples = 0

    try:
        while True:
            # Get the next audio chunk intended for ML
            chunk = ml_input_queue.get() # Blocks until a chunk is available

            # --- Add this print statement ---
            chunk_size_info = chunk.size if isinstance(chunk, np.ndarray) else 'N/A (None or other type)'
            # print(f"ML Interface [{source_id}]: Got chunk from queue (type: {type(chunk)}, size: {chunk_size_info})") # Keep commented unless debugging queue itself
            # ---------------------------------

            if chunk is None: # Shutdown signal
                print(f"ML Interface [{source_id}]: Received shutdown signal.")
                # Optional: Process any remaining data in the buffer before exiting
                if audio_buffer:
                    print(f"ML Interface [{source_id}]: Processing remaining {buffered_samples / RATE:.2f} seconds before shutdown.")
                    combined_chunk = np.concatenate(audio_buffer)
                    features = extract_features_from_chunk(combined_chunk, RATE)
                    if features is not None and features.shape[0] > 0:
                        # --- Perform ML prediction on remaining data (simulation) --- 
                        if random.random() < 0:
                           ml_result = {"warning": "popping detected (final)"}
                        else:
                           ml_result = {"warning": None}

                        if ml_result and ml_result.get("warning"):
                            warning_message = ml_result["warning"]
                            print(f"ML Interface [{source_id}]: Detected '{warning_message}'")
                            if not warning_queue.full():
                                # Put tagged warning
                                warning_queue.put((source_id, warning_message))
                break # Exit the loop

            # --- Buffer the chunk ---
            # Ensure chunk is a numpy array before buffering
            # This conversion might ideally happen in audio_handler before queuing
            if not isinstance(chunk, np.ndarray):
                try:
                    # Assuming float32 data is coming, adjust if needed (e.g., frombuffer)
                    chunk_np = np.array(chunk, dtype=np.float32)
                except ValueError:
                    print(f"ML Interface [{source_id}]: Warning - Could not convert incoming chunk to numpy array. Skipping.")
                    continue
            else:
                chunk_np = chunk

            audio_buffer.append(chunk_np)
            buffered_samples += len(chunk_np.flatten()) # Use flatten() in case of multi-channel chunks

            # --- Check if buffer is full enough ---
            if buffered_samples >= TARGET_SAMPLES:
                print(f"ML Interface [{source_id}]: Processing buffer ({buffered_samples / RATE:.2f} seconds)")
                # Combine buffered chunks into one large chunk
                combined_chunk = np.concatenate(audio_buffer)

                # --- Add Normalization Step ---
                peak_value = np.max(np.abs(combined_chunk))
                if peak_value > 1e-6: # Avoid division by zero or near-zero
                    normalized_chunk = combined_chunk / peak_value
                else:
                    normalized_chunk = combined_chunk # Keep as is if silent/zero
                # -----------------------------

                # Extract features from the *normalized* chunk
                features = extract_features_from_chunk(normalized_chunk, RATE) # Use normalized_chunk

                # --- TEMPORARY: Save features to file ---
                if features is not None and features.shape[0] > 0:
                    try:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        # Sanitize source_id for filename (replace tuple chars)
                        safe_source_id = str(source_id).replace(', ', '_').strip('()')
                        filename = f"features_src{safe_source_id}_{timestamp}.npy"
                        filepath = os.path.join(TEMP_FEATURE_DIR, filename)
                        np.save(filepath, features)
                        # print(f"ML Interface [{source_id}]: Saved features to {filepath}") # Optional: uncomment for verbose logging
                    except Exception as e:
                        print(f"ML Interface [{source_id}]: Error saving features: {e}")
                # -----------------------------------------

                if features is not None and features.shape[0] > 0:
                    # --- Placeholder: Interact with the actual ML model ---
                    prediction = ml_model.predict(features) # Example
                    if np.any(prediction == 1):
                        warning_message = "popping detected"
                        print(f"ML Interface [{source_id}]: Detected '{warning_message}'")
                        if not warning_queue.full():
                            warning_queue.put((source_id, warning_message))
                else:
                    print(f"ML Interface [{source_id}]: Skipping buffer due to feature extraction issue.")

                # Clear the buffer for the next segment
                audio_buffer = []
                buffered_samples = 0

    except KeyboardInterrupt:
        print(f"ML Interface [{source_id}]: Interrupted.")
    except Exception as e:
        print(f"ML Interface [{source_id}]: An error occurred: {e}")
    finally:
        print(f"ML Interface [{source_id}]: Stopped.")
