/*
 * MegaJolt Production 1.5 + P-MAG Dual Monitor
 * - Heartbeats: Bright Green Pulse.
 * - Screen Fix: update_ui() moved to high-priority execution to prevent 10s lag.
 * - Display: ST7789 (240x320) Inversion: TRUE.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>
#include <algorithm>
#include <memory>

#include "esp_log.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "driver/uart.h"

#include "usb/usb_host.h"
#include "usb/cdc_acm_host.h"
#include "usb/vcp_ch34x.hpp"
#include "usb/vcp.hpp"

#define LGFX_USE_V1
#include <LovyanGFX.hpp>

using namespace esp_usb;

static uint32_t last_mj_rx_ms = 0;
static bool is_demo_mode = true;

#define PMAG_UART UART_NUM_1
#define PMAG_TX_PIN 17
#define PMAG_RX_PIN 18

struct {
    uint32_t mj_baud = 38400;
    int mj_offset = -10;
    uint32_t mj_poll_ms = 150;
} settings;

struct {
    int mj_adv = 0;
    int mj_corr = 0;
    uint32_t mj_rpm = 0;
    char mj_state[3] = "--";
    bool mj_connected = false;
    uint32_t last_mj_rx = 0;

    float pmag_adv = 0.0f;
    uint32_t pmag_rpm = 0;
    float pmag_volts = 0.0;
    uint32_t last_pmag_rx = 0;
    bool pmag_ever_connected = false;

    uint64_t total_sparks = 0;
    uint32_t last_calc_ms = 0;
    bool counting_active = false;
} data;

static SemaphoreHandle_t mj_disconnected_sem;

class LGFX_S3_MJ : public lgfx::LGFX_Device {
    lgfx::Panel_ST7789  _panel_instance;
    lgfx::Bus_SPI       _bus_instance;
    lgfx::Light_PWM      _light_instance;
public:
    LGFX_S3_MJ() {
        {   auto cfg = _bus_instance.config();
            cfg.spi_host = SPI2_HOST; cfg.freq_write = 40000000;
            cfg.pin_sclk = 12; cfg.pin_mosi = 11; cfg.pin_dc = 2;
            _bus_instance.config(cfg);
            _panel_instance.setBus(&_bus_instance);
        }
        {   auto cfg = _panel_instance.config();
            cfg.pin_cs = 10; cfg.pin_rst = 1;
            cfg.panel_width  = 240;
            cfg.panel_height = 320;
            cfg.invert       = true;
            _panel_instance.config(cfg);
        }
        {   auto cfg = _light_instance.config();
            cfg.pin_bl = 3; _light_instance.config(cfg);
            _panel_instance.setLight(&_light_instance);
        }
        setPanel(&_panel_instance);
    }
};

static LGFX_S3_MJ tft;
static LGFX_Sprite canvas(&tft);

// UPDATED: Bright Green Pulse
uint16_t get_pulse_color() {
    float pulse = (sin(esp_log_timestamp() * 0.012f) + 1.0f) / 2.0f;
    uint8_t g = 110 + (int)(pulse * 145);
    return canvas.color565(0, g, 0);
}

void update_ui() {
    char buf[64];
    uint32_t now = esp_log_timestamp();

    if (!data.counting_active && data.mj_connected && data.pmag_ever_connected) {
        data.counting_active = true;
        data.last_calc_ms = now;
    }
    if (data.counting_active && data.mj_rpm > 0) {
        uint32_t delta = now - data.last_calc_ms;
        double sparks = ((double)data.mj_rpm * 8.0 * (double)delta) / 60000.0;
        data.total_sparks += (uint64_t)sparks;
    }
    data.last_calc_ms = now;

    canvas.fillSprite(TFT_BLACK);
    canvas.fillRect(95, 0, 3, 240, TFT_WHITE);
    uint16_t header_bg = 0x3186;
    canvas.fillRect(0, 0, 95, 30, header_bg);
    canvas.fillRect(98, 0, 222, 30, header_bg);

    // --- P-MAG (Left) ---
    canvas.setFont(&fonts::FreeSansBold9pt7b);
    canvas.setTextColor(TFT_YELLOW);
    canvas.drawCenterString("P-MAG", 48, 8);
    // Green Pulse for P-MAG
    if (now - data.last_pmag_rx < 2000) canvas.fillCircle(85, 15, 4, get_pulse_color());

    canvas.setFont(&fonts::FreeSansBold18pt7b);
    uint16_t pmag_color = (data.pmag_adv < 1.0f) ? TFT_SILVER : (data.pmag_adv > 35.0f ? TFT_RED : TFT_WHITE);
    canvas.setTextColor(pmag_color);
    snprintf(buf, sizeof(buf), "%.0f", roundf(data.pmag_adv));
    canvas.drawCenterString(buf, 48, 55);

    canvas.setFont(&fonts::FreeSansBold9pt7b);
    canvas.setTextColor(TFT_SILVER);
    canvas.drawCenterString("ADVANCE", 48, 85);

    canvas.setTextColor(data.pmag_rpm > 2700 ? TFT_RED : TFT_YELLOW);
    canvas.setFont(&fonts::FreeSansBold12pt7b);
    snprintf(buf, sizeof(buf), "%lu", (unsigned long)data.pmag_rpm);
    canvas.drawCenterString(buf, 48, 128);
    canvas.setFont(&fonts::FreeSansBold9pt7b);
    canvas.drawCenterString("RPM", 48, 155);

    canvas.setTextColor(TFT_GREEN);
    snprintf(buf, sizeof(buf), "%.1f", data.pmag_volts);
    canvas.drawCenterString(buf, 48, 195);
    canvas.drawCenterString("VOLTS", 48, 220);

    // --- MEGAJOLT (Right) ---
    int MJ_CX = 210, MJ_CY = 158;
    canvas.setFont(&fonts::FreeSansBold9pt7b);
    canvas.setTextColor(TFT_YELLOW);

    if (is_demo_mode) {
        canvas.drawCenterString("MJ DEMO MODE", MJ_CX, 8);
    } else {
        canvas.drawCenterString(data.mj_connected ? "MEGAJOLT ACTIVE" : "SEARCHING FOR MJ", MJ_CX, 8);
    }

    // Green Pulse for MegaJolt
    if (data.mj_connected && (now - data.last_mj_rx < 2000)) canvas.fillCircle(308, 15, 4, get_pulse_color());

    canvas.setFont(&fonts::FreeSansBold9pt7b);
    canvas.setTextColor(TFT_SILVER);
    canvas.drawCenterString("STATE", 145, 38);
    canvas.drawCenterString("Adv Corr", 265, 38);
    canvas.setTextColor(TFT_WHITE);
    canvas.setFont(&fonts::FreeSansBold12pt7b);
    canvas.drawCenterString(data.mj_state, 145, 55);
    snprintf(buf, sizeof(buf), "%+d", data.mj_corr);
    canvas.drawCenterString(buf, 265, 55);

    // Gauge
    for (int i = 0; i <= 25; i++) {
        float ang = 180 + (i * 7.2f);
        canvas.drawArc(MJ_CX, MJ_CY, 65, 60, ang, ang + 6.8, canvas.color565(255*(i/25.0), 255*(1-(i/25.0)), 0));
        if ((20 + i) % 5 == 0) {
            float rad = ang * 0.01745329;
            canvas.setFont(&fonts::Font0);
            canvas.setTextColor(TFT_SILVER);
            canvas.drawCenterString(std::to_string(20 + i).c_str(), MJ_CX + cos(rad) * 78, MJ_CY + sin(rad) * 78 - 4);
        }
    }

    float needle_val = std::max(20.0f, (float)data.mj_adv);
    needle_val = std::min(45.0f, needle_val);
    float target_ang = (float)(needle_val - 20) * 7.2f + 180;
    float rad = target_ang * 0.01745329;
    canvas.fillTriangle(MJ_CX + cos(rad+0.15)*10, MJ_CY + sin(rad+0.15)*10,
                        MJ_CX + cos(rad-0.15)*10, MJ_CY + sin(rad-0.15)*10,
                        MJ_CX + cos(rad)*62, MJ_CY + sin(rad)*62, TFT_RED);

    canvas.setTextColor(data.mj_adv == 0 ? TFT_SILVER : TFT_WHITE);
    canvas.setFont(&fonts::FreeSansBold24pt7b);
    canvas.drawCenterString(std::to_string(data.mj_adv).c_str(), MJ_CX, MJ_CY - 35);

    canvas.fillRoundRect(MJ_CX - 30, MJ_CY + 5, 60, 20, 3, data.mj_rpm > 2700 ? TFT_RED : TFT_YELLOW);
    canvas.setTextColor(TFT_BLACK);
    canvas.setFont(&fonts::FreeSansBold9pt7b);
    canvas.drawCenterString(std::to_string(data.mj_rpm).c_str(), MJ_CX, MJ_CY + 7);

    canvas.fillRect(98, 205, 222, 35, 0x18E3);
    canvas.setFont(&fonts::Font0);
    canvas.setTextColor(TFT_SILVER);
    if (data.counting_active) {
        canvas.drawString("TOTAL IGNITION EVENTS (8x REV)", 110, 208);
        canvas.setFont(&fonts::FreeSansBold9pt7b);
        canvas.setTextColor(TFT_WHITE);
        snprintf(buf, sizeof(buf), "%llu", data.total_sparks);
        canvas.drawString(buf, 110, 220);
    } else {
        canvas.drawString("AWAITING DUAL CONNECTION...", 110, 215);
    }

    canvas.pushSprite(0, 0);
}

void pmag_task(void *p) {
    uart_config_t cfg = { .baud_rate = 9600, .data_bits = UART_DATA_8_BITS, .parity = UART_PARITY_DISABLE, .stop_bits = UART_STOP_BITS_1, .flow_ctrl = UART_HW_FLOWCTRL_DISABLE, .source_clk = UART_SCLK_DEFAULT };
    uart_param_config(PMAG_UART, &cfg);
    uart_set_pin(PMAG_UART, PMAG_TX_PIN, PMAG_RX_PIN, -1, -1);
    uart_driver_install(PMAG_UART, 1024, 0, 0, NULL, 0);

    uint8_t rx[256];
    uint32_t last_pmag_poll = 0;

    while (1) {
        uint32_t now = esp_log_timestamp();
        if (now - data.last_pmag_rx > 3000 && now - last_pmag_poll > 1000) {
            uint8_t init_cmds[] = {47, 42, 13};
            uart_write_bytes(PMAG_UART, init_cmds, 3);
            vTaskDelay(pdMS_TO_TICKS(50));
            uart_write_bytes(PMAG_UART, "/I1\r", 4);
            last_pmag_poll = now;
        }

        int len = uart_read_bytes(PMAG_UART, rx, 255, pdMS_TO_TICKS(10));
        if (len > 12) {
            rx[len] = '\0';
            printf("[P-MAG RAW]: %s\n", (char*)rx);
            char *ptr = strchr((char*)rx, ' ');
            int off = (ptr == NULL) ? 0 : (ptr - (char*)rx);
            if (len - off >= 13) {
                data.pmag_ever_connected = true;
                char r_h[5]={0}, a_h[3]={0}, v_h[3]={0};
                memcpy(r_h, &rx[off+1], 4); data.pmag_rpm = strtol(r_h, NULL, 16);
                memcpy(a_h, &rx[off+5], 2); data.pmag_adv = strtol(a_h, NULL, 16) * 1.4f;
                v_h[0] = rx[off+11]; v_h[1] = rx[off+12];
                data.pmag_volts = ((float)(strtol(v_h, NULL, 16) - 10) / 10.0f) + 1.5f;
                data.last_pmag_rx = esp_log_timestamp();
                printf("[P-MAG PARSED] RPM: %lu, ADV: %.1f, V: %.1f\n", (unsigned long)data.pmag_rpm, data.pmag_adv, data.pmag_volts);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

static bool handle_mj_rx(const uint8_t *d, size_t len, void *arg) {
    if (len >= 9) {
        data.last_mj_rx = esp_log_timestamp();
        last_mj_rx_ms = esp_log_timestamp();
        data.mj_adv = (int8_t)d[0] + settings.mj_offset;
        uint16_t t = (d[1] << 8) | d[2];
        if (t == 0 || t > 60000) {
            data.mj_rpm = 0;
        } else {
            uint32_t calc_rpm = 60000000ULL / (t * 2);
            data.mj_rpm = (calc_rpm < 100) ? 0 : calc_rpm;
        }
        strcpy(data.mj_state, ((d[5] >> 7) & 1) ? "TO" : "CR");
        data.mj_corr = (int8_t)d[8];
    }
    return true;
}

static void handle_mj_evt(const cdc_acm_host_dev_event_data_t *event, void *ctx) {
    if (event->type == CDC_ACM_HOST_DEVICE_DISCONNECTED) {
        data.mj_connected = false;
        xSemaphoreGive(mj_disconnected_sem);
    }
}

extern "C" void app_main(void) {
    vTaskDelay(pdMS_TO_TICKS(1000));
    tft.init(); tft.setRotation(1);
    canvas.createSprite(320, 240);
    mj_disconnected_sem = xSemaphoreCreateBinary();

    is_demo_mode = true;
    int sweep_points[] = {20, 25, 30, 35, 40, 45, 40, 35, 30, 25, 20};
    for(int deg : sweep_points){
        float progress = (deg - 20) / 25.0f;
        data.mj_adv = deg; data.mj_rpm = (uint32_t)(progress * 2700);
        data.pmag_adv = (float)deg; data.pmag_rpm = (uint32_t)(progress * 2700);
        data.pmag_volts = 12.0f + (progress * 2.5f);
        strcpy(data.mj_state, (deg % 10 == 0) ? "CR" : "TO");
        update_ui(); vTaskDelay(pdMS_TO_TICKS(200));
    }

    is_demo_mode = false;
    data.mj_rpm = 0; data.pmag_rpm = 0;
    data.mj_adv = 0; data.pmag_adv = 0;
    data.pmag_volts = 0;
    update_ui();

    xTaskCreate(pmag_task, "pmag", 4096, NULL, 10, NULL);
    usb_host_config_t host_cfg = { .intr_flags = ESP_INTR_FLAG_LEVEL1 };
    usb_host_install(&host_cfg);
    xTaskCreate([](void* p){while(1){usb_host_lib_handle_events(portMAX_DELAY, NULL);}}, "usb", 4096, NULL, 20, NULL);
    cdc_acm_host_install(NULL);
    VCP::register_driver<CH34x>();

    while (true) {
        // Reduced timeout so we don't hang the loop while searching
        cdc_acm_host_device_config_t dev_cfg = { .connection_timeout_ms = 100, .out_buffer_size = 512, .in_buffer_size = 512, .event_cb = handle_mj_evt, .data_cb = handle_mj_rx };
        CdcAcmDevice* raw = VCP::open(&dev_cfg);

        if (raw) {
            auto vcp = std::unique_ptr<CdcAcmDevice>(raw);
            data.mj_connected = true;
            cdc_acm_line_coding_t lc = { settings.mj_baud, 0, 0, 8 };
            vcp->line_coding_set(&lc);
            vcp->set_control_line_state(true, true);
            last_mj_rx_ms = esp_log_timestamp();

            while (xSemaphoreTake(mj_disconnected_sem, 0) != pdTRUE) {
                uint8_t cmd = 'S';
                vcp->tx_blocking(&cmd, 1);
                update_ui(); // Regular updates when connected
                if (esp_log_timestamp() - last_mj_rx_ms > 5000) esp_restart();
                vTaskDelay(pdMS_TO_TICKS(settings.mj_poll_ms));
            }
        } else {
            // CRITICAL: Call update_ui even when MegaJolt isn't found
            // This prevents the "10 second lag" while the USB host searches.
            update_ui();
            vTaskDelay(pdMS_TO_TICKS(100)); // Short cycle
        }
    }
}