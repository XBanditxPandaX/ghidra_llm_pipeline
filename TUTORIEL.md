# Tutoriel Complet - Pipeline Ghidra + LLM

## Introduction

Ce projet implemente un pipeline d'amelioration automatique de l'analyse statique Ghidra via un modele de langage (LLM). Le pipeline effectue trois taches principales :

1. **Renommage de fonctions** : Propose des noms descriptifs pour les fonctions
2. **Detection d'API implicites** : Identifie les patterns et APIs utilises
3. **Generation de commentaires** : Cree des commentaires explicatifs

---

## Prerequis

### 1. Ghidra

Telecharger depuis https://ghidra-sre.org/ et extraire dans un dossier de votre choix.

**Ou trouver le chemin Ghidra ?**

Apres extraction, le dossier ressemble a :
```
ghidra_12.0.1_PUBLIC/
├── support/
│   ├── analyzeHeadless.bat   <-- c'est ce fichier que le pipeline utilise
│   └── ...
├── Ghidra/
└── ghidraRun.bat
```

Le chemin a retenir est le dossier racine, par exemple :
- Windows : `C:/Users/votre_nom/ghidra_12.0.1_PUBLIC`
- Linux : `/home/votre_nom/ghidra_12.0.1_PUBLIC`
- Mac : `/Applications/ghidra_12.0.1_PUBLIC`

### 2. LM Studio + Modeles

**Installation :**

1. Telecharger LM Studio depuis https://lmstudio.ai/
2. Installer et lancer LM Studio

**Telecharger les modeles :**

Dans LM Studio, onglet "Discover", telecharger un ou plusieurs de ces modeles :
- `deepseek-r1-0528-qwen3-8b`
- `qwen2.5-coder-7b-instruct`
- `codellama-7b-instruct`

**Demarrer le serveur local :**

1. Aller dans l'onglet "Local Server" (icone serveur a gauche)
2. Selectionner le modele charge
3. Cliquer sur "Start Server"
4. Le serveur ecoute par defaut sur http://localhost:1234

**Verifier le serveur :**

```bash
curl http://localhost:1234/v1/models
```

### 3. Python 3.8+

**Installer les dependances :**

```bash
pip install -r requirements.txt
```

### 4. Compilateur C (pour les binaires de test)

```bash
# Via chocolatey (Windows)
choco install mingw

# Ou telecharger depuis https://www.mingw-w64.org/
```

---

## Configuration (config.json)

**A la premiere utilisation**, le projet cree automatiquement un fichier `config.json` a partir de `config.example.json`. Il faut ensuite le modifier avec vos chemins.

### Etape 1 : Generer le config.json

Lancez n'importe quelle commande du pipeline, par exemple :

```bash
python scripts/quick_test.py
```

Le fichier `config.json` sera cree a la racine du projet. Le script vous demandera de l'editer.

### Etape 2 : Editer config.json

Ouvrez `config.json` et modifiez le champ `ghidra_path` avec votre chemin Ghidra :

```json
{
    "ghidra_path": "C:/Users/votre_nom/ghidra_12.0.1_PUBLIC",
    "lm_studio": {
        "base_url": "http://localhost:1234/v1",
        "model": "deepseek-r1-0528-qwen3-8b"
    }
}
```

**Important :**
- Utilisez des `/` (slashes) meme sous Windows (pas des `\`)
- Le chemin doit pointer vers le dossier qui contient `support/analyzeHeadless.bat`
- `config.json` est dans le `.gitignore` : vos chemins personnels ne seront jamais envoyes sur git

### Etape 3 : Verifier

```bash
python scripts/quick_test.py
```

Si tout est OK, vous verrez `[+] Ghidra trouve: ...`

### Alternative : passer les chemins en argument

Vous pouvez aussi passer le chemin Ghidra et le modele directement en argument, sans toucher au config :

```bash
python scripts/pipeline.py --binary test.exe --ghidra "C:/chemin/vers/ghidra" --model "deepseek-r1-0528-qwen3-8b"
```

Les arguments CLI sont toujours prioritaires sur le `config.json`.

---

## Structure du Projet

```
ghidra_llm_pipeline/
├── scripts/
│   ├── pipeline.py          # Pipeline principal
│   ├── LLM_client.py        # Client LM Studio (API OpenAI)
│   ├── config_loader.py     # Chargement de la configuration
│   ├── evaluate_results.py  # Evaluation des resultats (BLEU, ROUGE, etc.)
│   ├── multipass.py         # Analyse multi-passes avec enrichissement
│   ├── benchmark.py         # Benchmark comparatif multi-modeles
│   └── quick_test.py        # Test rapide de l'environnement
├── ghidra_scripts/
│   ├── java/
│   │   ├── extract_functions.java   # Extraction Ghidra (headless)
│   │   └── inject_annotations.java  # Injection Ghidra (headless)
│   └── python/
│       ├── extract_functions.py     # Extraction (PyGhidra)
│       └── inject_annotations.py    # Injection (PyGhidra)
├── test_binaries/
│   ├── src/                  # Code source C de test
│   ├── bin/                  # Binaires compiles
│   ├── extracted_files/      # JSONs extraits par Ghidra
│   ├── suggested_files/      # Suggestions du LLM
│   ├── report_files/         # Rapports d'execution
│   └── compile.bat           # Script de compilation
├── expected_results/
│   └── ground_truth.json     # Resultats attendus
├── config.example.json       # Configuration exemple (a copier en config.json)
├── config.json               # Votre configuration locale (non versionne)
└── TUTORIEL.md               # Ce fichier
```

---

## Partie 1 : Test Rapide

### Verifier l'environnement

```bash
python scripts/quick_test.py
```

Le chemin Ghidra est lu depuis `config.json`. Vous pouvez aussi le passer en argument :

```bash
python scripts/quick_test.py --ghidra "C:/chemin/vers/ghidra"
```

### Compiler les binaires de test

```bash
cd test_binaries
compile.bat
```

---

## Partie 2 : Pipeline Automatique

### Verifier la configuration

```bash
python scripts/pipeline.py ^
    --binary test_binaries/bin/test1_buffer.exe ^
    --verify-only
```

### Executer le pipeline complet

```bash
python scripts/pipeline.py ^
    --binary test_binaries/bin/test1_buffer.exe ^
    --task full
```

Le chemin Ghidra et le modele sont lus depuis `config.json`. Vous pouvez les surcharger :

```bash
python scripts/pipeline.py ^
    --binary test_binaries/bin/test1_buffer.exe ^
    --ghidra "C:/chemin/vers/ghidra" ^
    --model deepseek-r1-0528-qwen3-8b ^
    --task full
```

Les fichiers de sortie seront dans :
- `test_binaries/extracted_files/` : JSONs extraits
- `test_binaries/suggested_files/` : Suggestions LLM
- `test_binaries/report_files/` : Rapports

### Options du pipeline

| Option           | Description                                                           |
| ---------------- | --------------------------------------------------------------------- |
| `--binary`, `-b` | Chemin du binaire a analyser (obligatoire)                            |
| `--ghidra`, `-g` | Chemin d'installation Ghidra (optionnel si config.json)               |
| `--model`, `-m`  | Modele LM Studio (optionnel si config.json)                          |
| `--task`, `-t`   | Type de tache: `rename`, `detect_apis`, `comments`, `full`           |
| `--verify-only`  | Verifier la configuration sans lancer l'analyse                      |

### Script batch (Windows)

```bash
run_pipeline.bat test_binaries\bin\test1_buffer.exe
```

Ou avec un chemin Ghidra explicite :

```bash
run_pipeline.bat test_binaries\bin\test1_buffer.exe "C:\chemin\vers\ghidra"
```

---

## Partie 3 : Evaluation des Resultats

```bash
python scripts/evaluate_results.py ^
    --suggestions test_binaries/suggested_files/test1_buffer_suggestions.json ^
    --ground-truth expected_results/ground_truth.json ^
    --output evaluation_report.json
```

### Metriques d'evaluation

| Metrique                  | Description                               |
| ------------------------- | ----------------------------------------- |
| **Exact Match Rate**      | Pourcentage de noms exactement corrects   |
| **Acceptable Match Rate** | Pourcentage de noms acceptables           |
| **Semantic Score**        | Similarite semantique moyenne (0-1)       |
| **BLEU**                  | Score BLEU des commentaires               |
| **ROUGE-1/2/L**           | Scores ROUGE des commentaires             |
| **API Precision/Recall**  | Precision et rappel des APIs detectees    |
| **Hallucination Rate**    | Taux de suggestions incorrectes/inventees |

---

## Partie 4 : Benchmark Multi-Modeles

### Single-pass (un modele)

```bash
python scripts/benchmark.py ^
    --models "deepseek-r1-0528-qwen3-8b" ^
    --inputs test_binaries/extracted_files/*_extracted.json ^
    --ground-truth expected_results/ground_truth.json ^
    --output results/benchmark/ ^
    --no-multipass
```

### Benchmark complet (3 modeles + multi-pass)

```bash
python scripts/benchmark.py ^
    --models "deepseek-r1-0528-qwen3-8b" "qwen2.5-coder-7b-instruct" "codellama-7b-instruct" ^
    --inputs test_binaries/extracted_files/*_extracted.json ^
    --ground-truth expected_results/ground_truth.json ^
    --output results/benchmark/ ^
    --multipass
```

Le script demandera de charger chaque modele dans LM Studio quand c'est son tour.

---

## Partie 5 : Multi-Pass Iteratif

```bash
python scripts/multipass.py ^
    --input test_binaries/extracted_files/test1_buffer.exe_extracted.json ^
    --ground-truth expected_results/ground_truth.json ^
    --output results/multipass/
```

Le modele est lu depuis `config.json`. Vous pouvez le surcharger :

```bash
python scripts/multipass.py ^
    --input test_binaries/extracted_files/test1_buffer.exe_extracted.json ^
    --ground-truth expected_results/ground_truth.json ^
    --model "deepseek-r1-0528-qwen3-8b" ^
    --output results/multipass/
```

Le multi-pass effectue 3 passes successives :
1. **Passe 1** : Renommage des fonctions
2. **Passe 2** : Analyse complete avec noms enrichis
3. **Passe 3** : Generation de commentaires avec contexte maximal

---

## Depannage

### LM Studio ne repond pas

```bash
curl http://localhost:1234/v1/models
# Si pas de reponse: lancer LM Studio, charger un modele, demarrer le serveur
```

### Ghidra headless echoue

- Verifier que Java 17+ est installe (`java -version`)
- Verifier le chemin Ghidra dans `config.json` (doit contenir `support/analyzeHeadless.bat`)
- Ghidra 12+ ne supporte plus les scripts Python en headless, utiliser les scripts Java

### config.json non trouve

Si le fichier `config.json` n'existe pas, lancez n'importe quel script et il sera cree automatiquement depuis `config.example.json`. Editez ensuite le champ `ghidra_path`.

### Modele trop lent

- Utiliser une quantification plus agressive (Q4_K_S)
- Reduire max_tokens dans config.json (`lm_studio.options.max_tokens`)
- Activer GPU acceleration dans LM Studio

---

## Ressources

- [Documentation Ghidra](https://ghidra-sre.org/)
- [LM Studio](https://lmstudio.ai/)
- [DeepSeek Coder](https://github.com/deepseek-ai/DeepSeek-Coder)
