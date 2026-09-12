/**
 * @file wifi_manager.h
 * @brief Connects the ESP32-S3 to a router/AP as a WiFi station.
 *
 * CSI extraction requires the radio to be receiving frames. Connecting as a
 * station to an existing AP gives a steady stream of beacon frames (~10 Hz,
 * standard 100ms beacon interval) which esp_wifi's CSI callback fires on.
 * No additional traffic generator is required for this phase.
 */

#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include "esp_err.h"
#include <stdbool.h>

/**
 * @brief Initialize WiFi in station mode and connect to the AP configured
 *        via `idf.py menuconfig` (Component config -> CSI Presence Detection
 *        -> WiFi SSID / WiFi Password).
 *
 * Blocks until connected or until CONFIG_WIFI_MAXIMUM_RETRY consecutive
 * connection attempts fail, in which case it returns ESP_FAIL and the
 * caller should decide whether to reboot or retry.
 *
 * @return ESP_OK on successful connection, ESP_FAIL otherwise.
 */
esp_err_t wifi_manager_init_sta(void);

/**
 * @return true if currently associated to the AP, false otherwise.
 */
bool wifi_manager_is_connected(void);

/**
 * @return the WiFi channel currently in use (0 if not connected).
 */
uint8_t wifi_manager_get_channel(void);

#endif /* WIFI_MANAGER_H */
