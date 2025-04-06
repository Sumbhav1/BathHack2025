// components/WarningPopUp.jsx
import React, { useEffect } from "react";
import "../styles/WarningPopUp.css"; // External CSS

const WarningPopUp = ({ warning, onClose }) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onClose(warning.id); // Close the pop-up after 5 seconds
    }, 5000);

    return () => clearTimeout(timer); // Cleanup the timer on unmount
  }, [warning, onClose]);

  return (
    <div className="warning-popup">
      <span>{warning.message}</span>
    </div>
  );
};

export default WarningPopUp;
