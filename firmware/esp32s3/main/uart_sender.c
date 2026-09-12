#include "uart_sender.h"
#include "csi_collector.h"
#include "driver/usb_serial_jtag.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdlib.h>

static const char *TAG = "usb_sender";

static void uart_sender_task(void *arg)
{
    csi_frame_item_t *item = NULL;

    for (;;) {
        if (xQueueReceive(g_csi_frame_queue, &item, portMAX_DELAY) == pdTRUE) {

            int written = usb_serial_jtag_write_bytes(
                item->data,
                item->len,
                pdMS_TO_TICKS(100)
            );

            if (written < 0 || (size_t)written != item->len) {
                ESP_LOGW(TAG, "USB write failed: %d/%u bytes",
                         written, (unsigned)item->len);
            }

            free(item->data);
            free(item);
            item = NULL;
        }
    }
}

esp_err_t uart_sender_send(const uint8_t *data, size_t length)
{
    if (data == NULL || length == 0) {
        return ESP_ERR_INVALID_ARG;
    }

    int written = usb_serial_jtag_write_bytes(
        data,
        length,
        pdMS_TO_TICKS(100)
    );

    if (written < 0 || (size_t)written != length) {
        ESP_LOGE(TAG, "USB write failed (%d/%u)",
                 written, (unsigned)length);
        return ESP_FAIL;
    }

    return ESP_OK;
}

esp_err_t uart_sender_start(void)
{
    usb_serial_jtag_driver_config_t cfg =
        USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();

    cfg.tx_buffer_size = 4096;
    cfg.rx_buffer_size = 256;

    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&cfg));

    BaseType_t ok = xTaskCreate(
        uart_sender_task,
        "usb_sender",
        4096,
        NULL,
        10,
        NULL
    );

    if (ok != pdPASS) {
        ESP_LOGE(TAG, "Failed to create USB sender task");
        return ESP_ERR_NO_MEM;
    }

    ESP_LOGI(TAG, "USB Serial/JTAG sender started");
    return ESP_OK;
}