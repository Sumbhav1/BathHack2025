import numpy as np
from joblib import load

# Load the pre-trained model
model = load('ML_MODEL/audio_popping_classifier_model.joblib')

# Load the input data from the .npy file
input_data = np.load('temp/ml_features/features_src0_2_20250406_002223_381358.npy')

# Make a prediction using the model
prediction = model.predict(input_data)

# Print the result
print("Model Prediction:", prediction)
