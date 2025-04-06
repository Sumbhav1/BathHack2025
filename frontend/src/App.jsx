import React, { useState, useEffect } from "react";
import { FaPlus } from "react-icons/fa"; // Importing the plus icon from react-icons
import { io } from "socket.io-client";
import DeviceSelector from "./components/DeviceSelector";
import WarningPopUp from "./components/WarningPopUp";
import "./styles/App.css"; // External CSS

const App = () => {
  const [audioDevices, setAudioDevices] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioStream, setAudioStream] = useState(null);

  // Socket connection to listen for warnings
  useEffect(() => {
    const socket = io("http://localhost:5000");

    socket.on("warning", (data) => {
      setWarnings((prevWarnings) => [
        ...prevWarnings,
        { id: Date.now(), message: `Source ${data.source}: ${data.message}` },
      ]);
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  // Fetch available audio devices from the backend
  useEffect(() => {
    const fetchAudioDevices = async () => {
      const response = await fetch("http://localhost:5000/api/audio-devices");
      const data = await response.json();
      setAudioDevices(data);
    };

    fetchAudioDevices();
  }, []);

  // Handle selecting a device
  const handleDeviceSelect = (event) => {
    const selected = audioDevices.find(
      (device) => device.index === event.target.value
    );
    setSelectedDevice(selected);
  };
  const handlePlayPause = async () => {
    if (isPlaying) {
      // Stop the audio stream
      audioStream.getTracks().forEach((track) => track.stop());
      setIsPlaying(false);
    } else {
      // Start capturing audio from the selected device
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { deviceId: selectedDevice.deviceId },
        });
  
        const audioElement = document.getElementById("audio-element");
        audioElement.srcObject = stream;
        await audioElement.play(); // Ensure the play action is complete
  
        setAudioStream(stream);
        setIsPlaying(true);
      } catch (error) {
        console.error("Error playing audio stream: ", error);
      }
    }
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
      </div>

      {selectedDevice && (
        <div className="device-details">
          <h3>Selected Device: {selectedDevice.name}</h3>
          <button>Play</button>
        </div>
      )}

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
