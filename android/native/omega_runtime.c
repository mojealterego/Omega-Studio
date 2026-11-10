/* OMEGA Studio native ARM64 primitive library. No libc or external runtime. */
typedef __SIZE_TYPE__ size_t;
typedef unsigned char uint8_t;
typedef unsigned int uint32_t;

__attribute__((visibility("default"))) int omega_runtime_abi(void) { return 2; }

/* Bounded non-allocating header check; GGUF parser remains a separate component. */
__attribute__((visibility("default"))) int omega_is_gguf_header(const uint8_t *buf, size_t len) {
    return buf && len >= 4 && buf[0] == 'G' && buf[1] == 'G' && buf[2] == 'U' && buf[3] == 'F';
}

/* Bytewise CRC32 for independent native integrity checks. */
__attribute__((visibility("default"))) uint32_t omega_crc32(const uint8_t *buf, size_t len) {
    if (!buf && len) return 0;
    uint32_t crc = 0xffffffffU;
    for (size_t i = 0; i < len; ++i) {
        crc ^= buf[i];
        for (int bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (0xedb88320U & (0U - (crc & 1U)));
    }
    return ~crc;
}
