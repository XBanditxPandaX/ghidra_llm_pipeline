"""
Module d'integration avec LM Studio (DeepSeek) pour l'analyse de code decompile
Supporte les 3 taches principales:
1. Renommage de fonctions
2. Detection d'API implicites
3. Generation de commentaires

Compatible avec l'API OpenAI de LM Studio (http://localhost:1234/v1/)
"""

import requests
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class TaskType(Enum):
    RENAME_FUNCTION = "rename"
    DETECT_APIS = "detect_apis"
    GENERATE_COMMENTS = "comments"
    FULL_ANALYSIS = "full"

@dataclass
class LLMSuggestion:
    """Resultat d'analyse du LLM"""
    original_name: str
    suggested_name: Optional[str] = None
    suggested_return_type: Optional[str] = None
    suggested_param_types: Optional[List[Dict]] = None
    detected_apis: Optional[List[str]] = None
    comments: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""

class LMStudioClient:
    """Client pour communiquer avec LM Studio (API compatible OpenAI)"""

    def __init__(self, base_url: str = "http://localhost:1234/v1", model: str = "deepseek-coder"):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.api_endpoint = f"{self.base_url}/chat/completions"

    def check_connection(self) -> bool:
        """Verifie que LM Studio est accessible"""
        try:
            response = requests.get(f"{self.base_url}/models", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def list_models(self) -> List[str]:
        """Liste les modeles disponibles"""
        try:
            response = requests.get(f"{self.base_url}/models", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return [m["id"] for m in data.get("data", [])]
        except requests.exceptions.RequestException:
            pass
        return []

    def _build_prompt(self, task: TaskType, func_info: Dict) -> str:
        """Construit le prompt selon la tache"""

        base_context = f"""Tu es un expert en reverse engineering et analyse de binaires.
Analyse le code decompile suivant et reponds UNIQUEMENT en JSON valide.

Informations sur la fonction:
- Nom actuel: {func_info.get('name', 'unknown')}
- Signature: {func_info.get('signature', 'unknown')}
- Adresse: {func_info.get('address', 'unknown')}
- Fonctions appelees: {', '.join([f['name'] for f in func_info.get('called_functions', [])])}
- Chaines de caracteres: {', '.join([s['value'] for s in func_info.get('strings', [])])}

Code decompile:
```c
{func_info.get('decompiled_code', '// No code available')}
```
"""

        if task == TaskType.RENAME_FUNCTION:
            return base_context + """
Tache: Propose un nom de fonction plus descriptif.

Reponds UNIQUEMENT avec ce JSON:
{
    "suggested_name": "nom_propose",
    "confidence": 0.8,
    "reasoning": "explication courte"
}
"""

        elif task == TaskType.DETECT_APIS:
            return base_context + """
Tache: Identifie les API Windows/POSIX implicitement utilisees ou les patterns reconnaissables.

Reponds UNIQUEMENT avec ce JSON:
{
    "detected_apis": ["api1", "api2"],
    "detected_patterns": ["pattern1"],
    "confidence": 0.8,
    "reasoning": "explication courte"
}
"""

        elif task == TaskType.GENERATE_COMMENTS:
            return base_context + """
Tache: Genere un commentaire explicatif pour cette fonction.

Reponds UNIQUEMENT avec ce JSON:
{
    "summary": "description en une ligne",
    "detailed_comment": "commentaire detaille multi-lignes",
    "confidence": 0.8
}
"""

        else:  # FULL_ANALYSIS
            return base_context + """
Tache: Analyse complete de la fonction.

Reponds UNIQUEMENT avec ce JSON:
{
    "suggested_name": "nom_propose",
    "suggested_return_type": "type_retour",
    "suggested_param_types": [
        {"original": "param1", "suggested_name": "nouveau_nom", "suggested_type": "type"}
    ],
    "detected_apis": ["api1", "api2"],
    "summary": "description en une ligne",
    "detailed_comment": "commentaire detaille",
    "confidence": 0.8,
    "reasoning": "explication"
}
"""

    def _query_llm(self, prompt: str) -> Optional[str]:
        """Envoie une requete a LM Studio (API OpenAI compatible)"""
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Tu es un expert en reverse engineering et analyse de binaires. Reponds toujours en JSON valide."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,  # Plus deterministe pour l'analyse de code
                "max_tokens": 1024,
                "stream": False
            }

            response = requests.post(
                self.api_endpoint,
                json=payload,
                timeout=120
            )

            if response.status_code == 200:
                data = response.json()
                # Format OpenAI: choices[0].message.content
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")

        except requests.exceptions.RequestException as e:
            print(f"[!] Erreur LM Studio: {e}")

        return None

    def _parse_json_response(self, response: str) -> Optional[Dict]:
        """Parse la reponse JSON du LLM"""
        try:
            # Chercher le JSON dans la reponse
            start = response.find('{')
            end = response.rfind('}') + 1

            if start != -1 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        return None

    def analyze_function(self, func_info: Dict, task: TaskType = TaskType.FULL_ANALYSIS) -> Optional[LLMSuggestion]:
        """Analyse une fonction avec le LLM"""

        prompt = self._build_prompt(task, func_info)
        response = self._query_llm(prompt)

        if not response:
            return None

        parsed = self._parse_json_response(response)
        if not parsed:
            print(f"[!] Impossible de parser la reponse pour {func_info.get('name')}")
            return None

        suggestion = LLMSuggestion(
            original_name=func_info.get('name', 'unknown'),
            suggested_name=parsed.get('suggested_name'),
            suggested_return_type=parsed.get('suggested_return_type'),
            suggested_param_types=parsed.get('suggested_param_types'),
            detected_apis=parsed.get('detected_apis'),
            comments=parsed.get('detailed_comment') or parsed.get('summary'),
            confidence=parsed.get('confidence', 0.0),
            reasoning=parsed.get('reasoning', '')
        )

        return suggestion

    def analyze_batch(self, functions: List[Dict], task: TaskType = TaskType.FULL_ANALYSIS) -> List[LLMSuggestion]:
        """Analyse un lot de fonctions"""
        results = []

        for i, func in enumerate(functions):
            print(f"[*] Analyse {i+1}/{len(functions)}: {func.get('name', 'unknown')}")
            suggestion = self.analyze_function(func, task)
            if suggestion:
                results.append(suggestion)

        return results


def main():
    """Test du client LM Studio avec DeepSeek Coder"""
    # Le nom du modele dans LM Studio depend de comment vous l'avez charge
    # Generalement c'est le nom du fichier GGUF ou le nom affiche dans LM Studio
    client = LMStudioClient(model="deepseek-coder-6.7b-instruct")

    print("[*] Verification de la connexion LM Studio...")
    if not client.check_connection():
        print("[!] LM Studio n'est pas accessible.")
        print("    1. Lancez LM Studio")
        print("    2. Chargez le modele deepseek-coder-6.7B-instruct-GGUF")
        print("    3. Demarrez le serveur local (onglet 'Local Server')")
        print("    4. Verifiez que le serveur ecoute sur http://localhost:1234")
        return

    print("[+] Connexion OK")
    print(f"[*] Modeles disponibles: {client.list_models()}")

    # Test avec une fonction exemple
    test_func = {
        "name": "FUN_00401000",
        "signature": "undefined FUN_00401000(undefined4 param_1, undefined4 param_2)",
        "address": "00401000",
        "called_functions": [{"name": "malloc"}, {"name": "memcpy"}],
        "strings": [{"value": "Error: buffer overflow"}],
        "decompiled_code": """
void * FUN_00401000(int param_1, int param_2) {
    void *pvVar1;
    pvVar1 = malloc(param_2);
    if (pvVar1 != (void *)0x0) {
        memcpy(pvVar1, param_1, param_2);
    }
    return pvVar1;
}
"""
    }

    print("\n[*] Test d'analyse complete...")
    result = client.analyze_function(test_func, TaskType.FULL_ANALYSIS)

    if result:
        print(f"\n[+] Resultats:")
        print(f"    Nom suggere: {result.suggested_name}")
        print(f"    Type retour: {result.suggested_return_type}")
        print(f"    APIs detectees: {result.detected_apis}")
        print(f"    Commentaire: {result.comments}")
        print(f"    Confiance: {result.confidence}")
        print(f"    Raisonnement: {result.reasoning}")


# Alias pour compatibilite avec l'ancien code (pipeline.py utilise LLMClient)
LLMClient = LMStudioClient


if __name__ == "__main__":
    main()
