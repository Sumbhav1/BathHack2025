# 📡 RF Audio Monitor – Real-Time Radio Mic Fault Detection

🏆 **Best Overall Project – Hackathon 2025**

RF Audio Monitor is a real-time monitoring dashboard that uses machine learning to detect microphone issues like **popping** caused by **loose or snapped radio mic cables** — helping event technicians catch faults before they ruin a performance.

---

## 🚀 What It Does

- 🎧 Detects subtle mic faults (e.g. popping, snaps) in live audio streams.
- 📊 Visualizes device activity and audio status in a clean React dashboard.
- ⚠️ Sends real-time alerts when a fault is detected using WebSockets.

---

## 🧠 How It Works

- **Frontend:** Built with React + Tailwind CSS for responsive, real-time UI.
- **Backend:** Python (Flask + PyAudio) streams and analyzes live audio from multiple devices.
- **Machine Learning:** A Random Forest model trained on audio features like:
  - Spectral Flatness
  - RMS Energy
  - Zero Crossing Rate
  - Spectral Centroid
- **Multithreading:** Handles multiple devices in parallel using Python threads.
- **Real-Time Alerts:** WebSocket-based live warning system for fast feedback.

---

## ⚙️ Tech Stack

- 🧩 **Frontend:** React, Tailwind CSS  
- 🧠 **Backend:** Python, Flask, PyAudio, WebSockets  
- 📊 **ML:** Librosa, scikit-learn (Random Forest Classifier)  
- 🚀 **Workflow:** Agile methodology in a 24-hour hackathon sprint using version control

---

## 👥 Team

Built by Sumbhav, Finn and Alyson at Hackathon 2025  

---

## 📥 Clone & Run

1. **Clone the repository:**

   bash
   
   `git clone https://github.com/Sumbhav1/rf-audio-monitor.git
   cd rf-audio-monitor`
   
Frontend Setup:

Navigate to the frontend/ directory.

Run 
`npm install` 
to install the required dependencies.

bash
`cd frontend
npm install`

Backend Setup:

Navigate to the backend/ directory.

Install the Python dependencies from requirements.txt.

  bash
  `cd backend
  pip install -r requirements.txt`
  Run the Application:

Start the frontend:

  bash
  
  `npm run dev`
  
  In a new terminal, run the backend:

  ```bash
  python server.py
  python main_backend.py



