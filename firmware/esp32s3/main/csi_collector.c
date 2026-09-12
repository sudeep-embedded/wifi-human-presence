#include "csi_collector.h"
#include "csi_protocol.h"
#include "wifi_manager.h"
#include "esp_wifi.h"
#include "esp_timer.h"
#include "esp_log.h"
#include <string.h>
#include <stdlib.h>

static const char *TAG = "csi_collector";

QueueHandle_t g_csi_frame_queue = NULL;

/* Scratch buffer for building each frame before queueing. Sized for worst
 * case: header + CSI_PROTO_MAX_CSI_LEN + framing overhead. Static (not
 * stack) because this callback runs in the WiFi driver's task context with
 * limited stack. */
static uint8_t s_frame_scratch[sizeof(csi_payload_header_t) + CSI_PROTO_MAX_CSI_LEN + 8];

/**
 * @brief esp_wifi CSI RX callback. Runs in WiFi driver task context --
 *        must be fast and must not block (no logging at INFO level here
 *        in steady state, no long CPU work).
 */
static void IRAM_ATTR csi_rx_callback(void *ctx, wifi_csi_info_t *info)
{
    if (info == NULL || info->buf == NULL || info->len == 0) {
        return;
    }
    ESP_EARLY_LOGI(TAG, "CSI len=%d RSSI=%d", info->len, info->rx_ctrl.rssi);
    if (info->len > CSI_PROTO_MAX_CSI_LEN) {
        /* Should not happen for standard HT20/HT40; guard against overrun. */
        return;
    }

    csi_payload_header_t header;
    header.timestamp_us = (uint64_t) esp_timer_get_time();
    header.rssi = (int8_t) info->rx_ctrl.rssi;
    header.channel = (uint8_t) info->rx_ctrl.channel;
    memcpy(header.mac, info->mac, 6);
    header.rate = (uint8_t) info->rx_ctrl.rate;
    header.csi_len = (uint16_t) info->len;

    size_t frame_len = csi_protocol_build_frame(
        s_frame_scratch, sizeof(s_frame_scratch), &header, info->buf);

    if (frame_len == 0) {
        return; /* buffer too small / csi_len invalid, drop this capture */
    }

    csi_frame_item_t *item = (csi_frame_item_t *) malloc(sizeof(csi_frame_item_t));
    if (item == NULL) {
        return; /* OOM, drop rather than crash */
    }
    item->data = (uint8_t *) malloc(frame_len);
    if (item->data == NULL) {
        free(item);
        return;
    }
    memcpy(item->data, s_frame_scratch, frame_len);
    item->len = frame_len;

    /* Non-blocking send: if the queue is full because the UART sender task
     * is behind, drop this frame rather than stall the WiFi driver task. */
    if (g_csi_frame_queue != NULL) {
        BaseType_t ok = xQueueSend(g_csi_frame_queue, &item, 0);
        if (ok != pdTRUE) {
            free(item->data);
            free(item);
        }
    } else {
        free(item->data);
        free(item);
    }
}

esp_err_t csi_collector_init(size_t queue_len)
{
    g_csi_frame_queue = xQueueCreate(queue_len, sizeof(csi_frame_item_t *));
    if (g_csi_frame_queue == NULL) {
        ESP_LOGE(TAG, "Failed to create CSI frame queue");
        return ESP_ERR_NO_MEM;
    }

    wifi_csi_config_t csi_config = {
        .lltf_en = true,
        .htltf_en = true,
        .stbc_htltf2_en = true,
        .ltf_merge_en = true,
        .channel_filter_en = false,
        .manu_scale = false,
        .shift = false,
    };

    ESP_ERROR_CHECK(esp_wifi_set_csi_config(&csi_config));
    ESP_ERROR_CHECK(esp_wifi_set_csi_rx_cb(csi_rx_callback, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_csi(true));

    ESP_LOGI(TAG, "CSI collector initialized, queue depth=%u", (unsigned) queue_len);
    return ESP_OK;
}
