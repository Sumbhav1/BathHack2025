// components/DeviceSelector.jsx
import React from 'react';
import '../styles/DeviceSelector.css';

const DeviceSelector = ({ devices, onDeviceSelect, selectedDevice }) => {
  return (
    <div className="device-selector">
      <label htmlFor="device-select">Select an Audio Device</label>
      <select
        id="device-select"
        value={selectedDevice ? selectedDevice.index : ""}
        onChange={onDeviceSelect}
      >
        <option value="">-- Choose a device --</option>
        {devices.map((device) => (
          <option key={device.index} value={device.index}>
            {device.name}
          </option>
        ))}
      </select>
    </div>
  );
};

export default DeviceSelector;



