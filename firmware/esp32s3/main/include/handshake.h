/**
 * @file handshake.h
 * @brief Receiver handshake service.
 *
 * Sends receiver identity information to the PC immediately after boot.
 *
 * This allows the PC to uniquely identify each ESP32-S3 receiver
 * regardless of which USB COM port Windows assigns.
 */

#ifndef HANDSHAKE_H
#define HANDSHAKE_H

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialize the handshake service.
 *
 * Reserved for future use.
 *
 * @return ESP_OK on success.
 */
esp_err_t handshake_init(void);

/**
 * @brief Send one receiver handshake packet.
 *
 * The packet contains:
 *  - Receiver MAC
 *  - Chip model
 *  - Chip revision
 *  - Firmware version
 *  - Protocol version
 *
 * @return ESP_OK on success.
 */
esp_err_t handshake_send(void);

#ifdef __cplusplus
}
#endif

#endif /* HANDSHAKE_H */