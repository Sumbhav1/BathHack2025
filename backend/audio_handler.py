import pyaudio
import numpy as np
import time
import threading
from queue import Queue, Full # Import Queue for testing

# Constants
RATE = 16000
CHUNK_SIZE = 1024
FORMAT = pyaudio.paFloat32
FORMAT_NP = np.float32

class AudioCapture:
    """
    Manages capturing audio from a specific device and channel using PyAudio callback.
    Distributes the selected channel's audio chunks to multiple output queues.
    """
    def __init__(self, device_index, target_channel, output_queues, stop_event):
        """
        Initializes the AudioCapture instance.

        Args:
            device_index (int): Index of the audio input device.
            target_channel (int): 0-based index of the channel to capture.
            output_queues (dict): Dictionary mapping consumer names (str) to
                                  output Queues (e.g., {'ml': ml_q, 'stream': stream_q}).
            stop_event (threading.Event): Event to signal stopping the capture.
        """
        self.device_index = device_index
        self.target_channel = target_channel
        self.output_queues = output_queues
        self.stop_event = stop_event
        self.rate = RATE
        self.chunk_size = CHUNK_SIZE
        self.format = FORMAT
        self.format_np = FORMAT_NP

        self._p = None
        self._stream = None
        self._num_channels = 0 # Actual number of channels supported by the device

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Internal callback function executed by PyAudio."""
        if status:
            print(f"PyAudio Status [Dev:{self.device_index}/Ch:{self.target_channel}]: {status}")

        try:
            # 1. Convert raw bytes to numpy array
            numpy_chunk = np.frombuffer(in_data, dtype=self.format_np)

            # 2. Reshape based on channels
            if self._num_channels > 0:
                reshaped_chunk = numpy_chunk.reshape((frame_count, self._num_channels))

                # 3. Select the target channel's data
                if 0 <= self.target_channel < self._num_channels:
                    channel_data = reshaped_chunk[:, self.target_channel].copy() # Use copy

                    # 4. Distribute the selected channel data to ALL output queues
                    for key, queue in self.output_queues.items():
                        try:
                            queue.put_nowait(channel_data)
                        except Full:
                            print(f"Warning [Dev:{self.device_index}/Ch:{self.target_channel}]: Queue '{key}' is full. Dropping chunk.")
                        except Exception as q_err:
                             print(f"Error putting data into queue '{key}' [Dev:{self.device_index}/Ch:{self.target_channel}]: {q_err}")
                else:
                     print(f"Error [Dev:{self.device_index}/Ch:{self.target_channel}]: Invalid target_channel {self.target_channel} inside callback.")
            else:
                 print(f"Error [Dev:{self.device_index}/Ch:{self.target_channel}]: _num_channels is {self._num_channels} inside callback.")

        except ValueError as ve:
             print(f"Callback ValueError [Dev:{self.device_index}/Ch:{self.target_channel}]: {ve}. Check CHUNK_SIZE and stream parameters.")
        except Exception as e:
            print(f"Error in audio callback [Dev:{self.device_index}/Ch:{self.target_channel}]: {e}")

        # Check stop event - allows faster shutdown if needed, but main loop also checks
        # if self.stop_event.is_set():
        #     return (None, pyaudio.paComplete)

        return (None, pyaudio.paContinue) # Continue stream

    def start(self):
        """Initializes PyAudio, opens and starts the audio stream."""
        print(f"AudioCapture: Starting for Device {self.device_index}, Channel {self.target_channel}")
        if self._p is not None or self._stream is not None:
             print("AudioCapture: Already started or not properly stopped.")
             return False

        try:
            self._p = pyaudio.PyAudio()

            # Get device info and validate channel
            device_info = self._p.get_device_info_by_index(self.device_index)
            self._num_channels = device_info.get('maxInputChannels')
            if self._num_channels is None or self._num_channels <= 0:
                 print(f"Error: Device {self.device_index} reports no input channels.")
                 self.stop()
                 return False
            if not 0 <= self.target_channel < self._num_channels:
                print(f"Error: Requested channel {self.target_channel} is out of range for device {self.device_index} (max: {self._num_channels-1})")
                self.stop()
                return False

            print(f"AudioCapture: Device {self.device_index} - '{device_info.get('name')}' supports {self._num_channels} channels.")

            # Open stream using the instance method as callback
            self._stream = self._p.open(format=self.format,
                                        channels=self._num_channels,
                                        rate=self.rate,
                                        input=True,
                                        input_device_index=self.device_index,
                                        frames_per_buffer=self.chunk_size,
                                        stream_callback=self._audio_callback)

            print(f"AudioCapture: Stream opened for Device {self.device_index}, Channel {self.target_channel}")
            self._stream.start_stream()
            print(f"AudioCapture: Stream started.")
            return True # Success

        except Exception as e:
            print(f"Error during AudioCapture start for Device {self.device_index}: {e}")
            self.stop() # Ensure cleanup on error
            return False

    def stop(self):
        """Stops the audio stream and terminates the PyAudio instance."""
        print(f"AudioCapture: Stopping for Device {self.device_index}, Channel {self.target_channel}")
        if self._stream is not None:
            try:
                if self._stream.is_active():
                    self._stream.stop_stream()
                self._stream.close()
                print("AudioCapture: Stream closed.")
            except Exception as e:
                print(f"Error closing stream: {e}")
            finally:
                 self._stream = None # Ensure stream is marked as closed

        if self._p is not None:
            try:
                self._p.terminate()
                print("AudioCapture: PyAudio terminated.")
            except Exception as e:
                print(f"Error terminating PyAudio: {e}")
            finally:
                self._p = None # Ensure PyAudio is marked as terminated

    def run(self):
        """Starts the capture and blocks until the stop_event is set."""
        if self.start():
            print(f"AudioCapture: Running... Waiting for stop event for Device {self.device_index}, Channel {self.target_channel}")
            # Wait for stop signal while stream is active
            while self._stream is not None and self._stream.is_active() and not self.stop_event.is_set():
                 time.sleep(0.1) # Prevent busy-waiting
            print(f"AudioCapture: Stop event received or stream inactive for Device {self.device_index}, Channel {self.target_channel}.")
        else:
             print(f"AudioCapture: Failed to start stream for Device {self.device_index}, Channel {self.target_channel}. Not running.")
        # Ensure cleanup happens after the loop finishes or if start failed
        self.stop()
        print(f"AudioCapture: Run method finished for Device {self.device_index}, Channel {self.target_channel}.")

def list_audio_devices():
    """
    Lists available audio input devices and returns their details.
    Also prints the list to the console.

    Returns:
        list: A list of dictionaries, where each dictionary represents an
              input device and contains 'index', 'name', and 'channels' keys.
              Returns an empty list if no input devices are found or an error occurs.
    """
    devices = []
    p = None
    try:
        p = pyaudio.PyAudio()
        host_api_info = p.get_host_api_info_by_index(0)
        num_devices = host_api_info.get('deviceCount', 0)

        for i in range(num_devices):
            device_info = p.get_device_info_by_host_api_device_index(0, i)
            if device_info.get('maxInputChannels', 0) > 0:
                device_details = {
                    'index': i,
                    'name': device_info.get('name'),
                    'channels': device_info.get('maxInputChannels')
                }
                devices.append(device_details)

    except Exception as e:
        print(f"Error listing audio devices: {e}")
        # Ensure devices list is empty on error
        devices = []
    finally:
        if p is not None:
            p.terminate()

    return devices

# --- Main Test Block (Updated for Class Structure) ---
if __name__ == '__main__':
    available_devices = list_audio_devices()
    if not available_devices:
        print("\nNo input devices found. Cannot run capture test.")
    else:
        print("\n--- Testing AudioCapture Class --- ")
        print("Select a Device Index and Channel Index from the list above.")
        try:
            test_device_index = int(input("Enter Device Index: "))
            # Basic validation against returned list
            if not any(d['index'] == test_device_index for d in available_devices):
                print(f"Error: Device index {test_device_index} not found in the list.")
                exit()

            selected_device_info = next((d for d in available_devices if d['index'] == test_device_index), None)
            max_channels = selected_device_info['channels']

            test_channel_index = int(input(f"Enter Channel Index (0 to {max_channels-1}): "))
            if not 0 <= test_channel_index < max_channels:
                 print(f"Error: Channel index {test_channel_index} is out of range (0-{max_channels-1}).")
                 exit()

        except ValueError:
            print("Invalid input. Please enter numbers.")
            exit()
        except Exception as e:
            print(f"An error occurred during input: {e}")
            exit()

        # Create dummy queues for testing distribution
        test_ml_queue = Queue(maxsize=200) # Increased size slightly
        test_volume_queue = Queue(maxsize=200)
        test_stream_queue = Queue(maxsize=200) # For future frontend stream
        test_output_queues = {
            'ml': test_ml_queue,
            'volume': test_volume_queue,
            'stream': test_stream_queue
        }
        test_stop_event = threading.Event()

        print(f"\nPreparing to start capture using AudioCapture class for device {test_device_index}, channel {test_channel_index}.")
        print(f"Data will be distributed to queues: {list(test_output_queues.keys())}")

        # Create an instance of the capture class
        capture_instance = AudioCapture(
            device_index=test_device_index,
            target_channel=test_channel_index,
            output_queues=test_output_queues,
            stop_event=test_stop_event
        )

        # Run the capture instance in a separate thread
        # Target the 'run' method which handles start, wait, and stop
        capture_thread = threading.Thread(target=capture_instance.run, daemon=True)

        print("Starting capture thread...")
        capture_thread.start()

        # Let it run for a duration or until interrupted
        run_duration = 10 # seconds
        print(f"Capture thread started. Letting it run for {run_duration} seconds...")
        print("Check console output for stream/callback messages and queue warnings.")
        print("Press Ctrl+C to stop earlier.")
        try:
            start_time = time.time()
            while time.time() - start_time < run_duration:
                if not capture_thread.is_alive():
                    print("Capture thread terminated unexpectedly.")
                    break
                # Periodically check queue sizes (optional)
                print(f"Queue sizes: ML={test_ml_queue.qsize()}, Vol={test_volume_queue.qsize()}, Stream={test_stream_queue.qsize()}   \r", end="")
                time.sleep(0.5)
            else:
                 print(f"\n{run_duration} seconds elapsed.") # Newline after loop finishes

        except KeyboardInterrupt:
            print("\nCtrl+C detected.")
        except Exception as e:
             print(f"An error occurred while waiting: {e}")

        # Signal the thread to stop
        if capture_thread.is_alive():
            print("Signalling capture thread to stop...")
            test_stop_event.set()

            # Wait for the thread to finish cleanup
            print("Waiting for capture thread to join...")
            capture_thread.join(timeout=5.0) # Add a timeout
            if capture_thread.is_alive():
                print("Warning: Capture thread did not join within timeout.")
            else:
                print("Capture thread joined successfully.")
        else:
             print("Capture thread was not running when stop was attempted.")

        # Check final queue sizes
        print("\nFinal Queue sizes:")
        print(f" - ML Queue: {test_ml_queue.qsize()} chunks")
        print(f" - Volume Queue: {test_volume_queue.qsize()} chunks")
        print(f" - Stream Queue: {test_stream_queue.qsize()} chunks")
        print("\n--- Test Finished --- ")