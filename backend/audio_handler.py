import pyaudio

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

# Example usage (for testing this file directly)
if __name__ == '__main__':
    available_devices = list_audio_devices()
    if available_devices:
        print("\nFunction returned:")
        # print(available_devices) # Can print the whole list
        # Or iterate nicely:
        for device in available_devices:
             print(f"- Index: {device['index']}, Name: {device['name']}, Channels: {device['channels']}")
    else:
        print("\nFunction returned an empty list (no devices found or error occurred).")