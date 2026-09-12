/**
 * @file csi_protocol.h
 * @brief Wire protocol for CSI frames sent from ESP32-S3 to PC over UART.
 *
 * CRITICAL: This layout is mirrored EXACTLY in the Python side at
 * app/receiver/protocol.py. If you change one, you MUST change the other,
 * or the parser will desync / silently misinterpret bytes as valid CSI.
 *
 * Frame layout (all multi-byte fields little-endian):
 *
 *   [0]   SOF0        0xAA
 *   [1]   SOF1        0x55
 *   [2:4] LEN (u16)   length of PAYLOAD in bytes (NOT including SOF/LEN/CRC/EOF)
 *   [4:4+LEN] PAYLOAD
 *   [4+LEN : 6+LEN]   CRC16 (u16) over PAYLOAD only, CRC-16/CCITT-FALSE
 *                     (poly 0x1021, init 0xFFFF, no reflect, no xorout)
 *   [6+LEN]   EOF0    0x55
 *   [7+LEN]   EOF1    0xAA
 *
 * PAYLOAD layout:
 *   timestamp_us : u64   esp_timer_get_time(), microseconds since boot
 *   rssi         : i8    signal strength in dBm (negative)
 *   channel      : u8    WiFi channel number
 *   mac          : u8[6] source MAC address of the frame CSI was extracted from
 *   rate         : u8    PHY rate index (raw wifi_pkt_rx_ctrl_t.rate)
 *   csi_len      : u16   number of int8 values in csi_data (NOT subcarrier count;
 *                        each subcarrier contributes 2 values: imaginary, real)
 *   csi_data     : i8[csi_len]
 *
 * Rationale for this framing (not a raw struct dump over UART):
 *   - Fixed 2-byte sync word lets the receiver resynchronize after any
 *     dropped/corrupted byte, reboot, or boot-log text on the same line.
 *   - Explicit LEN means the receiver never has to guess csi_len before
 *     it can find the frame boundary.
 *   - CRC16 over the payload catches UART bit errors / partial writes,
 *     which a naive "read struct, trust it" approach will silently accept
 *     as valid CSI and corrupt downstream feature extraction.
 */

#ifndef CSI_PROTOCOL_H
#define CSI_PROTOCOL_H

#include <stdint.h>
#include <stddef.h>

#define CSI_PROTO_SOF0 0xAA
#define CSI_PROTO_SOF1 0x55
#define CSI_PROTO_EOF0 0x55
#define CSI_PROTO_EOF1 0xAA

/* Max raw CSI buffer IDF can hand us for HT40 LLTF+HT-LTF is well under this;
 * generous ceiling to avoid truncation, checked at runtime before packing. */
#define CSI_PROTO_MAX_CSI_LEN 512

#pragma pack(push, 1)
typedef struct {
    uint64_t timestamp_us;
    int8_t   rssi;
    uint8_t  channel;
    uint8_t  mac[6];
    uint8_t  rate;
    uint16_t csi_len;
    /* csi_data follows immediately after this struct in the TX buffer;
     * not embedded here because csi_len is variable. */
} csi_payload_header_t;
#pragma pack(pop)

/**
 * @brief Compute CRC-16/CCITT-FALSE over a buffer.
 *
 * Poly 0x1021, init 0xFFFF, no input/output reflection, no final XOR.
 * MUST match app/receiver/protocol.py:crc16_ccitt_false() exactly.
 */
uint16_t csi_protocol_crc16(const uint8_t *data, size_t len);

/**
 * @brief Build a complete framed packet (SOF+LEN+PAYLOAD+CRC+EOF) into out_buf.
 *
 * @param out_buf     destination buffer
 * @param out_buf_len capacity of out_buf
 * @param header      fixed-size payload header (csi_len must already be set)
 * @param csi_data    raw CSI int8 buffer, csi_len bytes
 * @return total number of bytes written to out_buf, or 0 on failure
 *         (buffer too small / csi_len exceeds CSI_PROTO_MAX_CSI_LEN)
 */
size_t csi_protocol_build_frame(uint8_t *out_buf, size_t out_buf_len,
                                 const csi_payload_header_t *header,
                                 const int8_t *csi_data);

#endif /* CSI_PROTOCOL_H */
