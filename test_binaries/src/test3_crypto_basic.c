/*
 * Test 3: Operations cryptographiques basiques
 * Objectif: Tester la detection de patterns cryptographiques
 *
 * Fonctions attendues apres analyse LLM:
 * - Detection de XOR cipher
 * - Detection de ROT13
 * - Detection de substitution simple
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Devrait etre renommee "xor_encrypt_decrypt" ou "xor_cipher"
// API detectee: pattern de chiffrement XOR
void func_201(unsigned char* data, size_t len, unsigned char key) {
    for (size_t i = 0; i < len; i++) {
        data[i] = data[i] ^ key;
    }
}

// Devrait etre renommee "xor_with_key_array" ou "xor_cipher_multikey"
void func_202(unsigned char* data, size_t data_len,
              const unsigned char* key, size_t key_len) {
    for (size_t i = 0; i < data_len; i++) {
        data[i] = data[i] ^ key[i % key_len];
    }
}

// Devrait etre renommee "rot13_transform"
void func_203(char* str) {
    while (*str != '\0') {
        if ((*str >= 'A' && *str <= 'M') || (*str >= 'a' && *str <= 'm')) {
            *str = *str + 13;
        } else if ((*str >= 'N' && *str <= 'Z') || (*str >= 'n' && *str <= 'z')) {
            *str = *str - 13;
        }
        str++;
    }
}

// Devrait etre renommee "caesar_cipher"
void func_204(char* str, int shift) {
    while (*str != '\0') {
        if (*str >= 'A' && *str <= 'Z') {
            *str = (((*str - 'A') + shift) % 26) + 'A';
        } else if (*str >= 'a' && *str <= 'z') {
            *str = (((*str - 'a') + shift) % 26) + 'a';
        }
        str++;
    }
}

// Devrait etre renommee "calculate_simple_checksum"
unsigned int func_205(const unsigned char* data, size_t len) {
    unsigned int sum = 0;
    for (size_t i = 0; i < len; i++) {
        sum += data[i];
    }
    return sum;
}

// Devrait etre renommee "calculate_xor_checksum"
unsigned char func_206(const unsigned char* data, size_t len) {
    unsigned char checksum = 0;
    for (size_t i = 0; i < len; i++) {
        checksum ^= data[i];
    }
    return checksum;
}

// Devrait etre renommee "base64_encode_char" ou "get_base64_char"
static const char b64_table[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

char func_207(unsigned char val) {
    if (val < 64) {
        return b64_table[val];
    }
    return '=';
}

// Devrait etre renommee "simple_hash" ou "djb2_hash"
unsigned long func_208(const char* str) {
    unsigned long hash = 5381;
    int c;
    while ((c = *str++)) {
        hash = ((hash << 5) + hash) + c;  // hash * 33 + c
    }
    return hash;
}

int main(int argc, char* argv[]) {
    char message[] = "Secret Message!";
    unsigned char key = 0x42;

    printf("Original: %s\n", message);

    // XOR encrypt
    func_201((unsigned char*)message, strlen(message), key);
    printf("XOR encrypted (hex): ");
    for (size_t i = 0; i < strlen(message); i++) {
        printf("%02X ", (unsigned char)message[i]);
    }
    printf("\n");

    // XOR decrypt
    func_201((unsigned char*)message, strlen(message), key);
    printf("XOR decrypted: %s\n", message);

    // ROT13
    func_203(message);
    printf("ROT13: %s\n", message);
    func_203(message);  // ROT13 twice = original
    printf("ROT13 back: %s\n", message);

    // Caesar cipher
    func_204(message, 3);
    printf("Caesar +3: %s\n", message);

    // Checksum
    printf("Checksum: %u\n", func_205((unsigned char*)message, strlen(message)));
    printf("XOR Checksum: %02X\n", func_206((unsigned char*)message, strlen(message)));

    // Hash
    printf("Hash: %lu\n", func_208(message));

    return 0;
}
