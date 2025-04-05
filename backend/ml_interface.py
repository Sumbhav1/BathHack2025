import time
import numpy as np
import librosa

# Constants
RATE = 44100 # Sample rate expected by feature extraction
BUFFER_DURATION_SECONDS = 5 # Target duration for ML processing
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


def buffer_and_analyze_audio(ml_input_queue, ml_output_queue, warning_queue):
    """
    Buffers audio chunks to ~5 seconds, extracts features, interacts with ML model,
    and sends warnings.
    """
    print(f"ML Interface: Starting... Buffering for {BUFFER_DURATION_SECONDS} seconds.")
    # Placeholder: Load or connect to your actual ML model here
    # ml_model = load_my_model()

    audio_buffer = []
    buffered_samples = 0

    try:
        while True:
            # Get the next audio chunk intended for ML
            chunk = ml_input_queue.get() # Blocks until a chunk is available

            if chunk is None: # Shutdown signal
                print("ML Interface: Received shutdown signal.")
                # Optional: Process any remaining data in the buffer before exiting
                if audio_buffer:
                    print(f"ML Interface: Processing remaining {buffered_samples / RATE:.2f} seconds before shutdown.")
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
                            print(f"ML Interface: Detected '{warning_message}'")
                            if not warning_queue.full():
                                warning_queue.put(warning_message)
                break # Exit the loop

            # --- Buffer the chunk ---
            # Ensure chunk is a numpy array before buffering
            # This conversion might ideally happen in audio_handler before queuing
            if not isinstance(chunk, np.ndarray):
                try:
                    # Assuming float32 data is coming, adjust if needed (e.g., frombuffer)
                    chunk_np = np.array(chunk, dtype=np.float32)
                except ValueError:
                    print("ML Interface: Warning - Could not convert incoming chunk to numpy array. Skipping.")
                    continue
            else:
                chunk_np = chunk

            audio_buffer.append(chunk_np)
            buffered_samples += len(chunk_np.flatten()) # Use flatten() in case of multi-channel chunks

            # --- Check if buffer is full enough ---
            if buffered_samples >= TARGET_SAMPLES:
                print(f"ML Interface: Processing buffer ({buffered_samples / RATE:.2f} seconds)")
                # Combine buffered chunks into one large chunk
                combined_chunk = np.concatenate(audio_buffer)

                # Extract features from the combined chunk
                features = extract_features_from_chunk(combined_chunk, RATE)

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
                        print(f"ML Interface: Detected '{warning_message}'")
                        # Send warning to frontend communicator
                        if not warning_queue.full():
                            warning_queue.put(warning_message)
                else:
                    print("ML Interface: Skipping buffer due to feature extraction issue.")

                # Clear the buffer for the next segment
                audio_buffer = []
                buffered_samples = 0

    except KeyboardInterrupt:
        print("ML Interface: Interrupted.")
    except Exception as e:
        print(f"ML Interface: An error occurred: {e}")
    finally:
        print("ML Interface: Stopped.")





'''
# Example of how this might be run (in main_backend.py)
if __name__ == '__main__':
    # This part is just for testing the module directly, not for production run
    from multiprocessing import Queue
    import numpy as np
    import time # Needed for sleep

    # --- Test 1: Direct call to extract_features_from_chunk (keep this) ---
    test_duration_seconds = 1.0
    dummy_chunk_for_extract = np.random.uniform(-0.5, 0.5, size=int(RATE * test_duration_seconds))
    print(f"--- Testing extract_features_from_chunk ---")
    print(f"Generated dummy_chunk shape: {dummy_chunk_for_extract.shape}")
    print(f"Dummy chunk duration: {len(dummy_chunk_for_extract)/RATE:.2f} seconds")
    features = extract_features_from_chunk(dummy_chunk_for_extract, RATE)
    if features is not None:
        print(f"Extracted features matrix shape: {features.shape}")
        print(f"(Shape means: {features.shape[0]} time steps, {features.shape[1]} features [RMS, ZCR, Onset Strength])")
        print("First 5 feature vectors:")
        print(features[:5, :])
    else:
        print("Feature extraction failed for the dummy chunk.")
    print("---------------------------------------------")

    # --- Test 2: Testing process_for_ml with queues ---
    print(f"\n--- Testing process_for_ml (using queues) ---")
    in_q = Queue()
    out_q = Queue() # Not strictly checked in this test, but needed by the function
    warn_q = Queue()

    # Simulate sending chunks over time (e.g., 6 seconds worth)
    chunk_size = 1024 # Typical chunk size
    total_test_duration_sec = 6.0
    num_chunks_to_send = int((total_test_duration_sec * RATE) / chunk_size)

    print(f"Simulating sending {num_chunks_to_send} chunks (each {chunk_size} samples) over ~{total_test_duration_sec}s...")
    print(f"Target buffer duration is {BUFFER_DURATION_SECONDS}s. Expecting one processing cycle.")

    # Put chunks onto the input queue
    for i in range(num_chunks_to_send):
        dummy_chunk = np.random.uniform(-0.5, 0.5, size=chunk_size).astype(np.float32)
        in_q.put(dummy_chunk)
        # time.sleep(0.001) # Optional small sleep to simulate real-time arrival

    # Send the shutdown signal
    print("Sending shutdown signal (None) to input queue.")
    in_q.put(None)

    # Run the function (usually in a separate process, but run directly for this test)
    print("Starting process_for_ml...")
    process_for_ml(in_q, out_q, warn_q)
    print("process_for_ml finished.")

    # Check the warning queue for results
    print("Checking warning queue...")
    warnings_received = []
    while not warn_q.empty():
        warnings_received.append(warn_q.get_nowait())

    if warnings_received:
        print(f"Received {len(warnings_received)} warning(s):")
        for warning in warnings_received:
            print(f" - {warning}")
    else:
        print("No warnings received from the warning queue.")
    print("---------------------------------------------")
'''
