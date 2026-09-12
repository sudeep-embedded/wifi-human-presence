from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix


TRAIN = Path("dataset/HomeHAR_windows/train/homehar_windows.npz")
TEST = Path("dataset/HomeHAR_windows/test/homehar_windows.npz")

X_train = np.load(TRAIN)["X"]
y_train = np.load(TRAIN)["y"]

X_test = np.load(TEST)["X"]
y_test = np.load(TEST)["y"]

print("Train:", X_train.shape)
print("Test :", X_test.shape)

model = RandomForestClassifier(
    n_estimators=200,
    random_state=42,
    n_jobs=-1,
)

print("\nTraining Random Forest...")
model.fit(X_train, y_train)

pred = model.predict(X_test)

accuracy = accuracy_score(y_test, pred)

print(f"\nAccuracy: {accuracy * 100:.2f}%")

print("\nClassification Report:")
print(
    classification_report(
        y_test,
        pred,
        target_names=[
            "drink",
            "eat",
            "empty",
            "sleep",
            "smoke",
            "watch",
            "work",
        ],
    )
)

print("\nConfusion Matrix:")
print(confusion_matrix(y_test, pred))