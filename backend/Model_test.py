import numpy as np
from joblib import load

# Constants
MODEL_PATH = 'ML_MODEL/models/audio_popping_classifier_model_normalised.joblib'

# Load the pre-trained model
model = load(MODEL_PATH)

# Load the input data from the .npy file
input_data = np.load('temp/ml_features/features_src0_2_20250406_002223_381358.npy')

# Make a prediction using the model
prediction = model.predict(input_data)

# Print the result
print("Model Prediction:", prediction)
