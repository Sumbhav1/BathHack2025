import numpy as np
import librosa
import time
from typing import Dict, Optional, Tuple

class FeatureProcessor:
    def __init__(self, rate=44100):
        self.rate = rate
        self.sample_rate = rate
        self._buffer = np.array([])
        self._min_chunk_size = 2048  # Minimum size for processing
        
    def process_chunk(self, chunk: np.ndarray) -> Optional[np.ndarray]:
        """Process a chunk of audio data with improved stability."""
        try:
            # Append new chunk to buffer
            self._buffer = np.concatenate([self._buffer, chunk]) if self._buffer.size > 0 else chunk
            
            # Only process if we have enough data
            if len(self._buffer) < self._min_chunk_size:
                return None
                
            # Extract features
            features = self._extract_features(self._buffer)
            
            # Keep a small overlap for continuity
            overlap = min(1024, len(self._buffer))
            self._buffer = self._buffer[-overlap:]
            
            return features
            
        except Exception as e:
            print(f"Error processing chunk: {e}")
            self._buffer = np.array([])  # Reset buffer on error
            return None
            
    def _extract_features(self, audio_data: np.ndarray) -> np.ndarray:
        """Extract audio features with improved stability and error checking."""
        try:
            # Ensure audio data is valid
            if len(audio_data) == 0:
                return np.array([])
                
            # 1. RMS Energy (with normalization)
            rms = librosa.feature.rms(y=audio_data)[0]
            rms = np.clip(rms, 0, None)  # Ensure non-negative
            
            # 2. Zero Crossing Rate (with smoothing)
            zcr = librosa.feature.zero_crossing_rate(audio_data, 
                frame_length=2048, 
                hop_length=512)[0]
            zcr = self._smooth_feature(zcr)
            
            # 3. Onset Strength (with adaptive threshold)
            onset_env = librosa.onset.onset_strength(
                y=audio_data, 
                sr=self.sample_rate,
                hop_length=512,
                aggregate=np.median)  # More stable aggregation
            onset_env = self._smooth_feature(onset_env)
            
            # 4. Spectral Centroid (new feature for better characterization)
            spectral = librosa.feature.spectral_centroid(
                y=audio_data, 
                sr=self.sample_rate,
                hop_length=512)[0]
            spectral = self._smooth_feature(spectral)
            
            # Align all features to same length
            min_length = min(len(rms), len(zcr), len(onset_env), len(spectral))
            features = np.vstack([
                rms[:min_length],
                zcr[:min_length],
                onset_env[:min_length],
                spectral[:min_length]
            ]).T
            
            return features
            
        except Exception as e:
            print(f"Error extracting features: {e}")
            return np.array([])
            
    def _smooth_feature(self, feature: np.ndarray, window_size: int = 3) -> np.ndarray:
        """Apply smoothing to reduce noise in feature extraction."""
        try:
            if len(feature) < window_size:
                return feature
            return np.convolve(feature, 
                             np.ones(window_size)/window_size, 
                             mode='valid')
        except Exception as e:
            print(f"Error smoothing feature: {e}")
            return feature
            
    def reset(self):
        """Reset the processor state."""
        self._buffer = np.array([])