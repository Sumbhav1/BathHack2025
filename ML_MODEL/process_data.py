import librosa
import numpy as np
import os
import argparse

# Constants
RATE = 16000  # Match sample rate with ml_interface.py
n_fft = 2048  # Match FFT size with ml_interface.py
hop_length = 512  # Consistent hop length

def extract_features_from_file(audio_path):
    """Loads an audio file, extracts frame-level features, and returns the feature matrix."""
    try:
        audio_data, sr = librosa.load(audio_path, sr=RATE, mono=True)
        print(f"Loaded '{audio_path}', Sample Rate: {sr}, Duration: {len(audio_data)/sr:.2f}s")

        if len(audio_data) == 0:
            print(f"Warning: Audio file '{audio_path}' is empty or could not be loaded properly.")
            return None

        # Normalize audio (peak normalization)
        peak_value = np.max(np.abs(audio_data))
        if peak_value > 1e-6:  # Avoid division by zero or near-zero
            audio_data = audio_data / peak_value

        # Check if audio is long enough for FFT
        if len(audio_data) < n_fft:
            print(f"Warning: Audio length ({len(audio_data)}) is shorter than n_fft ({n_fft})")
            return None

        # Extract features using consistent parameters
        rms = librosa.feature.rms(y=audio_data, frame_length=n_fft, hop_length=hop_length)[0]
        zcr = librosa.feature.zero_crossing_rate(y=audio_data, frame_length=n_fft, hop_length=hop_length)[0]
        onset_env = librosa.onset.onset_strength(y=audio_data, sr=RATE, hop_length=hop_length)
        spectral_centroid = librosa.feature.spectral_centroid(y=audio_data, sr=sr, n_fft=n_fft, hop_length=hop_length)[0]
        spectral_flatness = librosa.feature.spectral_flatness(y=audio_data, n_fft=n_fft, hop_length=hop_length)[0]

        # Ensure all features have the same number of frames using rms as reference
        target_frames = rms.shape[0]
        onset_env = np.resize(onset_env, target_frames)
        spectral_centroid = np.resize(spectral_centroid, target_frames)
        spectral_flatness = np.resize(spectral_flatness, target_frames)
        zcr = np.resize(zcr, target_frames)

        # Stack features and transpose to match ml_interface.py output shape (num_frames, 5)
        feature_matrix = np.vstack([rms, zcr, onset_env, spectral_centroid, spectral_flatness]).T
        print(f"Extracted feature matrix shape: {feature_matrix.shape}")

        return feature_matrix

    except Exception as e:
        print(f"Error processing file '{audio_path}': {e}")
        return None

def process_directory(directory_path):
    """Process all audio files in the directory and return features and labels."""
    features = []
    labels = []

    for label_dir in os.listdir(directory_path):
        label_path = os.path.join(directory_path, label_dir)
        if os.path.isdir(label_path):
            # Set the label based on the folder name
            label = 0 if label_dir == "GoodSound" else 1  # 0 for "good", 1 for "bad"
            
            for filename in os.listdir(label_path):
                if filename.endswith(".wav"):  # Process only .wav files
                    audio_path = os.path.join(label_path, filename)
                    feature_matrix = extract_features_from_file(audio_path)
                    
                    if feature_matrix is not None:
                        features.append(feature_matrix)
                        # Label all frames in this clip with the clip's label
                        labels.extend([label] * len(feature_matrix))  # One label per frame
                    else:
                        print(f"Skipping file {filename} due to extraction failure.")

    return features, labels

def save_features_and_labels(features, labels, output_dir, dataset_name):
    """Save the extracted features and labels to a .npy file."""
    combined_features = np.concatenate(features, axis=0)
    combined_labels = np.array(labels)
    os.makedirs(output_dir, exist_ok=True)
    # Save features and labels
    save_path = os.path.join(output_dir, f"{dataset_name}_features.npy")
    np.save(save_path, combined_features)
    print(f"Features saved to '{save_path}'")

    label_path = os.path.join(output_dir, f"{dataset_name}_labels.npy")
    np.save(label_path, combined_labels)
    print(f"Labels saved to '{label_path}'")

if __name__ == "__main__":
    # --- Command Line Argument Parsing ---
    parser = argparse.ArgumentParser(description="Extract audio features (RMS, ZCR, Onset Strength) from a directory of audio files.")
    parser.add_argument("input_dir", help="Directory containing subdirectories for each class ('good' and 'bad').")
    parser.add_argument("-o", "--output_dir", default=".", help="Directory to save the output .npy files (default: current directory).")
    parser.add_argument("-d", "--dataset_name", default="training_data", help="Dataset name for the output files (default: 'training_data').")

    args = parser.parse_args()

    # --- Process the Directory and Extract Features ---
    features, labels = process_directory(args.input_dir)

    if features:
        # Save the features and labels
        save_features_and_labels(features, labels, args.output_dir, args.dataset_name)
        print(f"Total number of feature matrices: {len(features)}")
        combined_features = np.concatenate(features, axis=0)
        print(f"Shape of combined features: {combined_features.shape}")
        print(f"Total number of labels: {len(labels)}")
    else:
        print(f"No valid features found in the directory '{args.input_dir}'.")
