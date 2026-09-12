/**
 * @file uart_sender.h
 * @brief FreeRTOS task that drains g_csi_frame_queue and writes each
 *        pre-built frame to a dedicated UART port (kept separate from
 *        UART0/console so boot logs never corrupt the CSI byte stream).
 */

#ifndef UART_SENDER_H
#define UART_SENDER_H
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

/**
 * @brief Configure the UART peripheral and start the sender task.
 *
 * Uses UART_NUM_1 with TX/RX pins from Kconfig
 * (CONFIG_CSI_UART_TX_GPIO / CONFIG_CSI_UART_RX_GPIO) at
 * CONFIG_CSI_UART_BAUD_RATE. RX side is wired but unused in this phase
 * (reserved for future PC->ESP32 control messages).
 */
esp_err_t uart_sender_start(void);
/**
 * @brief Send raw bytes over the CSI UART.
 *
 * @param data Pointer to data buffer.
 * @param length Number of bytes to send.
 *
 * @return ESP_OK on success.
 */
esp_err_t uart_sender_send(const uint8_t *data, size_t length);

#endif /* UART_SENDER_H */
