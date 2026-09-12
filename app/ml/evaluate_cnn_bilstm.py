import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)

from torch.utils.data import DataLoader, TensorDataset


TEST = "dataset/HomeHAR_raw/test/raw_csi.npz"
MODEL = "app/ml/cnn_bilstm_best.pth"


class CNNBiLSTM(nn.Module):

    def __init__(self):
        super().__init__()

        self.cnn = nn.Sequential(
            nn.Conv1d(104, 64, kernel_size=5, padding=2),
            nn.BatchNorm1d(64),
            nn.ReLU(),

            nn.Conv1d(64, 128, kernel_size=5, padding=2),
            nn.BatchNorm1d(128),
            nn.ReLU(),

            nn.MaxPool1d(2),
        )

        self.lstm = nn.LSTM(
            input_size=128,
            hidden_size=128,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
            dropout=0.2,
        )

        self.classifier = nn.Sequential(
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 7),
        )

    def forward(self, x):

        x = x.transpose(1, 2)

        x = self.cnn(x)

        x = x.transpose(1, 2)

        x, _ = self.lstm(x)

        x = x[:, -1, :]

        return self.classifier(x)


# ------------------------------------------------------------
# Load test data
# ------------------------------------------------------------

data = np.load(TEST)

X = data["X"].astype(np.float32)
y = data["y"].astype(np.int64)

print("Test:", X.shape)
print("Labels:", np.unique(y, return_counts=True))


# ------------------------------------------------------------
# Load model checkpoint
# ------------------------------------------------------------

checkpoint = torch.load(
    MODEL,
    map_location="cpu",
    weights_only=False,
)

mean = checkpoint["mean"]
std = checkpoint["std"]

X = (X - mean) / (std + 1e-6)

X = torch.tensor(X)
y_tensor = torch.tensor(y)

loader = DataLoader(
    TensorDataset(X, y_tensor),
    batch_size=128,
    shuffle=False,
)


# ------------------------------------------------------------
# Model
# ------------------------------------------------------------

device = torch.device("cpu")

model = CNNBiLSTM()

model.load_state_dict(
    checkpoint["model"]
)

model.to(device)
model.eval()


# ------------------------------------------------------------
# Prediction
# ------------------------------------------------------------

predictions = []

with torch.no_grad():

    for X_batch, _ in loader:

        output = model(
            X_batch.to(device)
        )

        pred = output.argmax(
            dim=1
        )

        predictions.extend(
            pred.cpu().numpy()
        )


predictions = np.asarray(
    predictions
)


# ------------------------------------------------------------
# Results
# ------------------------------------------------------------

accuracy = accuracy_score(
    y,
    predictions,
)

print()
print(
    f"Accuracy: {accuracy * 100:.2f}%"
)


class_names = [
    "drink",
    "eat",
    "empty",
    "sleep",
    "smoke",
    "watch",
    "work",
]


print()
print("Classification Report:")
print(
    classification_report(
        y,
        predictions,
        target_names=class_names,
        digits=4,
        zero_division=0,
    )
)


print("Confusion Matrix:")

cm = confusion_matrix(
    y,
    predictions,
)

print(cm)