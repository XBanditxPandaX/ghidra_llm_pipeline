/*
 * Test 4: Operations sur liste chainee
 * Objectif: Tester la detection de structures de donnees
 *
 * Fonctions attendues apres analyse LLM:
 * - Detection de structures de liste chainee
 * - Renommage en create_node, insert_node, delete_node, etc.
 */

#include <stdio.h>
#include <stdlib.h>

// Structure de noeud (sera analysee par le LLM via le code decompile)
typedef struct node {
    int data;
    struct node* next;
} Node;

// Devrait etre renommee "create_list_node" ou "allocate_node"
void* func_301(int value) {
    Node* new_node = (Node*)malloc(sizeof(Node));
    if (new_node != NULL) {
        new_node->data = value;
        new_node->next = NULL;
    }
    return new_node;
}

// Devrait etre renommee "insert_at_head" ou "prepend_node"
void* func_302(void* head, int value) {
    Node* new_node = (Node*)func_301(value);
    if (new_node != NULL) {
        new_node->next = (Node*)head;
    }
    return new_node;
}

// Devrait etre renommee "insert_at_tail" ou "append_node"
void* func_303(void* head, int value) {
    Node* new_node = (Node*)func_301(value);
    if (new_node == NULL) {
        return head;
    }

    if (head == NULL) {
        return new_node;
    }

    Node* current = (Node*)head;
    while (current->next != NULL) {
        current = current->next;
    }
    current->next = new_node;
    return head;
}

// Devrait etre renommee "find_node_by_value" ou "search_list"
void* func_304(void* head, int value) {
    Node* current = (Node*)head;
    while (current != NULL) {
        if (current->data == value) {
            return current;
        }
        current = current->next;
    }
    return NULL;
}

// Devrait etre renommee "delete_node_by_value" ou "remove_from_list"
void* func_305(void* head, int value) {
    Node* current = (Node*)head;
    Node* prev = NULL;

    while (current != NULL) {
        if (current->data == value) {
            if (prev == NULL) {
                // Supprimer la tete
                Node* new_head = current->next;
                free(current);
                return new_head;
            } else {
                prev->next = current->next;
                free(current);
                return head;
            }
        }
        prev = current;
        current = current->next;
    }
    return head;
}

// Devrait etre renommee "count_list_nodes" ou "get_list_length"
int func_306(void* head) {
    int count = 0;
    Node* current = (Node*)head;
    while (current != NULL) {
        count++;
        current = current->next;
    }
    return count;
}

// Devrait etre renommee "reverse_list"
void* func_307(void* head) {
    Node* prev = NULL;
    Node* current = (Node*)head;
    Node* next = NULL;

    while (current != NULL) {
        next = current->next;
        current->next = prev;
        prev = current;
        current = next;
    }
    return prev;
}

// Devrait etre renommee "free_list" ou "destroy_list"
void func_308(void* head) {
    Node* current = (Node*)head;
    while (current != NULL) {
        Node* next = current->next;
        free(current);
        current = next;
    }
}

// Devrait etre renommee "print_list" ou "display_list"
void func_309(void* head) {
    Node* current = (Node*)head;
    printf("[");
    while (current != NULL) {
        printf("%d", current->data);
        if (current->next != NULL) {
            printf(" -> ");
        }
        current = current->next;
    }
    printf("]\n");
}

int main(int argc, char* argv[]) {
    void* list = NULL;

    // Creer une liste
    list = func_303(list, 10);
    list = func_303(list, 20);
    list = func_303(list, 30);
    list = func_302(list, 5);  // Inserer au debut

    printf("Liste originale: ");
    func_309(list);
    printf("Taille: %d\n", func_306(list));

    // Chercher un element
    void* found = func_304(list, 20);
    if (found != NULL) {
        printf("Element 20 trouve!\n");
    }

    // Supprimer un element
    list = func_305(list, 20);
    printf("Apres suppression de 20: ");
    func_309(list);

    // Inverser
    list = func_307(list);
    printf("Liste inversee: ");
    func_309(list);

    // Liberer
    func_308(list);
    printf("Liste liberee.\n");

    return 0;
}
