import pyaudio
import threading
import numpy as np
from collections import deque
from threading import Thread, Lock
import time
import itertools
from typing import Dict, Optional, Tuple, List
from .utils.parse_frames import parse_frames_to_numpy # Assuming parse_frames.py exists

class AudioManager:
    def __init__(self):
        self.CHUNK_SIZE = 2048  # Increased from 1024 for better stability
        self.FORMAT = pyaudio.paFloat32  # Changed to float32 for better precision
        self.CHANNELS = 1
        self.RATE = 44100
        self.LATENCY = 0.1  # 100ms latency for better stability
        self.MAX_QUEUE_SIZE = 10
        
        self.audio = pyaudio.PyAudio()
        self.streams = {}
        self.buffers = {}
        self.lock = threading.Lock()
        
    def list_input_devices(self) -> List[dict]:
        """List all available input devices and their channels."""
        devices = []
        for i in range(self.audio.get_device_count()):
            try:
                device_info = self.audio.get_device_info_by_index(i)
                if device_info['maxInputChannels'] > 0:
                    devices.append({
                        'index': i,
                        'name': device_info['name'],
                        'channels': device_info['maxInputChannels'],
                        'sample_rate': int(device_info['defaultSampleRate'])
                    })
            except Exception as e:
                print(f"Error getting device info for index {i}: {e}")
        return devices

    def start_recording(self, device_id: int, channel_index: int):
        """Start recording with improved error handling and buffer management."""
        if (device_id, channel_index) in self.streams:
            return
            
        try:
            stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                input_device_index=device_id,
                frames_per_buffer=self.CHUNK_SIZE,
                start=False  # Don't start immediately
            )
            
            self.streams[(device_id, channel_index)] = stream
            self.buffers[(device_id, channel_index)] = deque(maxlen=self.MAX_QUEUE_SIZE)
            
            # Start stream in a controlled manner
            stream.start_stream()
            
            # Start the recording thread
            threading.Thread(
                target=self._record_audio,
                args=(device_id, channel_index),
                daemon=True
            ).start()
            
        except Exception as e:
            print(f"Error starting recording: {e}")
            self.cleanup()
            raise
            
    def _record_audio(self, device_id: int, channel_index: int):
        """Record audio with improved buffer management."""
        stream = self.streams.get((device_id, channel_index))
        if not stream:
            return
            
        while stream.is_active():
            try:
                data = stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
                audio_chunk = np.frombuffer(data, dtype=np.float32)
                
                with self.lock:
                    buffer = self.buffers.get((device_id, channel_index))
                    if buffer is not None:
                        # If buffer is full, remove oldest chunk
                        if len(buffer) >= self.MAX_QUEUE_SIZE:
                            buffer.popleft()
                        buffer.append(audio_chunk)
                        
            except Exception as e:
                print(f"Error recording audio: {e}")
                time.sleep(0.1)  # Prevent tight loop on error

    def stop_recording(self, device_id: int, channel_index: int):
        """Stop recording from a specific device and channel."""
        channel_key = (device_id, channel_index)
        if channel_key in self.streams:
            try:
                stream = self.streams[channel_key]
                stream.stop_stream()
                stream.close()
                del self.streams[channel_key]
                print(f"Stopped recording from device {device_id, channel_index}")
            except Exception as e:
                print(f"Error stopping recording: {e}")
            finally:
                self.cleanup_channel(device_id, channel_index)

    def cleanup_channel(self, device_id: int, channel_index: int):
        """Clean up resources for a specific channel."""
        channel_key = (device_id, channel_index)
        self.streams.pop(channel_key, None)
        self.buffers.pop(channel_key, None)

    def cleanup(self):
        """Clean up all resources."""
        for stream in self.streams.values():
            try:
                if stream.is_active():
                    stream.stop_stream()
                stream.close()
            except Exception as e:
                print(f"Error cleaning up stream: {e}")
                
        self.streams.clear()
        self.buffers.clear()
        
        try:
            self.audio.terminate()
        except Exception as e:
            print(f"Error terminating PyAudio: {e}")

    def get_buffer_segment_parsed(self, device_id: int, channel_index: int, seconds: float) -> Optional[np.ndarray]:
        """Get a segment of the audio buffer with improved synchronization."""
        channel_key = (device_id, channel_index)
        if channel_key not in self.buffers:
            return None
            
        try:
            chunks_needed = int((seconds * self.RATE) / self.CHUNK_SIZE)
            with self.lock:
                buffer = self.buffers[channel_key]
                if len(buffer) == 0:
                    return None
                    
                # Get the most recent chunks
                chunks = list(itertools.islice(buffer,
                    max(0, len(buffer) - chunks_needed),
                    len(buffer)))
                    
                if not chunks:
                    return None
                    
                # Concatenate chunks
                return np.concatenate(chunks)
                
        except Exception as e:
            print(f"Error getting buffer segment: {e}")
            return None

    def get_latest_parsed_chunk(self, device_id: int, channel_index: int) -> Optional[np.ndarray]:
        """Get latest audio chunk with smooth crossfade."""
        with self.lock:
            buffer = self.buffers.get((device_id, channel_index))
            if not buffer or len(buffer) == 0:
                return None
                
            # Get the latest chunk
            chunk = buffer.popleft()
            
            # Apply fade in/out to reduce clicks
            if len(chunk) > 0:
                fade_len = min(128, len(chunk))
                chunk[:fade_len] *= np.linspace(0, 1, fade_len)
                chunk[-fade_len:] *= np.linspace(1, 0, fade_len)
                
            return chunk
