#include "csi_protocol.h"
#include <string.h>

uint16_t csi_protocol_crc16(const uint8_t *data, size_t len)
{
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; i++) {
        crc ^= ((uint16_t)data[i]) << 8;
        for (int bit = 0; bit < 8; bit++) {
            if (crc & 0x8000) {
                crc = (crc << 1) ^ 0x1021;
            } else {
                crc <<= 1;
            }
        }
    }
    return crc;
}

size_t csi_protocol_build_frame(uint8_t *out_buf, size_t out_buf_len,
                                 const csi_payload_header_t *header,
                                 const int8_t *csi_data)
{
    if (header->csi_len > CSI_PROTO_MAX_CSI_LEN) {
        return 0;
    }

    const size_t payload_len = sizeof(csi_payload_header_t) + header->csi_len;
    const size_t total_len = 2 /*SOF*/ + 2 /*LEN*/ + payload_len + 2 /*CRC*/ + 2 /*EOF*/;

    if (out_buf_len < total_len) {
        return 0;
    }

    uint8_t *p = out_buf;

    *p++ = CSI_PROTO_SOF0;
    *p++ = CSI_PROTO_SOF1;

    /* LEN, little-endian */
    uint16_t len16 = (uint16_t)payload_len;
    *p++ = (uint8_t)(len16 & 0xFF);
    *p++ = (uint8_t)((len16 >> 8) & 0xFF);

    /* PAYLOAD: header struct then raw csi bytes */
    uint8_t *payload_start = p;
    memcpy(p, header, sizeof(csi_payload_header_t));
    p += sizeof(csi_payload_header_t);
    memcpy(p, csi_data, header->csi_len);
    p += header->csi_len;

    /* CRC over payload only */
    uint16_t crc = csi_protocol_crc16(payload_start, payload_len);
    *p++ = (uint8_t)(crc & 0xFF);
    *p++ = (uint8_t)((crc >> 8) & 0xFF);

    *p++ = CSI_PROTO_EOF0;
    *p++ = CSI_PROTO_EOF1;

    return (size_t)(p - out_buf);
}
