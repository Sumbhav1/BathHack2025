import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from joblib import dump
from sklearn.metrics import classification_report

# Constants
MODEL_PATH = 'ML_MODEL/models/audio_popping_classifier_model_normalised.joblib'

# Load the processed data
X = np.load('ML_MODEL/ProcessedData/training_data_features.npy')
y = np.load('ML_MODEL/ProcessedData/training_data_labels.npy')

# Split the data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Create and train the model
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Evaluate the model
y_pred = model.predict(X_test)
print("\nModel Performance:")
print(classification_report(y_test, y_pred))

# Save the model
dump(model, MODEL_PATH)
print(f"\nModel saved as '{MODEL_PATH}'")