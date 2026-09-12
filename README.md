# WiFi Human Presence Detection using ESP32-S3 CSI

> **A WiFi Channel State Information (CSI) based indoor human presence and occupancy sensing system using ESP32-S3, signal processing, and machine learning.**

---

## 📌 Project Overview

This project develops a **device-free indoor human presence detection and occupancy estimation system** using WiFi Channel State Information (CSI).

Instead of using conventional sensors such as PIR, ultrasonic sensors, or cameras, the system analyzes how the presence and movement of people affect the WiFi channel between a transmitter and an ESP32-S3 CSI receiver.

The project is being developed as a scalable platform that can progress from:

**Empty Room → One Person → Multiple People → Spatial Localization → Occupancy Heatmap**

The initial implementation focuses on building a reliable dataset using the **actual ESP32-S3 CSI hardware** and developing a machine-learning model for:

- Empty-room detection
- One-person presence detection
- Future multi-person occupancy estimation
- Future spatial localization
- Future room-level occupancy heatmaps

---

# 🎯 Objectives

The major objectives of this project are:

1. Capture real-time WiFi CSI using ESP32-S3.
2. Store raw CSI data for machine-learning experiments.
3. Develop a reliable CSI preprocessing pipeline.
4. Extract meaningful temporal and frequency-domain features.
5. Detect human presence without requiring the person to carry a device.
6. Estimate the number of people in the environment.
7. Develop a real-time monitoring dashboard.
8. Extend the system toward multi-node spatial sensing.
9. Generate room-level human presence/localization heatmaps.

---

# 🧠 Core Concept

WiFi signals propagate through an indoor environment and interact with objects and people.

When a person enters or moves inside the environment, the wireless propagation path changes.

This produces measurable changes in:

- CSI amplitude
- CSI phase
- Subcarrier response
- Temporal variation
- Signal energy
- Channel characteristics

The ESP32-S3 captures these CSI variations.

The processing pipeline then converts the raw CSI into information that can be used by a machine-learning model to determine whether a person is present.

### Basic Concept

```text
        WiFi Transmitter
        Mobile Hotspot
              │
              │ WiFi
              ▼
      ┌──────────────────┐
      │    ESP32-S3      │
      │   CSI Receiver   │
      └──────────────────┘
              │
              │ USB Serial
              ▼
      ┌──────────────────┐
      │      Laptop      │
      │ Python Processing│
      └──────────────────┘
              │
              ▼
      ┌──────────────────┐
      │ CSI Preprocessing│
      └──────────────────┘
              │
              ▼
      ┌──────────────────┐
      │ Feature Extraction│
      └──────────────────┘
              │
              ▼
      ┌──────────────────┐
      │ Machine Learning │
      │      Model       │
      └──────────────────┘
              │
              ▼
      Human Presence /
      Occupancy Detection
