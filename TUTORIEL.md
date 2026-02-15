# Tutoriel Complet - Pipeline Ghidra + LLM

## Introduction

Ce projet implémente un pipeline d'amélioration automatique de l'analyse statique Ghidra via un modèle de langage (LLM). Le pipeline effectue trois tâches principales :

1. **Renommage de fonctions** : Propose des noms descriptifs pour les fonctions
2. **Détection d'API implicites** : Identifie les patterns et APIs utilisés
3. **Génération de commentaires** : Crée des commentaires explicatifs

---

## Prérequis

### 1. Ghidra

### 2. LM Studio + DeepSeek Coder

**Installation :**

1. Télécharger LM Studio depuis https://lmstudio.ai/
2. Installer et lancer LM Studio

**Télécharger le modèle DeepSeek Coder :**

1. Dans LM Studio, aller dans l'onglet "Discover"
2. Rechercher "deepseek-coder-6.7B-instruct-GGUF" (par TheBloke)
3. Télécharger une version quantifiée (recommandé: Q4_K_M ou Q5_K_M)
   - Source: https://huggingface.co/TheBloke/deepseek-coder-6.7B-instruct-GGUF

**Démarrer le serveur local :**

1. Aller dans l'onglet "Local Server" (icône serveur à gauche)
2. Sélectionner le modèle deepseek-coder chargé
3. Cliquer sur "Start Server"
4. Le serveur écoute par défaut sur http://localhost:1234

**Vérifier le serveur :**

```bash
curl http://localhost:1234/v1/models
```

### 3. Python 3.8+

**Installer les dépendances :**

```bash
pip install requests
```

### 4. Compilateur C (pour les binaires de test)

**Option A : MinGW (GCC)**

```bash
# Via chocolatey
choco install mingw

# Ou télécharger depuis https://www.mingw-w64.org/
```

## Structure du Projet

```
ghidra_llm_pipeline/
├── scripts/
│   ├── pipeline.py          # Pipeline principal
│   ├── ollama_client.py     # Client pour Ollama
│   └── evaluate_results.py  # Évaluation des résultats
├── ghidra_scripts/
│   ├── extract_functions.py # Script Ghidra d'extraction
│   └── inject_annotations.py # Script Ghidra d'injection
├── test_binaries/
│   ├── src/                  # Code source C de test
│   ├── bin/                  # Binaires compilés
│   └── compile.bat           # Script de compilation
├── expected_results/
│   └── ground_truth.json     # Résultats attendus
├── results/                   # Résultats des analyses
└── TUTORIEL.md               # Ce fichier
```

---

## Partie 1 : Test Manuel Pas à Pas

### Étape 1 : Compiler les binaires de test

```bash
cd "C:\Users\themi\OneDrive - Institut Catholique de Lille\Bureau\CoursM1\M2\ghidra_llm_pipeline\test_binaries"
compile.bat
```

### Étape 2 : Extraire les fonctions avec Ghidra (manuel)

**Méthode A : Via l'interface graphique**

1. Lancer Ghidra
2. Créer un nouveau projet ou utiliser un projet existant
3. Importer un binaire de test (File > Import File)
4. Double-cliquer pour ouvrir dans CodeBrowser
5. Laisser l'analyse automatique se terminer
6. Aller dans Window > Script Manager
7. Chercher "extract_functions.py" et l'exécuter

Cela génère un fichier `test1_buffer.exe_extracted.json` contenant toutes les informations sur les fonctions.

### Étape 3 : Tester LM Studio manuellement

1. **Vérifier que LM Studio fonctionne :**

```bash
curl http://localhost:1234/v1/models
```

2. **Tester une requête simple :**

```bash
curl http://localhost:1234/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\": \"deepseek-coder-6.7b-instruct\", \"messages\": [{\"role\": \"user\", \"content\": \"What does this function do? void* func(void* src, size_t size) { void* dst = malloc(size); memcpy(dst, src, size); return dst; }\"}]}"
```

3. **Tester avec le client Python :**

```bash
cd "C:\Users\themi\Desktop\CoursM1\M2\ghidra_llm_pipeline\scripts"
python LLM_client.py
```

### Étape 4 : Analyser une fonction manuellement

Ouvrez le fichier JSON extrait et copiez une fonction. Envoyez-la à LLM avec ce prompt :

```
Tu es un expert en reverse engineering. Analyse ce code décompilé et propose :
1. Un nom de fonction descriptif
2. Les types de paramètres appropriés
3. Un commentaire explicatif

Code :
void * FUN_00401000(int param_1, int param_2) {
    void *pvVar1;
    pvVar1 = malloc(param_2);
    if (pvVar1 != (void *)0x0) {
        memcpy(pvVar1, param_1, param_2);
    }
    return pvVar1;
}

Réponds en JSON avec ce format :
{
    "suggested_name": "...",
    "suggested_return_type": "...",
    "suggested_param_types": [{"original": "param_1", "suggested_name": "...", "suggested_type": "..."}],
    "comments": "...",
    "confidence": 0.8
}
```

---

## Partie 2 : Utilisation du Pipeline Automatique

### Étape 1 : Vérifier la configuration

```bash
cd "C:\Users\themi\Bureau\CoursM1\M2\ghidra_llm_pipeline\scripts"

python pipeline.py ^
    --ghidra "C:\Users\themi\Bureau\CoursM1\M2\ghidra_12.0.1_PUBLIC" ^
    --model deepseek-coder-6.7b-instruct ^
    --verify-only
```

### Étape 2 : Exécuter le pipeline complet

```bash
python pipeline.py ^
    --binary "C:\Users\themi\Bureau\CoursM1\M2\ghidra_llm_pipeline\test_binaries\bin\test1_buffer.exe" ^
    --ghidra "C:\Users\themi\Bureau\CoursM1\M2\ghidra_12.0.1_PUBLIC" ^
    --model deepseek-coder-6.7b-instruct ^
    --task full ^
    --output "../results"
```

### Étape 3 : Options du pipeline

| Option           | Description                                                |
| ---------------- | ---------------------------------------------------------- |
| `--binary`, `-b` | Chemin du binaire à analyser                               |
| `--ghidra`, `-g` | Chemin d'installation Ghidra                               |
| `--model`, `-m`  | Modèle LM Studio (défaut: deepseek-coder-6.7b-instruct)    |
| `--task`, `-t`   | Type de tâche: `rename`, `detect_apis`, `comments`, `full` |
| `--output`, `-o` | Répertoire de sortie                                       |

### Étape 4 : Analyser les résultats

Le pipeline génère plusieurs fichiers :

- `*_extracted.json` : Fonctions extraites de Ghidra
- `*_suggestions.json` : Suggestions du LLM
- `*_report.json` : Rapport d'exécution

---

## Partie 3 : Évaluation des Résultats

### Utiliser le script d'évaluation

```bash
python evaluate_results.py ^
    --suggestions "../results/test1_buffer_suggestions_*.json" ^
    --ground-truth "../expected_results/ground_truth.json" ^
    --output "../results/evaluation_report.json"
```

### Métriques d'évaluation

| Métrique                  | Description                               |
| ------------------------- | ----------------------------------------- |
| **Exact Match Rate**      | Pourcentage de noms exactement corrects   |
| **Acceptable Match Rate** | Pourcentage de noms acceptables           |
| **Semantic Score**        | Similarité sémantique moyenne (0-1)       |
| **API Precision**         | Précision des APIs détectées              |
| **API Recall**            | Rappel des APIs détectées                 |
| **Comment Score**         | Score de qualité des commentaires         |
| **Hallucination Rate**    | Taux de suggestions incorrectes/inventées |

---

## Partie 4 : Protocole Expérimental pour le Mémoire

### Phase 1 : Préparation

1. **Compiler les 5 binaires de test**
2. **Vérifier LMStudio** avec différents modèles
3. **Établir la baseline** : analyser manuellement 2-3 fonctions par binaire

### Phase 2 : Expérimentation

Pour chaque binaire, effectuer :

```bash
# Analyse avec DeepSeek Coder
python pipeline.py -b binary.exe -g /path/to/ghidra -m deepseek-coder-6.7b-instruct -t full -o results/deepseek/
```

### Phase 3 : Évaluation=

1. **Évaluation automatique** :

```bash
python evaluate_results.py -s results/*_suggestions.json -g expected_results/ground_truth.json -o final_evaluation.json
```

2. **Évaluation manuelle** :
   - Sélectionner 20-30 fonctions aléatoires
   - Faire noter par 2-3 évaluateurs
   - Utiliser une échelle de 1-5 pour :
     - Pertinence du nom (1=incorrect, 5=parfait)
     - Utilité du commentaire
     - Précision des types

### Phase 4 : Analyse

Calculer et documenter :

- Précision globale par tâche
- Variation selon la complexité des fonctions
- Taux d'hallucinations par catégorie
- Comparaison entre modèles

---

## Partie 6 : Dépannage

### Problème : LM Studio ne répond pas

```bash
# Vérifier si le serveur tourne
curl http://localhost:1234/v1/models

# Solutions:
# 1. Vérifier que LM Studio est lancé
# 2. Aller dans l'onglet "Local Server"
# 3. Vérifier qu'un modèle est chargé
# 4. Cliquer sur "Start Server" si nécessaire
# 5. Vérifier le port (par défaut 1234)
```

### Problème : Ghidra headless échoue

```bash
# Vérifier les permissions
# Vérifier le chemin du JDK

# Exécuter avec plus de logs
support\analyzeHeadless.bat ... -log analysis.log
```

### Problème : Modèle trop lent

```
# Solutions dans LM Studio:
# 1. Utiliser une quantification plus aggressive (Q4_K_S au lieu de Q5_K_M)
# 2. Réduire le context length dans les paramètres du serveur
# 3. Activer GPU acceleration si disponible
# 4. Ajuster max_tokens dans ollama_client.py (réduire à 512)
```

### Problème : Extraction JSON vide

- Vérifier que le binaire a été correctement analysé
- Vérifier les permissions d'écriture
- Exécuter le script dans l'interface Ghidra pour voir les erreurs

---

## Annexe : Commandes Utiles

```bash
# Vérifier que LM Studio répond
curl http://localhost:1234/v1/models

# Tester une requête simple
curl http://localhost:1234/v1/chat/completions ^
  -H "Content-Type: application/json" ^
  -d "{\"model\": \"deepseek-coder-6.7b-instruct\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}]}"

# Tester le client Python
python scripts/ollama_client.py
```

---

## Ressources

- [Documentation Ghidra](https://ghidra-sre.org/)
- [API Ghidra Python](https://ghidra.re/ghidra_docs/api/)
- [LM Studio](https://lmstudio.ai/)
- [DeepSeek Coder GGUF (TheBloke)](https://huggingface.co/TheBloke/deepseek-coder-6.7B-instruct-GGUF)
- [DeepSeek Coder Paper](https://arxiv.org/abs/2401.14196)
