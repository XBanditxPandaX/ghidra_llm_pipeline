// Script Ghidra - Extraction des fonctions pour analyse LLM
// @category LLM_Pipeline
// @author Memoire M2
// Pas de dependance externe (Gson) - JSON ecrit manuellement

import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.util.task.ConsoleTaskMonitor;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;

import java.io.FileWriter;
import java.io.BufferedWriter;
import java.io.File;
import java.util.*;

public class extract_functions extends GhidraScript {

    private DecompInterface decompiler;

    /**
     * Echappe une chaine pour JSON (guillemets, backslashes, newlines, etc.)
     */
    private static String escapeJson(String s) {
        if (s == null) return "";
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"':  sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                case '\b': sb.append("\\b"); break;
                case '\f': sb.append("\\f"); break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        return sb.toString();
    }

    private void writeFunctionJson(BufferedWriter w, Function func, boolean isLast) throws Exception {
        w.write("    {\n");
        w.write("      \"name\": \"" + escapeJson(func.getName()) + "\",\n");
        w.write("      \"address\": \"" + escapeJson(func.getEntryPoint().toString()) + "\",\n");
        w.write("      \"signature\": \"" + escapeJson(func.getSignature().toString()) + "\",\n");
        w.write("      \"is_thunk\": " + func.isThunk() + ",\n");
        w.write("      \"calling_convention\": \"" + escapeJson(func.getCallingConventionName()) + "\",\n");
        w.write("      \"parameter_count\": " + func.getParameterCount() + ",\n");
        w.write("      \"size\": " + func.getBody().getNumAddresses() + ",\n");

        // Parametres
        w.write("      \"parameters\": [");
        Parameter[] params = func.getParameters();
        for (int i = 0; i < params.length; i++) {
            Parameter p = params[i];
            w.write("\n        {\"name\": \"" + escapeJson(p.getName()) +
                    "\", \"type\": \"" + escapeJson(p.getDataType().toString()) +
                    "\", \"storage\": \"" + escapeJson(p.getVariableStorage().toString()) + "\"}");
            if (i < params.length - 1) w.write(",");
        }
        w.write("],\n");

        // Variables locales
        w.write("      \"local_variables\": [");
        Variable[] locals = func.getLocalVariables();
        for (int i = 0; i < locals.length; i++) {
            Variable v = locals[i];
            w.write("\n        {\"name\": \"" + escapeJson(v.getName()) +
                    "\", \"type\": \"" + escapeJson(v.getDataType().toString()) +
                    "\", \"storage\": \"" + escapeJson(v.getVariableStorage().toString()) + "\"}");
            if (i < locals.length - 1) w.write(",");
        }
        w.write("],\n");

        // Fonctions appelees
        w.write("      \"called_functions\": [");
        Set<Function> calledSet = func.getCalledFunctions(new ConsoleTaskMonitor());
        Function[] called = calledSet.toArray(new Function[0]);
        for (int i = 0; i < called.length; i++) {
            w.write("\n        {\"name\": \"" + escapeJson(called[i].getName()) +
                    "\", \"address\": \"" + escapeJson(called[i].getEntryPoint().toString()) + "\"}");
            if (i < called.length - 1) w.write(",");
        }
        w.write("],\n");

        // Fonctions appelantes
        w.write("      \"calling_functions\": [");
        Set<Function> callingSet = func.getCallingFunctions(new ConsoleTaskMonitor());
        Function[] callers = callingSet.toArray(new Function[0]);
        for (int i = 0; i < callers.length; i++) {
            w.write("\n        {\"name\": \"" + escapeJson(callers[i].getName()) +
                    "\", \"address\": \"" + escapeJson(callers[i].getEntryPoint().toString()) + "\"}");
            if (i < callers.length - 1) w.write(",");
        }
        w.write("],\n");

        // Decompilation
        String decompiledCode = "// Decompilation not available";
        try {
            DecompileResults res = decompiler.decompileFunction(func, 60, new ConsoleTaskMonitor());
            if (res.decompileCompleted()) {
                DecompiledFunction df = res.getDecompiledFunction();
                if (df != null) {
                    decompiledCode = df.getC();
                }
            }
        } catch (Exception e) {
            decompiledCode = "// Decompilation failed: " + e.getMessage();
        }
        w.write("      \"decompiled_code\": \"" + escapeJson(decompiledCode) + "\",\n");

        // Chaines de caracteres
        w.write("      \"strings\": [");
        Listing listing = currentProgram.getListing();
        ReferenceManager refs = currentProgram.getReferenceManager();
        AddressSetView body = func.getBody();

        List<String> stringEntries = new ArrayList<>();
        for (Address addr : body.getAddresses(true)) {
            for (Reference ref : refs.getReferencesFrom(addr)) {
                Address to = ref.getToAddress();
                Data d = listing.getDataAt(to);
                if (d != null && d.hasStringValue()) {
                    stringEntries.add("\n        {\"address\": \"" + escapeJson(to.toString()) +
                            "\", \"value\": \"" + escapeJson(d.getValue().toString()) + "\"}");
                }
            }
        }
        for (int i = 0; i < stringEntries.size(); i++) {
            w.write(stringEntries.get(i));
            if (i < stringEntries.size() - 1) w.write(",");
        }
        w.write("]\n");

        w.write("    }");
        if (!isLast) w.write(",");
        w.write("\n");
    }

    /**
     * Determine le fichier de sortie.
     * Sauvegarde dans extracted_files/ (repertoire frere de bin/).
     * Fallback: a cote du binaire, puis repertoire utilisateur.
     */
    private File getOutputFile() {
        String progName = currentProgram.getName();
        String execPath = currentProgram.getExecutablePath();

        if (execPath != null && !execPath.isEmpty()) {
            File execFile = new File(execPath);
            File binDir = execFile.getParentFile();

            if (binDir != null && binDir.getParentFile() != null) {
                // Creer extracted_files/ comme repertoire frere de bin/
                File extractedDir = new File(binDir.getParentFile(), "extracted_files");
                if (extractedDir.mkdirs() || extractedDir.exists()) {
                    return new File(extractedDir, progName + "_extracted.json");
                }
            }

            // Fallback: a cote du binaire
            if (binDir != null && binDir.exists() && binDir.canWrite()) {
                return new File(binDir, progName + "_extracted.json");
            }
        }

        // Fallback: repertoire utilisateur
        String userHome = System.getProperty("user.home");
        if (userHome != null) {
            File homeDir = new File(userHome);
            if (homeDir.exists()) {
                return new File(homeDir, progName + "_extracted.json");
            }
        }

        // Dernier recours: repertoire courant
        return new File(progName + "_extracted.json");
    }

    @Override
    public void run() throws Exception {

        println("[*] Demarrage de l'extraction pour analyse LLM...");

        decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);

        // Collecter les fonctions non-externes
        FunctionManager fm = currentProgram.getFunctionManager();
        FunctionIterator it = fm.getFunctions(true);
        List<Function> functions = new ArrayList<>();

        while (it.hasNext() && !monitor.isCancelled()) {
            Function func = it.next();
            if (!func.isExternal()) {
                functions.add(func);
            }
        }

        println("[*] Total : " + functions.size() + " fonctions a extraire");

        File outFile = getOutputFile();
        println("[*] Fichier de sortie : " + outFile.getAbsolutePath());

        BufferedWriter w = new BufferedWriter(new FileWriter(outFile));

        // En-tete du JSON
        w.write("{\n");
        w.write("  \"name\": \"" + escapeJson(currentProgram.getName()) + "\",\n");
        w.write("  \"path\": \"" + escapeJson(currentProgram.getExecutablePath()) + "\",\n");
        w.write("  \"format\": \"" + escapeJson(currentProgram.getExecutableFormat()) + "\",\n");
        w.write("  \"language\": \"" + escapeJson(currentProgram.getLanguage().toString()) + "\",\n");
        w.write("  \"compiler\": \"" + escapeJson(currentProgram.getCompiler()) + "\",\n");
        w.write("  \"image_base\": \"" + escapeJson(currentProgram.getImageBase().toString()) + "\",\n");
        w.write("  \"functions\": [\n");

        // Ecrire chaque fonction
        for (int i = 0; i < functions.size(); i++) {
            Function func = functions.get(i);
            boolean isLast = (i == functions.size() - 1);
            writeFunctionJson(w, func, isLast);

            if ((i + 1) % 10 == 0) {
                println("[*] Traitement : " + (i + 1) + "/" + functions.size() + " fonctions...");
            }
        }

        w.write("  ]\n");
        w.write("}\n");
        w.close();

        println("[+] Extraction sauvegardee dans : " + outFile.getAbsolutePath());

        decompiler.dispose();
    }
}
