/*
 * Test 1: Operations sur les buffers
 * Objectif: Tester la detection de fonctions de manipulation memoire
 *
 * Fonctions attendues apres analyse LLM:
 * - FUN_xxx -> allocate_and_copy_buffer
 * - FUN_yyy -> free_buffer_safely
 * - FUN_zzz -> resize_buffer
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Cette fonction devrait etre renommee "allocate_and_copy_buffer" ou similaire
void* func_001(void* src, size_t size) {
    void* dst = malloc(size);
    if (dst != NULL) {
        memcpy(dst, src, size);
    }
    return dst;
}

// Cette fonction devrait etre renommee "free_buffer_safely" ou similaire
void func_002(void** ptr) {
    if (ptr != NULL && *ptr != NULL) {
        free(*ptr);
        *ptr = NULL;
    }
}

// Cette fonction devrait etre renommee "resize_buffer" ou similaire
void* func_003(void* old_buf, size_t old_size, size_t new_size) {
    void* new_buf = malloc(new_size);
    if (new_buf != NULL) {
        size_t copy_size = (old_size < new_size) ? old_size : new_size;
        memcpy(new_buf, old_buf, copy_size);
        free(old_buf);
    }
    return new_buf;
}

// Cette fonction devrait etre renommee "compare_buffers" ou similaire
int func_004(const void* buf1, const void* buf2, size_t size) {
    const unsigned char* p1 = buf1;
    const unsigned char* p2 = buf2;
    for (size_t i = 0; i < size; i++) {
        if (p1[i] != p2[i]) {
            return (int)(p1[i] - p2[i]);
        }
    }
    return 0;
}

// Cette fonction devrait etre renommee "fill_buffer_with_pattern" ou similaire
void func_005(void* buf, size_t size, unsigned char pattern) {
    unsigned char* p = buf;
    for (size_t i = 0; i < size; i++) {
        p[i] = pattern;
    }
}

int main(int argc, char* argv[]) {
    char data[] = "Hello, World!";

    // Allouer et copier
    void* copy = func_001(data, sizeof(data));

    // Remplir avec un pattern
    func_005(copy, sizeof(data), 0xAA);

    // Redimensionner
    copy = func_003(copy, sizeof(data), 64);

    // Comparer
    char test[64] = {0};
    int result = func_004(copy, test, 64);

    // Liberer
    func_002(&copy);

    printf("Result: %d\n", result);
    return 0;
}
