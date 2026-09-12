import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader

TRAIN = "dataset/HomeHAR_windows/train/homehar_windows.npz"
TEST = "dataset/HomeHAR_windows/test/homehar_windows.npz"

train = np.load(TRAIN)
test = np.load(TEST)

X_train = train["X"].astype(np.float32)
y_train = train["y"].astype(np.int64)

X_test = test["X"].astype(np.float32)
y_test = test["y"].astype(np.int64)

# Normalize using training statistics only
mean = X_train.mean(axis=0)
std = X_train.std(axis=0) + 1e-6

X_train = (X_train - mean) / std
X_test = (X_test - mean) / std

# CNN expects: batch, channels, sequence
X_train = torch.tensor(X_train).unsqueeze(1)
X_test = torch.tensor(X_test).unsqueeze(1)

y_train = torch.tensor(y_train)
y_test = torch.tensor(y_test)

train_loader = DataLoader(
    TensorDataset(X_train, y_train),
    batch_size=256,
    shuffle=True,
)

test_loader = DataLoader(
    TensorDataset(X_test, y_test),
    batch_size=256,
)


class CNN(nn.Module):

    def __init__(self):
        super().__init__()

        self.features = nn.Sequential(
            nn.Conv1d(1, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.BatchNorm1d(64),

            nn.Conv1d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.BatchNorm1d(128),

            nn.AdaptiveAvgPool1d(1),
        )

        self.classifier = nn.Linear(128, 7)

    def forward(self, x):
        x = self.features(x)
        x = x.squeeze(-1)
        return self.classifier(x)


device = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

print("Device:", device)

model = CNN().to(device)

criterion = nn.CrossEntropyLoss()

optimizer = torch.optim.Adam(
    model.parameters(),
    lr=0.001,
)

epochs = 15

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

    train_acc = correct / total

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

    test_acc = correct / total

    print(
        f"Epoch {epoch + 1:02d}/{epochs} "
        f"Train={train_acc * 100:.2f}% "
        f"Test={test_acc * 100:.2f}%"
    )

torch.save(
    {
        "model": model.state_dict(),
        "mean": mean,
        "std": std,
    },
    "app/ml/cnn_model.pth",
)

print("Model saved: app/ml/cnn_model.pth")