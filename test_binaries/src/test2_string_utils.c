/*
 * Test 2: Utilitaires de chaines de caracteres
 * Objectif: Tester la detection de fonctions de manipulation de strings
 *
 * Fonctions attendues apres analyse LLM:
 * - FUN_xxx -> calculate_string_length
 * - FUN_yyy -> copy_string
 * - FUN_zzz -> concatenate_strings
 * - FUN_aaa -> find_character_in_string
 * - FUN_bbb -> convert_to_uppercase
 */

#include <stdio.h>
#include <stdlib.h>

// Devrait etre renommee "calculate_string_length"
unsigned int func_101(const char* str) {
    unsigned int len = 0;
    while (str[len] != '\0') {
        len++;
    }
    return len;
}

// Devrait etre renommee "copy_string"
char* func_102(char* dest, const char* src) {
    char* original_dest = dest;
    while (*src != '\0') {
        *dest = *src;
        dest++;
        src++;
    }
    *dest = '\0';
    return original_dest;
}

// Devrait etre renommee "concatenate_strings"
char* func_103(char* dest, const char* src) {
    char* ptr = dest;
    // Aller a la fin de dest
    while (*ptr != '\0') {
        ptr++;
    }
    // Copier src
    while (*src != '\0') {
        *ptr = *src;
        ptr++;
        src++;
    }
    *ptr = '\0';
    return dest;
}

// Devrait etre renommee "find_character_in_string"
char* func_104(const char* str, int ch) {
    while (*str != '\0') {
        if (*str == (char)ch) {
            return (char*)str;
        }
        str++;
    }
    if (ch == '\0') {
        return (char*)str;
    }
    return NULL;
}

// Devrait etre renommee "convert_to_uppercase"
void func_105(char* str) {
    while (*str != '\0') {
        if (*str >= 'a' && *str <= 'z') {
            *str = *str - 32;  // 'a' - 'A' = 32
        }
        str++;
    }
}

// Devrait etre renommee "reverse_string"
void func_106(char* str) {
    unsigned int len = func_101(str);
    if (len < 2) return;

    char* start = str;
    char* end = str + len - 1;

    while (start < end) {
        char tmp = *start;
        *start = *end;
        *end = tmp;
        start++;
        end--;
    }
}

// Devrait etre renommee "count_character_occurrences"
int func_107(const char* str, char ch) {
    int count = 0;
    while (*str != '\0') {
        if (*str == ch) {
            count++;
        }
        str++;
    }
    return count;
}

// Devrait etre renommee "trim_whitespace"
char* func_108(char* str) {
    // Trim debut
    while (*str == ' ' || *str == '\t' || *str == '\n') {
        str++;
    }

    if (*str == '\0') {
        return str;
    }

    // Trim fin
    char* end = str + func_101(str) - 1;
    while (end > str && (*end == ' ' || *end == '\t' || *end == '\n')) {
        *end = '\0';
        end--;
    }

    return str;
}

int main(int argc, char* argv[]) {
    char buffer[256] = "   Hello, World!   ";
    char buffer2[256] = "";

    printf("Original: '%s'\n", buffer);

    // Trim
    char* trimmed = func_108(buffer);
    printf("Trimmed: '%s'\n", trimmed);

    // Longueur
    printf("Length: %u\n", func_101(trimmed));

    // Copie
    func_102(buffer2, trimmed);
    printf("Copy: '%s'\n", buffer2);

    // Majuscules
    func_105(buffer2);
    printf("Upper: '%s'\n", buffer2);

    // Inverse
    func_106(buffer2);
    printf("Reversed: '%s'\n", buffer2);

    // Comptage
    printf("Count 'L': %d\n", func_107(buffer2, 'L'));

    return 0;
}
