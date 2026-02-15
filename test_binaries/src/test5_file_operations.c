/*
 * Test 5: Operations sur fichiers
 * Objectif: Tester la detection d'API de fichiers
 *
 * APIs attendues:
 * - fopen, fclose, fread, fwrite
 * - Detection de patterns de lecture/ecriture de fichiers
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Devrait etre renommee "read_entire_file" ou "load_file_contents"
char* func_401(const char* filename, size_t* out_size) {
    FILE* file = fopen(filename, "rb");
    if (file == NULL) {
        return NULL;
    }

    // Obtenir la taille
    fseek(file, 0, SEEK_END);
    long size = ftell(file);
    fseek(file, 0, SEEK_SET);

    // Allouer le buffer
    char* buffer = (char*)malloc(size + 1);
    if (buffer == NULL) {
        fclose(file);
        return NULL;
    }

    // Lire le contenu
    size_t read = fread(buffer, 1, size, file);
    buffer[read] = '\0';

    fclose(file);

    if (out_size != NULL) {
        *out_size = read;
    }

    return buffer;
}

// Devrait etre renommee "write_to_file" ou "save_buffer_to_file"
int func_402(const char* filename, const char* data, size_t size) {
    FILE* file = fopen(filename, "wb");
    if (file == NULL) {
        return -1;
    }

    size_t written = fwrite(data, 1, size, file);
    fclose(file);

    return (written == size) ? 0 : -1;
}

// Devrait etre renommee "append_to_file"
int func_403(const char* filename, const char* data) {
    FILE* file = fopen(filename, "ab");
    if (file == NULL) {
        return -1;
    }

    size_t len = strlen(data);
    size_t written = fwrite(data, 1, len, file);
    fclose(file);

    return (written == len) ? 0 : -1;
}

// Devrait etre renommee "file_exists" ou "check_file_exists"
int func_404(const char* filename) {
    FILE* file = fopen(filename, "r");
    if (file != NULL) {
        fclose(file);
        return 1;  // Existe
    }
    return 0;  // N'existe pas
}

// Devrait etre renommee "get_file_size"
long func_405(const char* filename) {
    FILE* file = fopen(filename, "rb");
    if (file == NULL) {
        return -1;
    }

    fseek(file, 0, SEEK_END);
    long size = ftell(file);
    fclose(file);

    return size;
}

// Devrait etre renommee "copy_file"
int func_406(const char* src, const char* dst) {
    FILE* source = fopen(src, "rb");
    if (source == NULL) {
        return -1;
    }

    FILE* dest = fopen(dst, "wb");
    if (dest == NULL) {
        fclose(source);
        return -1;
    }

    unsigned char buffer[4096];
    size_t bytes;

    while ((bytes = fread(buffer, 1, sizeof(buffer), source)) > 0) {
        fwrite(buffer, 1, bytes, dest);
    }

    fclose(source);
    fclose(dest);

    return 0;
}

// Devrait etre renommee "read_line_from_file" ou "get_next_line"
char* func_407(FILE* file) {
    char* line = NULL;
    size_t capacity = 0;
    size_t length = 0;
    int ch;

    while ((ch = fgetc(file)) != EOF && ch != '\n') {
        if (length >= capacity) {
            capacity = (capacity == 0) ? 64 : capacity * 2;
            char* new_line = (char*)realloc(line, capacity);
            if (new_line == NULL) {
                free(line);
                return NULL;
            }
            line = new_line;
        }
        line[length++] = (char)ch;
    }

    if (length == 0 && ch == EOF) {
        free(line);
        return NULL;
    }

    // Ajouter le terminateur
    if (length >= capacity) {
        char* new_line = (char*)realloc(line, length + 1);
        if (new_line == NULL) {
            free(line);
            return NULL;
        }
        line = new_line;
    }
    line[length] = '\0';

    return line;
}

// Devrait etre renommee "count_lines_in_file"
int func_408(const char* filename) {
    FILE* file = fopen(filename, "r");
    if (file == NULL) {
        return -1;
    }

    int count = 0;
    int ch;
    int prev_ch = '\n';

    while ((ch = fgetc(file)) != EOF) {
        if (ch == '\n') {
            count++;
        }
        prev_ch = ch;
    }

    // Compter la derniere ligne si elle ne se termine pas par \n
    if (prev_ch != '\n') {
        count++;
    }

    fclose(file);
    return count;
}

int main(int argc, char* argv[]) {
    const char* test_file = "test_output.txt";
    const char* content = "Hello, World!\nThis is a test.\nLine 3.\n";

    // Ecrire
    printf("Writing to file...\n");
    if (func_402(test_file, content, strlen(content)) == 0) {
        printf("File written successfully.\n");
    }

    // Verifier existence
    if (func_404(test_file)) {
        printf("File exists.\n");
    }

    // Taille
    printf("File size: %ld bytes\n", func_405(test_file));

    // Nombre de lignes
    printf("Line count: %d\n", func_408(test_file));

    // Lire
    size_t read_size;
    char* data = func_401(test_file, &read_size);
    if (data != NULL) {
        printf("Read %zu bytes:\n%s\n", read_size, data);
        free(data);
    }

    // Copier
    printf("Copying file...\n");
    func_406(test_file, "test_output_copy.txt");

    // Append
    func_403(test_file, "Appended line.\n");

    return 0;
}
