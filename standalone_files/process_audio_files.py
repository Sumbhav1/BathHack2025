# python process_audio_files.py C:\Users\finnt\OneDrive - University of Bath\[01] Computer Science\Year 1\Semester 2\Hackathon\Good Sound.wav -o training_data

import librosa
import numpy as np
import os
import argparse

# Constants (should match main.py if consistency is desired)
RATE = 44100 # Target sample rate for loading audio

def extract_features_from_file(audio_path):
    """Loads an audio file, extracts features, and returns the feature matrix."""
    try:
        # Load audio file - librosa automatically resamples to RATE
        # It also converts to mono and normalizes to [-1, 1] by default
        audio_data, sr = librosa.load(audio_path, sr=RATE, mono=True)
        print(f"Loaded '{audio_path}', Sample Rate: {sr}, Duration: {len(audio_data)/sr:.2f}s")

        if len(audio_data) == 0:
            print(f"Warning: Audio file '{audio_path}' is empty or could not be loaded properly.")
            return None

        # --- Extract Core Features (same as main.py) ---
        # 1. RMS Energy
        rms = librosa.feature.rms(y=audio_data)[0]

        # 2. Zero Crossing Rate
        zcr = librosa.feature.zero_crossing_rate(audio_data)[0]

        # 3. Onset Strength Envelope
        onset_env = librosa.onset.onset_strength(y=audio_data, sr=RATE)

        # --- Align and Combine Features ---
        min_len = min(len(rms), len(zcr), len(onset_env))
        if min_len == 0:
            print(f"Warning: Could not extract features for '{audio_path}'.")
            return None

        rms = rms[:min_len]
        zcr = zcr[:min_len]
        onset_env = onset_env[:min_len]

        feature_matrix = np.vstack([rms, zcr, onset_env]).T
        print(f"Extracted feature matrix shape: {feature_matrix.shape}")

        return feature_matrix

    except Exception as e:
        print(f"Error processing file '{audio_path}': {e}")
        return None

if __name__ == "__main__":
    # --- Command Line Argument Parsing ---
    parser = argparse.ArgumentParser(description="Extract audio features (RMS, ZCR, Onset Strength) from an audio file.")
    parser.add_argument("input_file", help="Path to the input audio file (e.g., wav, mp3).")
    parser.add_argument("-o", "--output_dir", default=".", help="Directory to save the output .npy file (default: current directory).")

    args = parser.parse_args()

    # --- Feature Extraction ---
    feature_matrix = extract_features_from_file(args.input_file)

    if feature_matrix is not None:
        # --- Save the Feature Matrix ---
        # Create output filename based on input filename
        base_filename = os.path.splitext(os.path.basename(args.input_file))[0]
        output_filename = f"{base_filename}_features.npy"
        save_path = os.path.join(args.output_dir, output_filename)

        # Ensure output directory exists
        os.makedirs(args.output_dir, exist_ok=True)

        np.save(save_path, feature_matrix)
        print(f"Feature matrix saved to '{save_path}'")
    else:
        print(f"Failed to extract features from '{args.input_file}'.")

# --- How to process multiple files ---
# You could modify this script to loop through files in a directory:
# import glob
# audio_files = glob.glob('/path/to/your/audio/*.wav') # Get all wav files
# all_features = []
# for file_path in audio_files:
#     features = extract_features_from_file(file_path)
#     if features is not None:
#         # You might want to store features along with filenames or labels
#         all_features.append(features)
#         # Or save each feature matrix individually as done above
# # If collecting all features:
# # combined_features = np.concatenate(all_features, axis=0) # Combine along time axis
# # np.save('combined_training_features.npy', combined_features)
