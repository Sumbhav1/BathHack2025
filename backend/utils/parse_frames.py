import numpy as np

def parse_frames_to_numpy(audio_bytes: bytes, dtype=np.int16) -> np.ndarray:
    """Converts raw audio bytes into a normalized NumPy array.

    Args:
        audio_bytes: Raw audio data as bytes.
        dtype: The NumPy data type corresponding to the audio format (e.g., np.int16).

    Returns:
        A NumPy array of float32 values normalized between -1.0 and 1.0.
    """
    if not audio_bytes:
        return np.array([], dtype=np.float32)

    try:
        # Convert bytes to NumPy array based on the specified dtype
        audio_array = np.frombuffer(audio_bytes, dtype=dtype)

        # Normalize the array to float32 range [-1.0, 1.0]
        # Check if dtype is an integer type before normalization
        if np.issubdtype(dtype, np.integer):
            max_val = np.iinfo(dtype).max
            audio_normalized = audio_array.astype(np.float32) / max_val
        else:
            # If already float, assume it's in the correct range or doesn't need normalization
            audio_normalized = audio_array.astype(np.float32)

        return audio_normalized

    except Exception as e:
        print(f"Error parsing audio frames: {e}")
        return np.array([], dtype=np.float32)
