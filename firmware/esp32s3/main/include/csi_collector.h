/**
 * @file csi_collector.h
 * @brief Configures ESP-IDF's CSI capture and forwards each captured frame
 *        to a FreeRTOS queue for the UART sender task to consume.
 *
 * IMPORTANT (chip/IDF-version dependent behavior):
 *   - CSI is only reported for frames the radio actually receives while
 *     associated (or in promiscuous mode). We rely on beacon frames from
 *     the connected AP (see wifi_manager.c), giving ~10 Hz.
 *   - wifi_csi_info_t.len is the number of BYTES in the buf, where each
 *     subcarrier contributes 2 bytes (imaginary, real) as signed int8.
 *     Do not confuse this with subcarrier count.
 *   - This was written against ESP-IDF v5.1+ CSI API
 *     (esp_wifi_set_csi_config / esp_wifi_set_csi_rx_cb). Field names in
 *     wifi_csi_info_t and wifi_csi_config_t have changed across IDF
 *     versions in the past (e.g. secondary_channel handling) -- verify
 *     against your installed IDF's esp_wifi_types.h if you're on a
 *     different version.
 */

#ifndef CSI_COLLECTOR_H
#define CSI_COLLECTOR_H

#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

/**
 * @brief Queue handle that receives fully-built protocol frames (raw bytes,
 *        ready to write to UART) from the CSI callback. Created internally
 *        by csi_collector_init(). Each queue item is a heap-allocated
 *        csi_frame_item_t*; the consumer (uart_sender) owns and frees it
 *        after transmission.
 */
typedef struct {
    uint8_t *data;
    size_t   len;
} csi_frame_item_t;

extern QueueHandle_t g_csi_frame_queue;

/**
 * @brief Enable CSI reporting on the WiFi driver and register the internal
 *        callback that packs each capture into the wire protocol and
 *        pushes it onto g_csi_frame_queue.
 *
 * Must be called AFTER wifi_manager_init_sta() has successfully connected,
 * since esp_wifi_set_csi_config requires the driver to be started.
 *
 * @param queue_len depth of g_csi_frame_queue (items, not bytes). If the
 *        UART sender falls behind, oldest-first drop occurs at the queue
 *        (xQueueSend uses 0 timeout) rather than blocking the WiFi task,
 *        which would stall the whole radio.
 */
esp_err_t csi_collector_init(size_t queue_len);

#endif /* CSI_COLLECTOR_H */
