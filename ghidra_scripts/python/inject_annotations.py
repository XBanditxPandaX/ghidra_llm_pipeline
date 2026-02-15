# Script Ghidra Headless - Reinjection des annotations LLM
# A executer via: analyzeHeadless <project_dir> <project_name> -process <binary> -postScript inject_annotations.py <json_file>
# @category LLM_Pipeline
# @author Memoire M2

from ghidra.program.model.symbol import SourceType
from ghidra.program.model.data import DataTypeManager, PointerDataType
from ghidra.app.cmd.comments import SetCommentCmd
from ghidra.program.model.listing import CodeUnit
from ghidra.util.task import ConsoleTaskMonitor
import json
import os

def get_data_type(type_name, dtm):
    """Recupere ou cree un type de donnees"""
    # Types de base
    basic_types = {
        "void": dtm.getDataType("/void"),
        "int": dtm.getDataType("/int"),
        "char": dtm.getDataType("/char"),
        "short": dtm.getDataType("/short"),
        "long": dtm.getDataType("/long"),
        "float": dtm.getDataType("/float"),
        "double": dtm.getDataType("/double"),
        "uint": dtm.getDataType("/uint"),
        "uchar": dtm.getDataType("/uchar"),
        "ushort": dtm.getDataType("/ushort"),
        "ulong": dtm.getDataType("/ulong"),
        "size_t": dtm.getDataType("/size_t"),
        "bool": dtm.getDataType("/bool"),
    }

    # Gerer les pointeurs
    if type_name.endswith('*'):
        base_type = type_name[:-1].strip()
        base_dt = get_data_type(base_type, dtm)
        if base_dt:
            return PointerDataType(base_dt)

    return basic_types.get(type_name.lower())

def apply_function_rename(func, new_name):
    """Renomme une fonction"""
    try:
        func.setName(new_name, SourceType.USER_DEFINED)
        print("[+] Renomme: {} -> {}".format(func.getName(), new_name))
        return True
    except Exception as e:
        print("[!] Erreur renommage {}: {}".format(func.getName(), e))
        return False

def apply_return_type(func, type_name):
    """Change le type de retour d'une fonction"""
    try:
        dtm = currentProgram.getDataTypeManager()
        dt = get_data_type(type_name, dtm)
        if dt:
            func.setReturnType(dt, SourceType.USER_DEFINED)
            print("[+] Type retour {}: {}".format(func.getName(), type_name))
            return True
    except Exception as e:
        print("[!] Erreur type retour {}: {}".format(func.getName(), e))
    return False

def apply_parameter_types(func, param_suggestions):
    """Applique les types et noms de parametres"""
    try:
        params = func.getParameters()
        dtm = currentProgram.getDataTypeManager()

        for suggestion in param_suggestions:
            original = suggestion.get("original", "")
            new_name = suggestion.get("suggested_name")
            new_type = suggestion.get("suggested_type")

            # Trouver le parametre correspondant
            for param in params:
                if param.getName() == original or original in param.getName():
                    if new_name:
                        param.setName(new_name, SourceType.USER_DEFINED)
                        print("[+] Param renomme: {} -> {}".format(original, new_name))

                    if new_type:
                        dt = get_data_type(new_type, dtm)
                        if dt:
                            param.setDataType(dt, SourceType.USER_DEFINED)
                            print("[+] Param type: {} = {}".format(new_name or original, new_type))
                    break

        return True
    except Exception as e:
        print("[!] Erreur parametres {}: {}".format(func.getName(), e))
    return False

def apply_comment(func, comment, comment_type="plate"):
    """Ajoute un commentaire a la fonction"""
    try:
        addr = func.getEntryPoint()

        if comment_type == "plate":
            # Commentaire de type "plate" (en-tete de fonction)
            cmd = SetCommentCmd(addr, CodeUnit.PLATE_COMMENT, comment)
        elif comment_type == "pre":
            cmd = SetCommentCmd(addr, CodeUnit.PRE_COMMENT, comment)
        else:
            cmd = SetCommentCmd(addr, CodeUnit.EOL_COMMENT, comment)

        cmd.applyTo(currentProgram)
        print("[+] Commentaire ajoute pour {}".format(func.getName()))
        return True
    except Exception as e:
        print("[!] Erreur commentaire {}: {}".format(func.getName(), e))
    return False

def apply_suggestion(func, suggestion):
    """Applique toutes les suggestions pour une fonction"""
    success_count = 0

    # Verifier le seuil de confiance
    confidence = suggestion.get("confidence", 0)
    if confidence < 0.5:
        print("[*] Confiance faible ({}) pour {} - ignore".format(confidence, func.getName()))
        return 0

    # Appliquer le renommage
    if suggestion.get("suggested_name"):
        if apply_function_rename(func, suggestion["suggested_name"]):
            success_count += 1

    # Appliquer le type de retour
    if suggestion.get("suggested_return_type"):
        if apply_return_type(func, suggestion["suggested_return_type"]):
            success_count += 1

    # Appliquer les types de parametres
    if suggestion.get("suggested_param_types"):
        if apply_parameter_types(func, suggestion["suggested_param_types"]):
            success_count += 1

    # Appliquer les commentaires
    comment_parts = []
    if suggestion.get("comments"):
        comment_parts.append(suggestion["comments"])
    if suggestion.get("detected_apis"):
        apis = ", ".join(suggestion["detected_apis"])
        comment_parts.append("APIs detectees: " + apis)
    if suggestion.get("reasoning"):
        comment_parts.append("Analyse LLM: " + suggestion["reasoning"])

    if comment_parts:
        full_comment = "\n".join(comment_parts)
        if apply_comment(func, full_comment, "plate"):
            success_count += 1

    return success_count

def main():
    print("[*] Demarrage de l'injection des annotations LLM...")

    # Recuperer le fichier JSON des arguments
    args = getScriptArgs()
    if not args:
        # Chercher le fichier par defaut
        json_file = currentProgram.getName() + "_llm_suggestions.json"
        print("[*] Recherche du fichier par defaut: " + json_file)
    else:
        json_file = args[0]

    # Charger les suggestions
    if not os.path.exists(json_file):
        print("[!] Fichier non trouve: " + json_file)
        return

    with open(json_file, 'r') as f:
        suggestions = json.load(f)

    print("[*] {} suggestions chargees".format(len(suggestions)))

    # Appliquer les suggestions
    func_manager = currentProgram.getFunctionManager()
    applied_count = 0
    error_count = 0

    for suggestion in suggestions:
        address_str = suggestion.get("address", "")
        original_name = suggestion.get("original_name", "")

        # Trouver la fonction
        func = None

        # Par adresse
        if address_str:
            try:
                addr = currentProgram.getAddressFactory().getAddress(address_str)
                func = func_manager.getFunctionAt(addr)
            except:
                pass

        # Par nom
        if not func and original_name:
            functions = list(func_manager.getFunctions(True))
            for f in functions:
                if f.getName() == original_name:
                    func = f
                    break

        if func:
            count = apply_suggestion(func, suggestion)
            applied_count += count
        else:
            print("[!] Fonction non trouvee: {} / {}".format(original_name, address_str))
            error_count += 1

    print("\n[+] Injection terminee:")
    print("    {} modifications appliquees".format(applied_count))
    print("    {} erreurs".format(error_count))

if __name__ == "__main__":
    main()
