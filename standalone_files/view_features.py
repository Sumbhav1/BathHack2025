import numpy as np

# Load the feature matrix
feature_matrix = np.load('C:/Users/finnt/Documents/audio_features.npy')

# Print matrix info
print("Feature Matrix Shape:", feature_matrix.shape)
print("\nFirst 10 frames of data:")
print("Frame\t\tRMS Energy\tZero Crossing\tOnset Strength")
print("-" * 65)

# Print first 10 rows
for i in range(min(10, len(feature_matrix))):
    print(f"{i}\t\t{feature_matrix[i,0]:.6f}\t{feature_matrix[i,1]:.6f}\t{feature_matrix[i,2]:.6f}")

# Print basic statistics
print("\nFeature Statistics:")
print("RMS Energy     - Mean: {:.6f}, Min: {:.6f}, Max: {:.6f}".format(
    np.mean(feature_matrix[:,0]), np.min(feature_matrix[:,0]), np.max(feature_matrix[:,0])))
print("Zero Crossing  - Mean: {:.6f}, Min: {:.6f}, Max: {:.6f}".format(
    np.mean(feature_matrix[:,1]), np.min(feature_matrix[:,1]), np.max(feature_matrix[:,1])))
print("Onset Strength - Mean: {:.6f}, Min: {:.6f}, Max: {:.6f}".format(
    np.mean(feature_matrix[:,2]), np.min(feature_matrix[:,2]), np.max(feature_matrix[:,2])))