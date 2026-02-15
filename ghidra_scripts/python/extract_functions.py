# Script Ghidra Headless - Extraction des fonctions pour analyse LLM
# A executer via: analyzeHeadless <project_dir> <project_name> -import <binary> -postScript extract_functions.py
# @category LLM_Pipeline
# @author Memoire M2

from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor
from ghidra.program.model.symbol import SourceType
import json
import os

def get_function_info(func, decompiler):
    """Extrait les informations d'une fonction pour le LLM"""
    info = {
        "name": func.getName(),
        "address": str(func.getEntryPoint()),
        "signature": str(func.getSignature()),
        "is_thunk": func.isThunk(),
        "calling_convention": str(func.getCallingConventionName()),
        "parameter_count": func.getParameterCount(),
        "parameters": [],
        "local_variables": [],
        "called_functions": [],
        "calling_functions": [],
        "decompiled_code": "",
        "size": func.getBody().getNumAddresses()
    }

    # Parametres
    for param in func.getParameters():
        info["parameters"].append({
            "name": param.getName(),
            "type": str(param.getDataType()),
            "storage": str(param.getVariableStorage())
        })

    # Variables locales
    for var in func.getLocalVariables():
        info["local_variables"].append({
            "name": var.getName(),
            "type": str(var.getDataType()),
            "storage": str(var.getVariableStorage())
        })

    # Fonctions appelees
    for ref in func.getCalledFunctions(ConsoleTaskMonitor()):
        info["called_functions"].append({
            "name": ref.getName(),
            "address": str(ref.getEntryPoint())
        })

    # Fonctions appelantes
    for ref in func.getCallingFunctions(ConsoleTaskMonitor()):
        info["calling_functions"].append({
            "name": ref.getName(),
            "address": str(ref.getEntryPoint())
        })

    # Decompilation
    try:
        results = decompiler.decompileFunction(func, 60, ConsoleTaskMonitor())
        if results.decompileCompleted():
            decomp = results.getDecompiledFunction()
            if decomp:
                info["decompiled_code"] = decomp.getC()
    except Exception as e:
        info["decompiled_code"] = "// Decompilation failed: " + str(e)

    return info

def get_strings_in_function(func):
    """Recupere les chaines de caracteres referencees par la fonction"""
    strings = []
    listing = currentProgram.getListing()
    refs = currentProgram.getReferenceManager()

    addr_set = func.getBody()
    for addr in addr_set.getAddresses(True):
        for ref in refs.getReferencesFrom(addr):
            to_addr = ref.getToAddress()
            data = listing.getDataAt(to_addr)
            if data and data.hasStringValue():
                strings.append({
                    "address": str(to_addr),
                    "value": str(data.getValue())
                })
    return strings

def main():
    print("[*] Demarrage de l'extraction pour analyse LLM...")

    # Initialiser le decompilateur
    decompiler = DecompInterface()
    decompiler.openProgram(currentProgram)

    # Informations sur le binaire
    binary_info = {
        "name": currentProgram.getName(),
        "path": currentProgram.getExecutablePath(),
        "format": currentProgram.getExecutableFormat(),
        "language": str(currentProgram.getLanguage()),
        "compiler": str(currentProgram.getCompiler()),
        "image_base": str(currentProgram.getImageBase()),
        "functions": []
    }

    # Extraire toutes les fonctions
    func_manager = currentProgram.getFunctionManager()
    functions = func_manager.getFunctions(True)

    count = 0
    for func in functions:
        # Ignorer les fonctions externes/thunks simples
        if func.isExternal():
            continue

        func_info = get_function_info(func, decompiler)
        func_info["strings"] = get_strings_in_function(func)
        binary_info["functions"].append(func_info)
        count += 1

        if count % 10 == 0:
            print("[*] Traitement: {} fonctions...".format(count))

    print("[*] Total: {} fonctions extraites".format(count))

    # Sauvegarder en JSON
    output_dir = os.path.dirname(currentProgram.getExecutablePath())
    if not output_dir:
        output_dir = "."

    output_file = os.path.join(output_dir, currentProgram.getName() + "_extracted.json")

    with open(output_file, 'w') as f:
        json.dump(binary_info, f, indent=2)

    print("[+] Extraction sauvegardee dans: " + output_file)

    decompiler.dispose()

if __name__ == "__main__":
    main()
