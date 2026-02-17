// Script Ghidra - Reinjection des annotations LLM
// Pas de dependance externe (Gson) - parsing JSON manuel
// @category LLM_Pipeline
// @author Memoire M2

import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.comments.SetCommentCmd;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;

import java.io.File;
import java.nio.file.Files;
import java.util.*;

public class inject_annotations extends GhidraScript {

    private int appliedCount = 0;
    private int errorCount = 0;

    // ===== Parsing JSON minimal =====

    private int pos;
    private String json;

    private void skipWhitespace() {
        while (pos < json.length() && Character.isWhitespace(json.charAt(pos))) pos++;
    }

    private char peek() {
        skipWhitespace();
        return pos < json.length() ? json.charAt(pos) : 0;
    }

    private char next() {
        skipWhitespace();
        return pos < json.length() ? json.charAt(pos++) : 0;
    }

    private String parseString() {
        if (next() != '"') return null;
        StringBuilder sb = new StringBuilder();
        while (pos < json.length()) {
            char c = json.charAt(pos++);
            if (c == '"') return sb.toString();
            if (c == '\\' && pos < json.length()) {
                char esc = json.charAt(pos++);
                switch (esc) {
                    case '"': sb.append('"'); break;
                    case '\\': sb.append('\\'); break;
                    case 'n': sb.append('\n'); break;
                    case 'r': sb.append('\r'); break;
                    case 't': sb.append('\t'); break;
                    case '/': sb.append('/'); break;
                    case 'u':
                        if (pos + 4 <= json.length()) {
                            sb.append((char) Integer.parseInt(json.substring(pos, pos + 4), 16));
                            pos += 4;
                        }
                        break;
                    default: sb.append(esc);
                }
            } else {
                sb.append(c);
            }
        }
        return sb.toString();
    }

    private Object parseValue() {
        char c = peek();
        if (c == '"') return parseString();
        if (c == '{') return parseObject();
        if (c == '[') return parseArray();
        if (c == 't' || c == 'f') return parseBoolean();
        if (c == 'n') { pos += 4; return null; }
        return parseNumber();
    }

    private Double parseNumber() {
        skipWhitespace();
        int start = pos;
        while (pos < json.length() && "0123456789.eE+-".indexOf(json.charAt(pos)) >= 0) pos++;
        try {
            return Double.parseDouble(json.substring(start, pos));
        } catch (Exception e) {
            return 0.0;
        }
    }

    private Boolean parseBoolean() {
        skipWhitespace();
        if (json.startsWith("true", pos)) { pos += 4; return true; }
        if (json.startsWith("false", pos)) { pos += 5; return false; }
        return false;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> parseObject() {
        Map<String, Object> map = new LinkedHashMap<>();
        next(); // {
        while (peek() != '}') {
            String key = parseString();
            next(); // :
            Object value = parseValue();
            map.put(key, value);
            if (peek() == ',') next();
        }
        next(); // }
        return map;
    }

    private List<Object> parseArray() {
        List<Object> list = new ArrayList<>();
        next(); // [
        while (peek() != ']') {
            list.add(parseValue());
            if (peek() == ',') next();
        }
        next(); // ]
        return list;
    }

    // ===== Logique d'injection =====

    private DataType getDataType(String typeName, DataTypeManager dtm) {
        if (typeName == null || typeName.isEmpty()) return null;

        if (typeName.endsWith("*")) {
            String baseTypeName = typeName.substring(0, typeName.length() - 1).trim();
            DataType baseDt = getDataType(baseTypeName, dtm);
            if (baseDt != null) return new PointerDataType(baseDt);
            return null;
        }

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
        if (path != null) return dtm.getDataType(path);
        return null;
    }

    private String getStr(Map<String, Object> map, String key) {
        Object v = map.get(key);
        return (v instanceof String) ? (String) v : null;
    }

    private double getNum(Map<String, Object> map, String key) {
        Object v = map.get(key);
        return (v instanceof Number) ? ((Number) v).doubleValue() : 0.0;
    }

    @SuppressWarnings("unchecked")
    private int applySuggestion(Function func, Map<String, Object> suggestion) {
        int successCount = 0;

        double confidence = getNum(suggestion, "confidence");
        if (confidence < 0.5) {
            println("[*] Confiance faible (" + confidence + ") pour " + func.getName() + " - ignore");
            return 0;
        }

        // Renommage
        String suggestedName = getStr(suggestion, "suggested_name");
        if (suggestedName != null && !suggestedName.isEmpty()) {
            try {
                String oldName = func.getName();
                func.setName(suggestedName, SourceType.USER_DEFINED);
                println("[+] Renomme: " + oldName + " -> " + suggestedName);
                successCount++;
            } catch (Exception e) {
                println("[!] Erreur renommage: " + e.getMessage());
            }
        }

        // Type de retour
        String returnType = getStr(suggestion, "suggested_return_type");
        if (returnType != null && !returnType.isEmpty()) {
            try {
                DataType dt = getDataType(returnType, currentProgram.getDataTypeManager());
                if (dt != null) {
                    func.setReturnType(dt, SourceType.USER_DEFINED);
                    successCount++;
                }
            } catch (Exception e) {
                println("[!] Erreur type retour: " + e.getMessage());
            }
        }

        // Parametres
        Object paramObj = suggestion.get("suggested_param_types");
        if (paramObj instanceof List) {
            try {
                List<Object> paramList = (List<Object>) paramObj;
                Parameter[] params = func.getParameters();
                DataTypeManager dtm = currentProgram.getDataTypeManager();

                for (Object item : paramList) {
                    if (!(item instanceof Map)) continue;
                    Map<String, Object> pSugg = (Map<String, Object>) item;
                    String original = getStr(pSugg, "original");
                    String newName = getStr(pSugg, "suggested_name");
                    String newType = getStr(pSugg, "suggested_type");

                    for (Parameter param : params) {
                        if (param.getName().equals(original) || param.getName().contains(original != null ? original : "")) {
                            if (newName != null && !newName.isEmpty()) {
                                param.setName(newName, SourceType.USER_DEFINED);
                            }
                            if (newType != null && !newType.isEmpty()) {
                                DataType dt = getDataType(newType, dtm);
                                if (dt != null) param.setDataType(dt, SourceType.USER_DEFINED);
                            }
                            successCount++;
                            break;
                        }
                    }
                }
            } catch (Exception e) {
                println("[!] Erreur parametres: " + e.getMessage());
            }
        }

        // Commentaires
        List<String> commentParts = new ArrayList<>();
        String comments = getStr(suggestion, "comments");
        if (comments != null && !comments.isEmpty()) commentParts.add(comments);
        String reasoning = getStr(suggestion, "reasoning");
        if (reasoning != null && !reasoning.isEmpty()) commentParts.add("Analyse: " + reasoning);

        Object apisObj = suggestion.get("detected_apis");
        if (apisObj instanceof List) {
            List<Object> apis = (List<Object>) apisObj;
            if (!apis.isEmpty()) {
                StringBuilder sb = new StringBuilder("APIs: ");
                for (int i = 0; i < apis.size(); i++) {
                    if (i > 0) sb.append(", ");
                    sb.append(apis.get(i));
                }
                commentParts.add(sb.toString());
            }
        }

        if (!commentParts.isEmpty()) {
            try {
                String fullComment = String.join("\n", commentParts);
                SetCommentCmd cmd = new SetCommentCmd(func.getEntryPoint(), CodeUnit.PLATE_COMMENT, fullComment);
                cmd.applyTo(currentProgram);
                successCount++;
            } catch (Exception e) {
                println("[!] Erreur commentaire: " + e.getMessage());
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
            File binDir = new File(currentProgram.getExecutablePath()).getParentFile();
            File parentDir = binDir.getParentFile();
            jsonFilePath = new File(new File(parentDir, "suggested_files"),
                    currentProgram.getName().replace(".exe", "") + "_suggestions.json").getAbsolutePath();
            println("[*] Recherche du fichier par defaut: " + jsonFilePath);
        } else {
            jsonFilePath = args[0];
        }

        File jsonFile = new File(jsonFilePath);
        if (!jsonFile.exists()) {
            println("[!] Fichier non trouve: " + jsonFile.getAbsolutePath());
            return;
        }

        println("[*] Chargement: " + jsonFile.getAbsolutePath());

        // Lire et parser le JSON
        json = new String(Files.readAllBytes(jsonFile.toPath()), "UTF-8");
        pos = 0;

        List<Object> suggestions = parseArray();
        println("[*] " + suggestions.size() + " suggestions chargees");

        // Appliquer les suggestions
        FunctionManager funcManager = currentProgram.getFunctionManager();

        for (Object item : suggestions) {
            if (monitor.isCancelled()) break;
            if (!(item instanceof Map)) continue;

            Map<String, Object> suggestion = (Map<String, Object>) item;
            String originalName = getStr(suggestion, "original_name");

            Function func = null;

            // Recherche par nom
            if (originalName != null && !originalName.isEmpty()) {
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
                println("[!] Fonction non trouvee: " + originalName);
                errorCount++;
            }
        }

        println("[+] Injection terminee: " + appliedCount + " modifications, " + errorCount + " erreurs");
    }
}
