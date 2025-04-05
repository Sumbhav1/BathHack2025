import pyaudio

def get_device_list():
    """
    Get a list of audio devices.
    :return: List of audio devices.
    """
    p = pyaudio.PyAudio()
    device_list = []
    for i in range(p.get_device_count()):
        device_info = p.get_device_info_by_index(i)
        device_list.append(device_info)
    p.terminate()

    for idx, device in enumerate(device_list):
        device_list[idx] = {"id": device['index'], "name": device['name'], "maxInputChannels": device['maxInputChannels']}


    return device_list

def get_input_channels(device_index):
    """
    Get the number of input channels for a given device index.
    :param device_index: Index of the audio device.
    :return: Number of input channels.
    """
    p = pyaudio.PyAudio()
    device_info = p.get_device_info_by_index(device_index)
    p.terminate()
    return device_info['maxInputChannels'] if device_info['maxInputChannels'] > 0 else 0

if __name__ == "__main__":
    # Example usage
    devices = get_device_list()
    print(devices)

    print("Input Channels for Device 0:", get_input_channels(0))
