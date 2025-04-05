import time
import queue
import threading
import numpy as np
import sounddevice as sd
from typing import Optional
from backend import BackendService
import os

def print_device_list(devices):
    """Print available devices in a readable format."""
    print("\nAvailable Devices:")
    print("-" * 50)
    for device in devices:
        print(f"ID: {device['index']}")
        print(f"Name: {device['name']}")
        print(f"Channels: {device['channels']}")
        print(f"Sample Rate: {device['sample_rate']}")
        print("-" * 50)

def get_user_selection(devices):
    """Get user's device and channel selection."""
    print_device_list(devices)
    
    while True:
        try:
            device_id = int(input("\nEnter device ID: "))
            # Find the selected device
            selected_device = next((d for d in devices if d['index'] == device_id), None)
            if selected_device is None:
                print("Invalid device ID. Please try again.")
                continue
            
            # Get channel selection
            max_channels = selected_device['channels']
            print(f"\nAvailable channels: 0 to {max_channels - 1}")
            channel = int(input("Enter channel number: "))
            
            if 0 <= channel < max_channels:
                return device_id, channel
            else:
                print("Invalid channel number. Please try again.")
        except ValueError:
            print("Please enter valid numbers.")

def list_output_devices():
    """List available output devices."""
    print("\nAvailable Output Devices:")
    print("-" * 50)
    try:
        devices = sd.query_devices()
        for idx, device in enumerate(devices):
            if device['max_output_channels'] > 0:
                print(f"ID: {idx}")
                print(f"Name: {device['name']}")
                print(f"Channels: {device['max_output_channels']}")
                print(f"Sample Rate: {device['default_samplerate']}")
                print("-" * 50)
    except Exception as e:
        print(f"Error listing output devices: {e}")

def select_output_device():
    """Let user select an output device."""
    list_output_devices()
    while True:
        try:
            device_input = input("\nEnter output device ID (or press Enter for default): ").strip()
            if not device_input:  # User pressed Enter
                return None
            device_id = int(device_input)
            # Verify device exists and has output channels
            devices = sd.query_devices()
            if 0 <= device_id < len(devices) and devices[device_id]['max_output_channels'] > 0:
                return device_id
            else:
                print("Selected device has no output channels. Please select another.")
        except ValueError:
            print("Please enter a valid number or press Enter for default device.")
        except Exception as e:
            print(f"Invalid device selection: {e}")
            return None  # Use default device on error

def play_audio_from_queue(queue_obj: queue.Queue, stop_event: threading.Event, output_device: Optional[int] = None):
    """Play audio data from queue using sounddevice."""
    print(f"\nStarting audio playback thread (Output device: {output_device if output_device is not None else 'default'})")
    
    # Configure sounddevice settings with more conservative values
    blocksize = 2048  # Increased block size to match AudioManager
    latency = 0.1    # More conservative latency
    
    try:
        stream = sd.OutputStream(
            samplerate=44100,
            channels=1,
            dtype=np.float32,
            device=output_device,
            blocksize=blocksize,
            latency=latency,
            callback=None  # Use blocking mode
        )
        stream.start()
        print("Audio output stream started successfully")
    except Exception as e:
        print(f"Error starting audio output stream: {e}")
        return

    # Audio processing parameters
    buffer = []
    last_playback_time = time.time()
    MIN_PLAYBACK_INTERVAL = 0.01  # Increased to 10ms
    
    # Feedback prevention with more conservative settings
    prev_rms = 0
    RMS_SMOOTHING = 0.3    # Slower response to changes
    FEEDBACK_THRESHOLD = 2.0  # Higher threshold
    
    while not stop_event.is_set():
        try:
            message = queue_obj.get(timeout=0.1)  # Increased timeout
            if message is None:
                break

            if message['type'] == 'live_audio':
                try:
                    audio_data = np.frombuffer(message['data'], dtype=np.int16)
                    
                    # Calculate current RMS with smoothing
                    current_rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
                    smoothed_rms = (RMS_SMOOTHING * prev_rms) + ((1 - RMS_SMOOTHING) * current_rms)
                    
                    # More sophisticated feedback detection
                    if smoothed_rms > FEEDBACK_THRESHOLD * prev_rms and prev_rms > 1000:
                        print("Potential feedback detected - reducing volume")
                        audio_data = audio_data * 0.3  # More aggressive volume reduction
                    
                    prev_rms = smoothed_rms
                    
                    # Normalize with soft clipping
                    normalized_data = np.tanh(audio_data.astype(np.float32) / 32768.0)
                    
                    # Conservative volume control
                    volume = 0.5  # Further reduced base volume
                    normalized_data *= volume
                    
                    current_time = time.time()
                    if current_time - last_playback_time >= MIN_PLAYBACK_INTERVAL:
                        try:
                            # Longer fades to reduce clicks
                            if len(normalized_data) > 200:
                                normalized_data[:50] *= np.linspace(0, 1, 50)
                                normalized_data[-50:] *= np.linspace(1, 0, 50)
                            
                            stream.write(normalized_data)
                            last_playback_time = current_time
                            
                        except Exception as e:
                            print(f"Error writing to audio stream: {e}")
                        
                except Exception as e:
                    print(f"Error processing live audio: {e}")
            
            elif message['type'] == 'buffer_data':
                try:
                    if isinstance(message['data'], np.ndarray):
                        playback_data = message['data']
                        if not np.issubdtype(playback_data.dtype, np.floating):
                            playback_data = np.tanh(playback_data.astype(np.float32) / 32768.0)
                        
                        # Reduced volume for buffer playback
                        playback_data *= 0.5
                        
                        # Process in larger chunks
                        chunk_size = blocksize * 8
                        
                        for i in range(0, len(playback_data), chunk_size):
                            if stop_event.is_set():
                                break
                                
                            chunk = playback_data[i:i + chunk_size]
                            if len(chunk) < chunk_size:
                                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
                            
                            # Longer crossfades between chunks
                            if i > 0:
                                chunk[:50] *= np.linspace(0, 1, 50)
                            if i + chunk_size < len(playback_data):
                                chunk[-50:] *= np.linspace(1, 0, 50)
                                
                            stream.write(chunk)
                            time.sleep(0.005)  # Small delay between chunks
                            
                except Exception as e:
                    print(f"Error playing buffer data: {e}")

            queue_obj.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            print(f"Error in playback thread: {e}")
    
    # Clean up
    try:
        stream.stop()
        stream.close()
        print("Audio output stream closed")
    except:
        pass

def save_metrics(metrics_dir, device_id, channel, feature_matrices, rms_values):
    """Save metrics to files."""
    # Create metrics directory if it doesn't exist
    os.makedirs(metrics_dir, exist_ok=True)
    
    # Save feature matrices
    for i, matrix in enumerate(feature_matrices):
        filename = f"device_{device_id}_channel_{channel}_matrix_{i}.npy"
        filepath = os.path.join(metrics_dir, filename)
        np.save(filepath, matrix)
        print(f"Saved feature matrix {i} to {filepath}")
    
    # Save RMS values
    rms_filename = f"device_{device_id}_channel_{channel}_rms_values.npy"
    rms_filepath = os.path.join(metrics_dir, rms_filename)
    np.save(rms_filepath, np.array(rms_values))
    print(f"Saved RMS values to {rms_filepath}")

def collect_metrics(feature_queue: queue.Queue, duration: float):
    """Collect metrics from feature queue for specified duration."""
    start_time = time.time()
    rms_values = []
    feature_matrices = []
    print(f"\nCollecting metrics for {duration} seconds...")
    
    while time.time() - start_time < duration:
        try:
            message = feature_queue.get_nowait()
            print(f"Received message type: {message['type']}")
            
            if message['type'] == 'level_update':
                rms_values.append(message['rms'])
                print(f"Added RMS value: {message['rms']:.6f}")
            elif message['type'] == 'buffer_data':
                if isinstance(message['data'], np.ndarray):
                    feature_matrices.append(message['data'])
                    print(f"Added feature matrix with shape: {message['data'].shape}")
                else:
                    print(f"Warning: buffer_data contains non-numpy data: {type(message['data'])}")
            feature_queue.task_done()
        except queue.Empty:
            time.sleep(0.01)
            continue
        except Exception as e:
            print(f"Error collecting metrics: {e}")
            continue
    
    print(f"Collection complete. Got {len(rms_values)} RMS values and {len(feature_matrices)} feature matrices.")
    return feature_matrices, rms_values

if __name__ == "__main__":
    print("=== Audio Playback and Metrics Test ===")
    
    # Select output device first
    output_device_id = select_output_device()
    
    # Initialize backend
    backend = BackendService()
    backend.start()
    time.sleep(1)  # Give time for initialization
    
    try:
        # Get available devices and user selection
        devices = backend.get_available_devices()
        if not devices:
            print("No input devices found!")
            exit(1)
        
        device_id, channel = get_user_selection(devices)
        print(f"\nSelected Device ID: {device_id}, Channel: {channel}")
        
        # Start monitoring the selected device/channel
        backend.command_queue.put({
            'type': 'start_monitoring',
            'device_id': device_id,
            'channel_index': channel
        })
        time.sleep(1)  # Allow time for monitoring to start
        
        # Setup audio playback
        stop_playback = threading.Event()
        playback_thread = threading.Thread(
            target=play_audio_from_queue,
            args=(backend.live_audio_queue, stop_playback, output_device_id),
            daemon=True
        )
        playback_thread.start()
        
        # Live playback for 10 seconds
        print("\nStarting 10-second live playback...")
        backend.command_queue.put({
            'type': 'start_live_audio',
            'device_id': device_id,
            'channel_index': channel
        })
        
        # Collect metrics during live playback
        live_matrices, live_rms = collect_metrics(backend.feature_queue, 10)
        
        # Stop live playback
        backend.command_queue.put({
            'type': 'stop_live_audio',
            'device_id': device_id,
            'channel_index': channel
        })
        time.sleep(0.5)
        
        # Request and play back the stored recording (last 10 seconds)
        print("\nPlaying back stored recording...")
        backend.command_queue.put({
            'type': 'get_buffer',
            'device_id': device_id,
            'channel_index': channel,
            'seconds': 10
        })
        
        # Collect metrics during playback
        playback_matrices, playback_rms = collect_metrics(backend.feature_queue, 2)  # Short duration for buffer retrieval
        
        # Save all metrics
        print("\nSaving metrics...")
        metrics_dir = os.path.join("metrics", f"device_{device_id}_channel_{channel}")
        save_metrics(metrics_dir, device_id, channel, live_matrices + playback_matrices, live_rms + playback_rms)
        
        # Stop monitoring
        backend.command_queue.put({
            'type': 'stop_monitoring',
            'device_id': device_id,
            'channel_index': channel
        })
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    finally:
        # Cleanup
        stop_playback.set()
        backend.live_audio_queue.put(None)  # Sentinel value
        playback_thread.join(timeout=1)
        backend.stop()
        print("\n=== Test Complete ===")