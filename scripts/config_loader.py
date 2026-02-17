"""
Chargement de la configuration locale (config.json).

Cherche config.json a la racine du projet.
Si absent, propose de le creer a partir de config.example.json.
"""

import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"
CONFIG_EXAMPLE = PROJECT_ROOT / "config.example.json"


def load_config() -> dict:
    """Charge config.json. Le cree depuis config.example.json si absent."""
    if not CONFIG_PATH.exists():
        if CONFIG_EXAMPLE.exists():
            print("[*] Premiere utilisation : creation de config.json depuis config.example.json")
            shutil.copy(CONFIG_EXAMPLE, CONFIG_PATH)
            print(f"[!] Editez {CONFIG_PATH} avec votre chemin Ghidra, puis relancez.")
            print(f"    Champ a modifier : \"ghidra_path\"")
            sys.exit(1)
        else:
            return {}

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_ghidra_path(cli_override: str = None) -> str:
    """Retourne le chemin Ghidra : CLI > config.json > erreur."""
    if cli_override:
        return cli_override

    config = load_config()
    ghidra = config.get("ghidra_path", "")

    if not ghidra or "chemin/vers" in ghidra:
        print("[!] Chemin Ghidra non configure.")
        print(f"    Editez {CONFIG_PATH} et renseignez \"ghidra_path\"")
        print(f"    Ou passez --ghidra en argument.")
        sys.exit(1)

    return ghidra


def get_model(cli_override: str = None) -> str:
    """Retourne le modele : CLI > config.json > defaut."""
    if cli_override:
        return cli_override

    config = load_config()
    return config.get("lm_studio", {}).get("model", "deepseek-r1-0528-qwen3-8b")


def get_lm_studio_url() -> str:
    """Retourne l'URL LM Studio depuis le config."""
    config = load_config()
    return config.get("lm_studio", {}).get("base_url", "http://localhost:1234/v1")
