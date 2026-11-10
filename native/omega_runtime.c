/* Freestanding Android ARM64 core. Real GGUF header validation and checksum API.
 * This native library does not bundle Python, Git, Termux or llama.cpp.
 * SPDX-License-Identifier: MIT
 */
typedef unsigned long omega_size_t;
typedef unsigned long long omega_u64;

__attribute__((visibility("default"))) int omega_runtime_abi_version(void) { return 2; }

__attribute__((visibility("default"))) int omega_gguf_version(const unsigned char *data, omega_size_t length) {
    if (!data || length < 8) return -1;
    if (data[0] != 'G' || data[1] != 'G' || data[2] != 'U' || data[3] != 'F') return -2;
    unsigned int v = ((unsigned int)data[4]) | ((unsigned int)data[5] << 8) |
                     ((unsigned int)data[6] << 16) | ((unsigned int)data[7] << 24);
    if (v < 2 || v > 3) return -3;
    return (int)v;
}

__attribute__((visibility("default"))) omega_u64 omega_fnv1a64(const unsigned char *data, omega_size_t length) {
    if (!data && length) return 0;
    omega_u64 hash = 14695981039346656037ULL;
    for (omega_size_t i = 0; i < length; ++i) {
        hash ^= data[i];
        hash *= 1099511628211ULL;
    }
    return hash;
}

__attribute__((visibility("default"))) int omega_utf8_valid(const unsigned char *s, omega_size_t n) {
    if (!s && n) return 0;
    for (omega_size_t i = 0; i < n;) {
        unsigned char c = s[i++];
        if (c < 0x80) continue;
        unsigned int count, min;
        if ((c & 0xE0) == 0xC0) { count = 1; min = 0x80; }
        else if ((c & 0xF0) == 0xE0) { count = 2; min = 0x800; }
        else if ((c & 0xF8) == 0xF0) { count = 3; min = 0x10000; }
        else return 0;
        if (n - i < count) return 0;
        unsigned int cp = c & ((1u << (6 - count)) - 1);
        for (unsigned int j = 0; j < count; ++j) {
            if ((s[i] & 0xC0) != 0x80) return 0;
            cp = (cp << 6) | (s[i++] & 0x3F);
        }
        if (cp < min || cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF)) return 0;
    }
    return 1;
}

/* JNI entrypoint uses only primitive JNI types; no Android SDK headers required. */
__attribute__((visibility("default"))) int
Java_org_omega_actions_core_OmegaNative_abiVersion(void *env, void *klass) {
    (void)env; (void)klass;
    return omega_runtime_abi_version();
}
