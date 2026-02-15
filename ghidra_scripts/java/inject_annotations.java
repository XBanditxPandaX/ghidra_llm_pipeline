// Script Ghidra - Reinjection des annotations LLM
// A executer via: analyzeHeadless <project_dir> <project_name> -process <binary> -postScript inject_annotations.java <json_file>
// @category LLM_Pipeline
// @author Memoire M2

import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.comments.SetCommentCmd;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;

import java.io.File;
import java.io.FileReader;
import java.util.*;
import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import java.lang.reflect.Type;

public class inject_annotations extends GhidraScript {

    private int appliedCount = 0;
    private int errorCount = 0;

    /**
     * Recupere un type de donnees de base ou un pointeur a partir du nom.
     */
    private DataType getDataType(String typeName, DataTypeManager dtm) {
        if (typeName == null || typeName.isEmpty()) {
            return null;
        }

        // Gerer les pointeurs (recursif)
        if (typeName.endsWith("*")) {
            String baseTypeName = typeName.substring(0, typeName.length() - 1).trim();
            DataType baseDt = getDataType(baseTypeName, dtm);
            if (baseDt != null) {
                return new PointerDataType(baseDt);
            }
            return null;
        }

        // Types de base
        Map<String, String> typeMap = new LinkedHashMap<>();
        typeMap.put("void", "/void");
        typeMap.put("int", "/int");
        typeMap.put("char", "/char");
        typeMap.put("short", "/short");
        typeMap.put("long", "/long");
        typeMap.put("float", "/float");
        typeMap.put("double", "/double");
        typeMap.put("uint", "/uint");
        typeMap.put("uchar", "/uchar");
        typeMap.put("ushort", "/ushort");
        typeMap.put("ulong", "/ulong");
        typeMap.put("size_t", "/size_t");
        typeMap.put("bool", "/bool");

        String path = typeMap.get(typeName.toLowerCase());
        if (path != null) {
            return dtm.getDataType(path);
        }

        return null;
    }

    /**
     * Renomme une fonction.
     */
    private boolean applyFunctionRename(Function func, String newName) {
        try {
            String oldName = func.getName();
            func.setName(newName, SourceType.USER_DEFINED);
            println("[+] Renomme: " + oldName + " -> " + newName);
            return true;
        } catch (Exception e) {
            println("[!] Erreur renommage " + func.getName() + ": " + e.getMessage());
            return false;
        }
    }

    /**
     * Change le type de retour d'une fonction.
     */
    private boolean applyReturnType(Function func, String typeName) {
        try {
            DataTypeManager dtm = currentProgram.getDataTypeManager();
            DataType dt = getDataType(typeName, dtm);
            if (dt != null) {
                func.setReturnType(dt, SourceType.USER_DEFINED);
                println("[+] Type retour " + func.getName() + ": " + typeName);
                return true;
            }
        } catch (Exception e) {
            println("[!] Erreur type retour " + func.getName() + ": " + e.getMessage());
        }
        return false;
    }

    /**
     * Applique les types et noms de parametres.
     */
    @SuppressWarnings("unchecked")
    private boolean applyParameterTypes(Function func, List<Map<String, Object>> paramSuggestions) {
        try {
            Parameter[] params = func.getParameters();
            DataTypeManager dtm = currentProgram.getDataTypeManager();

            for (Map<String, Object> suggestion : paramSuggestions) {
                String original = (String) suggestion.getOrDefault("original", "");
                String newName = (String) suggestion.get("suggested_name");
                String newType = (String) suggestion.get("suggested_type");

                // Trouver le parametre correspondant
                for (Parameter param : params) {
                    if (param.getName().equals(original) || param.getName().contains(original)) {
                        if (newName != null && !newName.isEmpty()) {
                            param.setName(newName, SourceType.USER_DEFINED);
                            println("[+] Param renomme: " + original + " -> " + newName);
                        }

                        if (newType != null && !newType.isEmpty()) {
                            DataType dt = getDataType(newType, dtm);
                            if (dt != null) {
                                param.setDataType(dt, SourceType.USER_DEFINED);
                                String displayName = (newName != null && !newName.isEmpty()) ? newName : original;
                                println("[+] Param type: " + displayName + " = " + newType);
                            }
                        }
                        break;
                    }
                }
            }

            return true;
        } catch (Exception e) {
            println("[!] Erreur parametres " + func.getName() + ": " + e.getMessage());
        }
        return false;
    }

    /**
     * Ajoute un commentaire a la fonction.
     */
    private boolean applyComment(Function func, String comment, String commentType) {
        try {
            Address addr = func.getEntryPoint();
            int codeUnitType;

            switch (commentType) {
                case "pre":
                    codeUnitType = CodeUnit.PRE_COMMENT;
                    break;
                case "eol":
                    codeUnitType = CodeUnit.EOL_COMMENT;
                    break;
                case "plate":
                default:
                    codeUnitType = CodeUnit.PLATE_COMMENT;
                    break;
            }

            SetCommentCmd cmd = new SetCommentCmd(addr, codeUnitType, comment);
            cmd.applyTo(currentProgram);
            println("[+] Commentaire ajoute pour " + func.getName());
            return true;
        } catch (Exception e) {
            println("[!] Erreur commentaire " + func.getName() + ": " + e.getMessage());
        }
        return false;
    }

    /**
     * Applique toutes les suggestions pour une fonction.
     */
    @SuppressWarnings("unchecked")
    private int applySuggestion(Function func, Map<String, Object> suggestion) {
        int successCount = 0;

        // Verifier le seuil de confiance
        double confidence = 0.0;
        Object confObj = suggestion.get("confidence");
        if (confObj instanceof Number) {
            confidence = ((Number) confObj).doubleValue();
        }
        if (confidence < 0.5) {
            println("[*] Confiance faible (" + confidence + ") pour " + func.getName() + " - ignore");
            return 0;
        }

        // Appliquer le renommage
        String suggestedName = (String) suggestion.get("suggested_name");
        if (suggestedName != null && !suggestedName.isEmpty()) {
            if (applyFunctionRename(func, suggestedName)) {
                successCount++;
            }
        }

        // Appliquer le type de retour
        String suggestedReturnType = (String) suggestion.get("suggested_return_type");
        if (suggestedReturnType != null && !suggestedReturnType.isEmpty()) {
            if (applyReturnType(func, suggestedReturnType)) {
                successCount++;
            }
        }

        // Appliquer les types de parametres
        Object paramTypesObj = suggestion.get("suggested_param_types");
        if (paramTypesObj instanceof List) {
            List<Map<String, Object>> paramTypes = (List<Map<String, Object>>) paramTypesObj;
            if (applyParameterTypes(func, paramTypes)) {
                successCount++;
            }
        }

        // Appliquer les commentaires
        List<String> commentParts = new ArrayList<>();

        String comments = (String) suggestion.get("comments");
        if (comments != null && !comments.isEmpty()) {
            commentParts.add(comments);
        }

        Object detectedApisObj = suggestion.get("detected_apis");
        if (detectedApisObj instanceof List) {
            List<String> detectedApis = (List<String>) detectedApisObj;
            if (!detectedApis.isEmpty()) {
                commentParts.add("APIs detectees: " + String.join(", ", detectedApis));
            }
        }

        String reasoning = (String) suggestion.get("reasoning");
        if (reasoning != null && !reasoning.isEmpty()) {
            commentParts.add("Analyse LLM: " + reasoning);
        }

        if (!commentParts.isEmpty()) {
            String fullComment = String.join("\n", commentParts);
            if (applyComment(func, fullComment, "plate")) {
                successCount++;
            }
        }

        return successCount;
    }

    @Override
    @SuppressWarnings("unchecked")
    public void run() throws Exception {

        println("[*] Demarrage de l'injection des annotations LLM...");

        // Recuperer le fichier JSON des arguments
        String[] args = getScriptArgs();
        String jsonFilePath;

        if (args == null || args.length == 0) {
            // Chercher le fichier par defaut a cote du binaire analyse
            // (meme logique que extract_functions.java pour la sortie)
            File binDir = new File(currentProgram.getExecutablePath()).getParentFile();
            jsonFilePath = new File(binDir, currentProgram.getName() + "_llm_suggestions.json").getAbsolutePath();
            println("[*] Recherche du fichier par defaut: " + jsonFilePath);
        } else {
            jsonFilePath = args[0];
        }

        File jsonFile = new File(jsonFilePath);
        if (!jsonFile.exists()) {
            println("[!] Fichier non trouve: " + jsonFile.getAbsolutePath());
            return;
        }

        // Charger les suggestions depuis le JSON
        Gson gson = new Gson();
        Type listType = new TypeToken<List<Map<String, Object>>>() {}.getType();
        FileReader reader = new FileReader(jsonFile);
        List<Map<String, Object>> suggestions = gson.fromJson(reader, listType);
        reader.close();

        println("[*] " + suggestions.size() + " suggestions chargees");

        // Appliquer les suggestions
        FunctionManager funcManager = currentProgram.getFunctionManager();

        for (Map<String, Object> suggestion : suggestions) {
            if (monitor.isCancelled()) {
                break;
            }

            String addressStr = (String) suggestion.getOrDefault("address", "");
            String originalName = (String) suggestion.getOrDefault("original_name", "");

            Function func = null;

            // Recherche par adresse
            if (addressStr != null && !addressStr.isEmpty()) {
                try {
                    Address addr = currentProgram.getAddressFactory().getAddress(addressStr);
                    func = funcManager.getFunctionAt(addr);
                } catch (Exception e) {
                    // ignore, on essaie par nom
                }
            }

            // Recherche par nom
            if (func == null && originalName != null && !originalName.isEmpty()) {
                FunctionIterator it = funcManager.getFunctions(true);
                while (it.hasNext()) {
                    Function f = it.next();
                    if (f.getName().equals(originalName)) {
                        func = f;
                        break;
                    }
                }
            }

            if (func != null) {
                int count = applySuggestion(func, suggestion);
                appliedCount += count;
            } else {
                println("[!] Fonction non trouvee: " + originalName + " / " + addressStr);
                errorCount++;
            }
        }

        println("");
        println("[+] Injection terminee:");
        println("    " + appliedCount + " modifications appliquees");
        println("    " + errorCount + " erreurs");
    }
}
