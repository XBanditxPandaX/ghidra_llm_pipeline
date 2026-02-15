// Script Ghidra - Extraction des fonctions pour analyse LLM
// @category LLM_Pipeline
// @author Memoire M2

import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.util.task.ConsoleTaskMonitor;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;

import java.io.FileWriter;
import java.io.File;
import java.util.*;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

public class extract_functions extends GhidraScript {

    private DecompInterface decompiler;

    private Map<String, Object> getFunctionInfo(Function func) {

        Map<String, Object> info = new LinkedHashMap<>();

        info.put("name", func.getName());
        info.put("address", func.getEntryPoint().toString());
        info.put("signature", func.getSignature().toString());
        info.put("is_thunk", func.isThunk());
        info.put("calling_convention", func.getCallingConventionName());
        info.put("parameter_count", func.getParameterCount());
        info.put("size", func.getBody().getNumAddresses());

        List<Map<String, Object>> parameters = new ArrayList<>();
        for (Parameter p : func.getParameters()) {
            Map<String, Object> param = new LinkedHashMap<>();
            param.put("name", p.getName());
            param.put("type", p.getDataType().toString());
            param.put("storage", p.getVariableStorage().toString());
            parameters.add(param);
        }
        info.put("parameters", parameters);

        List<Map<String, Object>> locals = new ArrayList<>();
        for (Variable v : func.getLocalVariables()) {
            Map<String, Object> local = new LinkedHashMap<>();
            local.put("name", v.getName());
            local.put("type", v.getDataType().toString());
            local.put("storage", v.getVariableStorage().toString());
            locals.add(local);
        }
        info.put("local_variables", locals);

        List<Map<String, Object>> called = new ArrayList<>();
        for (Function f : func.getCalledFunctions(new ConsoleTaskMonitor())) {
            Map<String, Object> cf = new LinkedHashMap<>();
            cf.put("name", f.getName());
            cf.put("address", f.getEntryPoint().toString());
            called.add(cf);
        }
        info.put("called_functions", called);

        List<Map<String, Object>> callers = new ArrayList<>();
        for (Function f : func.getCallingFunctions(new ConsoleTaskMonitor())) {
            Map<String, Object> cf = new LinkedHashMap<>();
            cf.put("name", f.getName());
            cf.put("address", f.getEntryPoint().toString());
            callers.add(cf);
        }
        info.put("calling_functions", callers);

        // Décompilation
        try {
            DecompileResults res = decompiler.decompileFunction(func, 60, new ConsoleTaskMonitor());
            if (res.decompileCompleted()) {
                DecompiledFunction df = res.getDecompiledFunction();
                if (df != null) {
                    info.put("decompiled_code", df.getC());
                }
            }
        } catch (Exception e) {
            info.put("decompiled_code", "// Decompilation failed: " + e.getMessage());
        }

        // Chaînes de caractères
        List<Map<String, Object>> strings = new ArrayList<>();
        Listing listing = currentProgram.getListing();
        ReferenceManager refs = currentProgram.getReferenceManager();

        AddressSetView body = func.getBody();
        for (Address addr : body.getAddresses(true)) {
            for (Reference ref : refs.getReferencesFrom(addr)) {
                Address to = ref.getToAddress();
                Data d = listing.getDataAt(to);
                if (d != null && d.hasStringValue()) {
                    Map<String, Object> s = new LinkedHashMap<>();
                    s.put("address", to.toString());
                    s.put("value", d.getValue().toString());
                    strings.add(s);
                }
            }
        }
        info.put("strings", strings);

        return info;
    }

    @Override
    public void run() throws Exception {

        println("[*] Démarrage de l'extraction pour analyse LLM...");

        decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);

        Map<String, Object> binary = new LinkedHashMap<>();
        binary.put("name", currentProgram.getName());
        binary.put("path", currentProgram.getExecutablePath());
        binary.put("format", currentProgram.getExecutableFormat());
        binary.put("language", currentProgram.getLanguage().toString());
        binary.put("compiler", currentProgram.getCompiler());
        binary.put("image_base", currentProgram.getImageBase().toString());

        List<Map<String, Object>> functionsOut = new ArrayList<>();

        FunctionManager fm = currentProgram.getFunctionManager();
        FunctionIterator it = fm.getFunctions(true);

        int count = 0;
        while (it.hasNext() && !monitor.isCancelled()) {
            Function func = it.next();

            if (func.isExternal()) {
                continue;
            }

            functionsOut.add(getFunctionInfo(func));
            count++;

            if (count % 10 == 0) {
                println("[*] Traitement : " + count + " fonctions...");
            }
        }

        binary.put("functions", functionsOut);

        println("[*] Total : " + count + " fonctions extraites");

        File outDir = new File(currentProgram.getExecutablePath()).getParentFile();
        File outFile = new File(outDir, currentProgram.getName() + "_extracted.json");

        Gson gson = new GsonBuilder().setPrettyPrinting().create();
        FileWriter writer = new FileWriter(outFile);
        gson.toJson(binary, writer);
        writer.close();

        println("[+] Extraction sauvegardée dans : " + outFile.getAbsolutePath());

        decompiler.dispose();
    }
}