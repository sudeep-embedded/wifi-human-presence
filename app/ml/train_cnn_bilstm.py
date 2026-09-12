import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader


TRAIN = "dataset/HomeHAR_raw/train/raw_csi.npz"
TEST = "dataset/HomeHAR_raw/test/raw_csi.npz"

train = np.load(TRAIN)
test = np.load(TEST)

X_train = train["X"].astype(np.float32)
y_train = train["y"].astype(np.int64)

X_test = test["X"].astype(np.float32)
y_test = test["y"].astype(np.int64)

print("Train:", X_train.shape)
print("Test :", X_test.shape)

# Normalize using training data only
mean = X_train.mean(axis=(0, 1), keepdims=True)
std = X_train.std(axis=(0, 1), keepdims=True) + 1e-6

X_train = (X_train - mean) / std
X_test = (X_test - mean) / std

X_train = torch.tensor(X_train)
y_train = torch.tensor(y_train)

X_test = torch.tensor(X_test)
y_test = torch.tensor(y_test)

train_loader = DataLoader(
    TensorDataset(X_train, y_train),
    batch_size=128,
    shuffle=True,
)

test_loader = DataLoader(
    TensorDataset(X_test, y_test),
    batch_size=128,
)


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

        # (batch, time, features)
        x = x.transpose(1, 2)

        # CNN
        x = self.cnn(x)

        # (batch, channels, time)
        x = x.transpose(1, 2)

        # BiLSTM
        x, _ = self.lstm(x)

        # Last temporal output
        x = x[:, -1, :]

        return self.classifier(x)


device = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

print("Device:", device)

model = CNNBiLSTM().to(device)

criterion = nn.CrossEntropyLoss()

optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=0.001,
    weight_decay=1e-4,
)

epochs = 20

best_accuracy = 0.0

for epoch in range(epochs):

    model.train()

    correct = 0
    total = 0

    for X, y in train_loader:

        X = X.to(device)
        y = y.to(device)

        optimizer.zero_grad()

        output = model(X)

        loss = criterion(output, y)

        loss.backward()

        optimizer.step()

        pred = output.argmax(dim=1)

        correct += (pred == y).sum().item()
        total += y.size(0)

    train_accuracy = correct / total

    model.eval()

    correct = 0
    total = 0

    with torch.no_grad():

        for X, y in test_loader:

            X = X.to(device)
            y = y.to(device)

            output = model(X)

            pred = output.argmax(dim=1)

            correct += (pred == y).sum().item()
            total += y.size(0)

    test_accuracy = correct / total

    print(
        f"Epoch {epoch + 1:02d}/{epochs} "
        f"Train={train_accuracy * 100:.2f}% "
        f"Test={test_accuracy * 100:.2f}%"
    )

    if test_accuracy > best_accuracy:

        best_accuracy = test_accuracy

        torch.save(
            {
                "model": model.state_dict(),
                "mean": mean,
                "std": std,
            },
            "app/ml/cnn_bilstm_best.pth",
        )

print(
    f"\nBest Test Accuracy: "
    f"{best_accuracy * 100:.2f}%"
)

print(
    "Saved: app/ml/cnn_bilstm_best.pth"
)