import React, { useState, useEffect } from "react";
import { FaPlus } from "react-icons/fa";
import { io } from "socket.io-client";
import DeviceSelector from "./components/DeviceSelector";
import ChannelSelector from "./components/ChannelSelector";
import WarningPopUp from "./components/WarningPopUp";
import "./styles/App.css";

const App = () => {
  const [audioDevices, setAudioDevices] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [selectedChannel, setSelectedChannel] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [activeDevices, setActiveDevices] = useState([]);
  const [socket, setSocket] = useState(null);

  // Initialize socket connection
  useEffect(() => {
    const newSocket = io("http://localhost:5000");
    setSocket(newSocket);

    newSocket.on("warning", (data) => {
      setWarnings((prevWarnings) => [
        ...prevWarnings,
        { id: Date.now(), message: `Source ${data.source}: ${data.message}` },
      ]);
    });

    newSocket.on("audio_error", (data) => {
      setWarnings((prevWarnings) => [
        ...prevWarnings,
        { id: Date.now(), message: `Audio Error: ${data.message}` },
      ]);
      // Reset playing state for the affected device
      setActiveDevices(devices => 
        devices.map(d => 
          d.id === data.deviceId ? { ...d, isPlaying: false } : d
        )
      );
    });

    return () => {
      newSocket.disconnect();
    };
  }, []);

  // Fetch available audio devices from the backend
  useEffect(() => {
    const fetchAudioDevices = async () => {
      try {
        const response = await fetch("http://localhost:5000/api/audio-devices");
        const data = await response.json();
        setAudioDevices(data);
      } catch (error) {
        console.error("Error fetching audio devices:", error);
        setWarnings(prev => [...prev, {
          id: Date.now(),
          message: "Failed to fetch audio devices. Please check if the backend server is running."
        }]);
      }
    };

    fetchAudioDevices();
  }, []);

  const handleDeviceSelect = (event) => {
    const deviceIndex = parseInt(event.target.value, 10);
    const selected = audioDevices.find(
      (device) => device.index === deviceIndex
    );
    setSelectedDevice(selected);
    setSelectedChannel(null);
  };

  const handleChannelSelect = (event) => {
    const channelIndex = parseInt(event.target.value, 10);
    setSelectedChannel(channelIndex);
  };

  const handleAddDevice = () => {
    if (selectedDevice && selectedChannel !== null) {
      const newDevice = {
        id: Date.now(),
        device: selectedDevice,
        channel: selectedChannel,
        isPlaying: false
      };
      setActiveDevices([...activeDevices, newDevice]);
      setSelectedDevice(null);
      setSelectedChannel(null);
    }
  };

  const handlePlayPause = (deviceId) => {
    const device = activeDevices.find(d => d.id === deviceId);
    if (!device) return;

    if (device.isPlaying) {
      // Stop audio capture
      socket.emit('stop_audio', {
        deviceId: deviceId,
        deviceIndex: device.device.index,
        channel: device.channel
      });
    } else {
      // Start audio capture
      socket.emit('start_audio', {
        deviceId: deviceId,
        deviceIndex: device.device.index,
        channel: device.channel
      });
    }

    // Update device state
    setActiveDevices(devices =>
      devices.map(d =>
        d.id === deviceId ? { ...d, isPlaying: !d.isPlaying } : d
      )
    );
  };

  return (
    <div className="app">
      <h1>Audio Device Hub</h1>

      <div className="device-selection">
        <DeviceSelector
          devices={audioDevices}
          selectedDevice={selectedDevice}
          onDeviceSelect={handleDeviceSelect}
        />
        {selectedDevice && (
          <ChannelSelector
            channels={selectedDevice.channels}
            selectedChannel={selectedChannel}
            onChannelSelect={handleChannelSelect}
          />
        )}
        {selectedDevice && selectedChannel !== null && (
          <button className="add-device-button" onClick={handleAddDevice}>
            <FaPlus /> Add Device
          </button>
        )}
      </div>

      <div className="device-info-container">
        {activeDevices.map((device) => (
          <button
            key={device.id}
            className="device-info-button"
            onClick={() => handlePlayPause(device.id)}
          >
            {device.device.name}
            <br />
            Channel {device.channel + 1}
            <br />
            <br />
            {device.isPlaying ? "Stop" : "Play"}
          </button>
        ))}
      </div>

      <audio id="audio-element" controls style={{ display: "none" }} />

      <div className="warning-container">
        {warnings.map((warning) => (
          <WarningPopUp
            key={warning.id}
            warning={warning}
            onClose={(id) => setWarnings(warnings.filter((w) => w.id !== id))}
          />
        ))}
      </div>
    </div>
  );
};

export default App;
