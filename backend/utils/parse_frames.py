import numpy as np
import pyaudio

def parse_frames_to_numpy(raw_bytes: bytes, dtype=pyaudio.paInt16, normalize=True) -> np.ndarray:
    """Parse raw audio bytes into a numpy array.
    
    Args:
        raw_bytes: Raw audio bytes from PyAudio
        dtype: PyAudio format type (default: paInt16)
        normalize: Whether to normalize to [-1, 1] range (default: True)
        
    Returns:
        Numpy array of parsed audio data
    """
    # Map PyAudio format to numpy dtype
    format_map = {
        pyaudio.paFloat32: np.float32,
        pyaudio.paInt32: np.int32,
        pyaudio.paInt24: np.int32,  # No direct numpy equivalent for 24-bit
        pyaudio.paInt16: np.int16,
        pyaudio.paInt8: np.int8,
        pyaudio.paUInt8: np.uint8
    }
    
    numpy_dtype = format_map.get(dtype, np.int16)
    
    try:
        # Convert bytes to numpy array
        audio_data = np.frombuffer(raw_bytes, dtype=numpy_dtype)
        
        if normalize:
            if np.issubdtype(numpy_dtype, np.integer):
                # Convert to float32 and normalize to [-1, 1]
                max_val = float(np.iinfo(numpy_dtype).max)
                audio_data = audio_data.astype(np.float32) / max_val
            elif numpy_dtype == np.float32:
                # Already float32, just ensure proper range
                audio_data = np.clip(audio_data, -1.0, 1.0)
        
        return audio_data
        
    except Exception as e:
        print(f"Error parsing frames: {e}")
        return np.array([], dtype=numpy_dtype)
