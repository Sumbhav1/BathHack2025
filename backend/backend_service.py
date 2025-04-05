import numpy as np
from .audio_manager import AudioManager
from .feature_processor import FeatureProcessor # Assuming this processes parsed numpy arrays
import queue
import threading
import librosa
import time
from typing import Dict, List, Optional, Tuple # Add Tuple

class BackendService:
    def __init__(self):
        self.audio_manager = AudioManager()
        self.feature_processor = FeatureProcessor() # Pass rate

        # Queues for communication
        self.feature_queue = queue.Queue() # For features/results to frontend/ML
        self.command_queue = queue.Queue() # For commands from frontend
        self.live_audio_queue = queue.Queue() # For raw audio to frontend playback

        # Store active devices as (device_id, channel_index) -> state
        self.active_channels: Dict[Tuple[int, int], dict] = {}
        self.processing_thread = None
        self.ml_processing_thread = None # Dedicated thread for ML chunks
        self.running = False
        self.ml_chunk_seconds = 5 # Process ML every 5 seconds
        self.rms_update_interval = 0.1 # Send RMS update every 100ms

        self._processing_thread = None
        self._stop_event = threading.Event()
        self.last_process_time = 0
        self.MIN_PROCESS_INTERVAL = 0.02  # 20ms minimum between processing

    def start(self):
        """Start the backend service and processing threads."""
        if self.running:
            return
        print("Starting BackendService...")
        self.running = True
        # Main loop for commands, RMS updates, and feeding ML preprocessor
        self.processing_thread = threading.Thread(target=self._processing_loop)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        # Dedicated loop for aggregating features and calling ML model
        self.ml_processing_thread = threading.Thread(target=self._ml_processing_loop)
        self.ml_processing_thread.daemon = True
        self.ml_processing_thread.start()
        print("BackendService started.")


    def stop(self):
        """Stop the backend service."""
        if not self.running:
            return
        print("Stopping BackendService...")
        self.running = False # Signal threads to stop
        # Send sentinel values or use timeouts if queues might block joins
        self.command_queue.put(None) # Example sentinel

        if self.processing_thread:
            self.processing_thread.join(timeout=2)
        if self.ml_processing_thread:
             # Add mechanism to signal ML thread to stop (e.g., another queue/event)
            self.ml_processing_thread.join(timeout=2) # Needs proper stop signal

        self.audio_manager.cleanup()
        print("BackendService stopped.")


    def get_available_devices(self) -> List[dict]:
        """Get list of available input devices."""
        return self.audio_manager.list_input_devices()

    def start_monitoring_channel(self, device_id: int, channel_index: int):
        """Start monitoring a specific device channel."""
        channel_key = (device_id, channel_index)
        if channel_key not in self.active_channels:
            print(f"Request received to start monitoring {channel_key}")
            self.active_channels[channel_key] = {
                'monitoring': True,
                'last_pop_time': 0,
                'last_rms_update_time': 0,
                'feature_buffer': [] # Buffer features for ML chunking
            }
            self.audio_manager.start_recording(device_id, channel_index)
        else:
             print(f"Already monitoring {channel_key}")


    def stop_monitoring_channel(self, device_id: int, channel_index: int):
        """Stop monitoring a specific device channel."""
        channel_key = (device_id, channel_index)
        if channel_key in self.active_channels:
            print(f"Request received to stop monitoring {channel_key}")
            self.audio_manager.stop_recording(device_id, channel_index)
            # Use pop with default to avoid KeyError if already removed
            self.active_channels.pop(channel_key, None)


    def get_recent_audio_parsed(self, device_id: int, channel_index: int, seconds: float) -> Optional[np.ndarray]:
         """Get recent parsed audio data for playback/analysis."""
         # Note: Frontend might want raw bytes for playback. Decide format needed.
         return self.audio_manager.get_buffer_segment_parsed(device_id, channel_index, seconds)

    # --- Main Processing Loop ---
    def _processing_loop(self):
        """Main processing loop for audio features."""
        while not self._stop_event.is_set():
            try:
                # Process commands with a shorter timeout
                try:
                    command = self.command_queue.get(timeout=0.01)
                    self._handle_command(command)
                    self.command_queue.task_done()
                except queue.Empty:
                    pass  # No commands waiting
                
                # Process live audio streams
                for device_id, channel_index in list(self._monitored_channels):
                    try:
                        # Get latest chunk with a small timeout
                        chunk = self.audio_manager.get_latest_parsed_chunk(device_id, channel_index)
                        if chunk is not None:
                            # Calculate RMS with stability improvements
                            rms = float(np.sqrt(np.mean(np.square(chunk))))
                            
                            # Update running statistics for normalization
                            self._update_running_stats(device_id, channel_index, rms)
                            
                            # Process features in batches
                            self._process_features(device_id, channel_index, chunk)
                            
                            # Send level updates at a reasonable rate (every ~100ms)
                            current_time = time.time()
                            last_update = self._last_level_update.get((device_id, channel_index), 0)
                            if current_time - last_update >= 0.1:
                                self.feature_queue.put({
                                    'type': 'level_update',
                                    'device_id': device_id,
                                    'channel_index': channel_index,
                                    'rms': rms
                                })
                                self._last_level_update[(device_id, channel_index)] = current_time
                                
                    except Exception as e:
                        print(f"Error processing audio for device {device_id}, channel {channel_index}: {e}")
                
                # Small sleep to prevent CPU overuse
                time.sleep(0.001)
                
            except Exception as e:
                print(f"Error in processing loop: {e}")
                time.sleep(0.1)  # Longer sleep on error

    def _process_features(self, device_id: int, channel_index: int, chunk: np.ndarray):
        """Process audio features with improved stability."""
        try:
            # Get the feature processor for this channel
            processor = self._get_or_create_processor(device_id, channel_index)
            
            # Process features in batches for efficiency
            features = processor.process_chunk(chunk)
            
            # Only send features if we have enough data
            if features is not None and len(features) > 0:
                self.feature_queue.put({
                    'type': 'buffer_data',
                    'device_id': device_id,
                    'channel_index': channel_index,
                    'data': features
                })
                
        except Exception as e:
            print(f"Error processing features: {e}")

    def _update_running_stats(self, device_id: int, channel_index: int, rms: float):
        """Update running statistics for audio normalization."""
        key = (device_id, channel_index)
        if key not in self._running_stats:
            self._running_stats[key] = {
                'min_rms': rms,
                'max_rms': rms,
                'count': 1,
                'sum': rms
            }
        else:
            stats = self._running_stats[key]
            stats['min_rms'] = min(stats['min_rms'], rms)
            stats['max_rms'] = max(stats['max_rms'], rms)
            stats['count'] += 1
            stats['sum'] += rms

    # --- ML Processing Loop ---
    def _ml_processing_loop(self):
        """Aggregates features into chunks and sends them for ML processing."""
        print("ML processing loop started.")
        # Calculate how many feature frames approx correspond to ml_chunk_seconds
        # hop_length is likely 512 (librosa default), rate is 44100
        hop_length = 512 # Make this configurable if needed
        frames_per_second = self.audio_manager.RATE / hop_length
        target_feature_frames = int(frames_per_second * self.ml_chunk_seconds)

        while self.running:
            active_keys = list(self.active_channels.keys()) # Snapshot

            for channel_key in active_keys:
                 # Ensure channel is still active
                if channel_key not in self.active_channels:
                    continue

                channel_state = self.active_channels[channel_key]
                feature_buffer = channel_state['feature_buffer']

                # Check if we have enough features buffered
                current_buffered_frames = sum(len(f) for f in feature_buffer)

                if current_buffered_frames >= target_feature_frames:
                    # Concatenate features up to the target length
                    ml_chunk_features_list = []
                    frames_to_consume = target_feature_frames
                    consumed_buffer_indices = 0

                    temp_buffer = list(feature_buffer) # Work on a copy

                    for i, features in enumerate(temp_buffer):
                        if frames_to_consume <= 0:
                            break
                        take_frames = min(len(features), frames_to_consume)
                        ml_chunk_features_list.append(features[:take_frames])
                        frames_to_consume -= take_frames

                        # If we consumed the whole feature block, mark for removal later
                        if take_frames == len(features):
                             consumed_buffer_indices = i + 1
                        else:
                            # Partially consumed, update the block in the original buffer
                            # This requires careful handling or simpler logic (e.g., only consume full blocks)
                            # For simplicity here, let's assume we consume full blocks near the target size
                            # A more robust implementation might handle partial consumption.
                            # Let's adjust: only consume if we have *at least* target_feature_frames
                            pass # Revisit partial consumption if needed


                    # Simplified: Consume full blocks until target is met/exceeded
                    ml_chunk_features_list = []
                    frames_gathered = 0
                    blocks_to_consume = 0
                    for i, features in enumerate(feature_buffer):
                        ml_chunk_features_list.append(features)
                        frames_gathered += len(features)
                        blocks_to_consume = i + 1
                        if frames_gathered >= target_feature_frames:
                            break

                    if frames_gathered >= target_feature_frames:
                        # Combine the features
                        ml_feature_matrix = np.concatenate(ml_chunk_features_list, axis=0)

                        # Remove consumed blocks from the original buffer
                        channel_state['feature_buffer'] = feature_buffer[blocks_to_consume:]

                        print(f"Sending {ml_feature_matrix.shape} feature matrix for ML processing from {channel_key}")
                        # --- Send to ML Model ---
                        # This is where you'd call your ML model prediction function
                        # pop_detected = your_ml_model.predict(ml_feature_matrix)
                        pop_detected = False # Placeholder
                        # ------------------------

                        # Send result to frontend
                        self.feature_queue.put({
                            'type': 'pop_update',
                            'device_id': channel_key[0],
                            'channel_index': channel_key[1],
                            'pop_detected': pop_detected,
                            'timestamp': time.time()
                        })

            time.sleep(0.5) # Check for ML chunks less frequently than main loop
        print("ML processing loop finished.")


    # --- Command Handling ---
    def _handle_command(self, command: dict):
        """Handle commands received from the frontend."""
        if not isinstance(command, dict):
            print(f"Received invalid command format: {command}")
            return

        cmd_type = command.get('type')
        device_id = command.get('device_id')
        channel_index = command.get('channel_index') # Expect channel index now

        print(f"Handling command: {command}")

        if cmd_type == 'start_monitoring':
            if device_id is not None and channel_index is not None:
                self.start_monitoring_channel(device_id, channel_index)
            else:
                print("Error: Missing device_id or channel_index for start_monitoring")

        elif cmd_type == 'stop_monitoring':
             if device_id is not None and channel_index is not None:
                self.stop_monitoring_channel(device_id, channel_index)
             else:
                print("Error: Missing device_id or channel_index for stop_monitoring")

        elif cmd_type == 'start_live_audio':
            if device_id is not None and channel_index is not None:
                self.start_live_audio_stream(device_id, channel_index)
            else:
                print("Error: Missing device_id or channel_index for start_live_audio")

        elif cmd_type == 'stop_live_audio':
            if device_id is not None and channel_index is not None:
                self.stop_live_audio_stream(device_id, channel_index)
            else:
                print("Error: Missing device_id or channel_index for stop_live_audio")

        elif cmd_type == 'get_buffer':
            if device_id is not None and channel_index is not None:
                seconds = command.get('seconds', 300) # Default to 5 minutes (300s)
                # Decide if frontend needs raw bytes or parsed numpy
                # Let's assume parsed for now, but raw might be better for playback libs
                audio_data = self.get_recent_audio_parsed(device_id, channel_index, seconds)
                if audio_data is not None:
                     # Sending large numpy arrays via queue might be inefficient.
                     # Consider alternative IPC or saving to temp file if needed.
                    self.feature_queue.put({
                        'type': 'buffer_data',
                        'device_id': device_id,
                        'channel_index': channel_index,
                        'data': audio_data, # This is a numpy array
                        'timestamp': time.time()
                    })
            else:
                print("Error: Missing device_id or channel_index for get_buffer")

        # Add handling for live audio start/stop if needed
        # elif cmd_type == 'start_live_audio': ...
        # elif cmd_type == 'stop_live_audio': ...

        else:
            print(f"Received unknown command type: {cmd_type}")

    def start_live_audio_stream(self, device_id: int, channel_index: int):
        """Start streaming live audio data to the live_audio_queue."""
        channel_key = (device_id, channel_index)
        if channel_key not in self.active_channels:
            print(f"Error: Cannot start live audio for inactive channel {channel_key}")
            return

        self.active_channels[channel_key]['streaming'] = True
        print(f"Started live streaming for device {device_id}, channel {channel_index}")

    def stop_live_audio_stream(self, device_id: int, channel_index: int):
        """Stop streaming live audio data."""
        channel_key = (device_id, channel_index)
        if channel_key in self.active_channels:
            self.active_channels[channel_key]['streaming'] = False
            print(f"Stopped live streaming for device {device_id}, channel {channel_index}")

    def _process_live_audio(self, device_id: int, channel_index: int):
        """Process and forward live audio data."""
        while self._should_process_live_audio.get((device_id, channel_index), False):
            try:
                # Get latest chunk from AudioManager
                audio_chunk = self.audio_mgr.get_latest_raw_chunk(device_id, channel_index)
                if audio_chunk is None:
                    time.sleep(0.001)
                    continue

                # Forward raw audio for playback
                if not self.live_audio_queue.full():
                    self.live_audio_queue.put({
                        'type': 'live_audio',
                        'data': audio_chunk
                    })

                # Clear any old messages from the queue
                while not self.live_audio_queue.empty():
                    try:
                        self.live_audio_queue.get_nowait()
                        self.live_audio_queue.task_done()
                    except queue.Empty:
                        break

                time.sleep(0.001)  # Prevent CPU thrashing
            except Exception as e:
                print(f"Error in live audio processing: {e}")
                time.sleep(0.1)

    def _process_features(self, device_id: int, channel_index: int):
        """Process audio features and detect pops."""
        feature_matrix = []
        last_feature_time = time.time()
        FEATURE_INTERVAL = 0.1  # Process features every 100ms
        
        while self._should_process_features.get((device_id, channel_index), False):
            try:
                current_time = time.time()
                
                # Get latest normalized chunk
                chunk = self.audio_mgr.get_latest_parsed_chunk(device_id, channel_index)
                if chunk is None:
                    time.sleep(0.001)
                    continue
                
                # Calculate RMS level
                rms = np.sqrt(np.mean(np.square(chunk)))
                if not self.feature_queue.full():
                    self.feature_queue.put({
                        'type': 'level_update',
                        'rms': float(rms)
                    })
                
                # Process features at regular intervals
                if current_time - last_feature_time >= FEATURE_INTERVAL:
                    # Get recent audio segment
                    audio_segment = self.audio_mgr.get_buffer_segment_parsed(
                        device_id, channel_index, seconds=0.5
                    )
                    
                    if audio_segment is not None:
                        # Extract features
                        features = self._extract_features(audio_segment)
                        if features is not None:
                            # Update feature matrix
                            feature_matrix = features
                            
                            if not self.feature_queue.full():
                                self.feature_queue.put({
                                    'type': 'buffer_data',
                                    'data': feature_matrix
                                })
                                
                                # Clear old feature data
                                feature_matrix = []
                                
                            # Pop detection update
                            self.feature_queue.put({
                                'type': 'pop_update',
                                'detected': self._detect_pop(features)
                            })
                    
                    last_feature_time = current_time
                
                time.sleep(0.001)  # Prevent CPU thrashing
                
            except Exception as e:
                print(f"Error processing features: {e}")
                time.sleep(0.1)

    def _extract_features(self, audio_data):
        """Extract audio features for pop detection."""
        try:
            if len(audio_data) == 0:
                return None
                
            # Extract core features
            rms = librosa.feature.rms(y=audio_data)[0]
            zcr = librosa.feature.zero_crossing_rate(audio_data)[0]
            onset_env = librosa.onset.onset_strength(y=audio_data, sr=44100)
            
            # Print shapes for debugging
            print(f"Extracted RMS shape: {rms.shape}")
            print(f"Extracted ZCR shape: {zcr.shape}")
            print(f"Extracted Onset strength shape: {onset_env.shape}")
            
            # Ensure all features have the same length
            min_len = min(len(rms), len(zcr), len(onset_env))
            feature_matrix = np.vstack([
                rms[:min_len],
                zcr[:min_len],
                onset_env[:min_len]
            ]).T
            
            print(f"Created feature matrix with shape: {feature_matrix.shape}")
            return feature_matrix
            
        except Exception as e:
            print(f"Error extracting features: {e}")
            return None

    def start_processing(self, device_id: int, channel_index: int):
        """Start the audio processing pipeline with improved stability."""
        if self._processing_thread and self._processing_thread.is_alive():
            print("Processing already running")
            return
            
        try:
            self.audio_manager.start_recording(device_id, channel_index)
            self._stop_event.clear()
            self._processing_thread = threading.Thread(
                target=self._processing_loop,
                args=(device_id, channel_index),
                daemon=True
            )
            self._processing_thread.start()
            print(f"Started processing for device {device_id}, channel {channel_index}")
            
        except Exception as e:
            print(f"Error starting processing: {e}")
            self.stop_processing()
            
    def stop_processing(self):
        """Stop the audio processing pipeline gracefully."""
        try:
            self._stop_event.set()
            if self._processing_thread:
                self._processing_thread.join(timeout=1.0)
            self.audio_manager.cleanup()
            self.feature_processor.reset()
            print("Stopped processing")
            
        except Exception as e:
            print(f"Error stopping processing: {e}")
            
    def _processing_loop(self, device_id: int, channel_index: int):
        """Main processing loop with improved timing and error handling."""
        consecutive_errors = 0
        MAX_ERRORS = 5
        
        while not self._stop_event.is_set():
            try:
                # Respect minimum processing interval
                current_time = time.time()
                time_since_last = current_time - self.last_process_time
                if time_since_last < self.MIN_PROCESS_INTERVAL:
                    time.sleep(self.MIN_PROCESS_INTERVAL - time_since_last)
                    
                # Get latest audio chunk
                chunk = self.audio_manager.get_latest_parsed_chunk(device_id, channel_index)
                if chunk is None:
                    continue
                    
                # Process features
                features = self.feature_processor.process_chunk(chunk)
                if features is not None and len(features) > 0:
                    # Store or analyze features here
                    pass
                    
                self.last_process_time = time.time()
                consecutive_errors = 0  # Reset error count on success
                
            except Exception as e:
                print(f"Error in processing loop: {e}")
                consecutive_errors += 1
                if consecutive_errors >= MAX_ERRORS:
                    print("Too many consecutive errors, stopping processing")
                    break
                time.sleep(0.1)  # Brief pause before retry
                
        self.stop_processing()
        
    def list_input_devices(self) -> List[dict]:
        """List available audio input devices."""
        return self.audio_manager.list_input_devices()
