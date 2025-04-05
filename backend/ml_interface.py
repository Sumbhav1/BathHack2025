import time
import numpy as np
import librosa

# Constants
RATE = 16000  # New Sample rate (Hz) - MUST MATCH audio_handler.py
BUFFER_DURATION_SECONDS = 2  # New Duration to buffer audio before processing (seconds)
TARGET_SAMPLES = int(BUFFER_DURATION_SECONDS * RATE)

def extract_features_from_chunk(audio_chunk, sr):
    """Extracts features (RMS, ZCR, Onset Strength) from a raw audio chunk."""
    try:
        # Ensure chunk is numpy array and potentially flatten if needed
        if not isinstance(audio_chunk, np.ndarray):
            # This might depend on how chunks arrive (e.g., from sounddevice)
            audio_chunk = np.array(audio_chunk, dtype=np.float32).flatten()
        elif audio_chunk.ndim > 1:
             # Flatten if it's multi-channel, feature extraction expects mono
             audio_chunk = audio_chunk.flatten()

        if len(audio_chunk) == 0:
            print("Warning: Received empty audio chunk.")
            return None

        # --- Extract Core Features ---
        # Adjust parameters like hop_length if needed for chunk-based processing
        # hop_length = 512 # Example, default for librosa features

        # 1. RMS Energy
        rms = librosa.feature.rms(y=audio_chunk)[0] # hop_length=hop_length

        # 2. Zero Crossing Rate
        zcr = librosa.feature.zero_crossing_rate(y=audio_chunk)[0] # hop_length=hop_length

        # 3. Onset Strength Envelope
        # Note: Onset strength might be less meaningful on very short chunks
        # Consider if this feature is appropriate for real-time chunks
        onset_env = librosa.onset.onset_strength(y=audio_chunk, sr=sr) # hop_length=hop_length

        # --- Align and Combine Features ---
        # The length alignment might behave differently with chunks vs full files
        min_len = min(len(rms), len(zcr), len(onset_env))
        if min_len == 0:
            print("Warning: Could not extract features from chunk.")
            return None

        rms = rms[:min_len]
        zcr = zcr[:min_len]
        onset_env = onset_env[:min_len]

        # Combine features: Result shape will be (min_len, 3)
        feature_matrix = np.vstack([rms, zcr, onset_env]).T
        # print(f"Extracted feature matrix shape: {feature_matrix.shape}") # Debug print

        return feature_matrix

    except Exception as e:
        print(f"Error extracting features from chunk: {e}")
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
            # chunk_size_info = chunk.size if isinstance(chunk, np.ndarray) else 'N/A (None or other type)'
            # print(f"ML Interface [{source_id}]: Got chunk from queue (type: {type(chunk)}, size: {chunk_size_info})")
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
                        import random
                        if random.random() < 0.05:
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

                if features is not None and features.shape[0] > 0:
                    # --- Placeholder: Interact with the actual ML model ---
                    # prediction = ml_model.predict(features) # Example

                    # Simulate receiving a result (replace with actual model interaction)
                    time.sleep(0.05) # Simulate processing time
                    import random
                    if random.random() < 0.05: # Simulate a 5% chance of detecting popping
                       ml_result = {"warning": "popping detected"}
                    else:
                       ml_result = {"warning": None}

                    # --- Process ML Result ---
                    if ml_result and ml_result.get("warning"):
                        warning_message = ml_result["warning"]
                        print(f"ML Interface [{source_id}]: Detected '{warning_message}'")
                        # Send tagged warning to the shared queue
                        if not warning_queue.full():
                            warning_queue.put((source_id, warning_message)) # Put tuple
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
