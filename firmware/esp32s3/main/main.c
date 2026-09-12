/**
 * @file main.c
 * @brief Entry point for the ESP32-S3 CSI collection firmware.
 *
 * Boot sequence:
 *   1. Start UART sender (so it's ready to accept frames the moment CSI
 *      capture begins -- avoids a startup race where CSI frames arrive
 *      before the consumer task exists).
 *   2. Connect to the configured AP as a WiFi station (blocks until
 *      connected or out of retries).
 *   3. Enable CSI capture and register the callback.
 *   4. Idle: all real work happens in the CSI callback (WiFi driver task
 *      context) and the uart_sender task.
 */

#include "wifi_manager.h"
#include "csi_collector.h"
#include "uart_sender.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "main";

#define CSI_FRAME_QUEUE_LEN 64

void app_main(void)
{
    ESP_LOGI(TAG, "WiFi Human Presence Detection -- CSI collector starting");

esp_err_t wifi_result = wifi_manager_init_sta();
if (wifi_result != ESP_OK) {
    ESP_LOGE(TAG, "WiFi connection failed, rebooting in 5s");
    vTaskDelay(pdMS_TO_TICKS(5000));
    esp_restart();
}

ESP_ERROR_CHECK(csi_collector_init(CSI_FRAME_QUEUE_LEN));

ESP_ERROR_CHECK(uart_sender_start());

ESP_LOGI(TAG, "Setup complete. Streaming CSI over UART1.");

    /* Nothing else to do on this task; CSI callback + uart_sender task do
     * all the work. Idle loop just gives periodic connection-status logs. */
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(10000));
        ESP_LOGI(TAG, "Status: connected=%d channel=%d",
                 wifi_manager_is_connected(), wifi_manager_get_channel());
    }
}
