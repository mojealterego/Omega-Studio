package org.omega.actions;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/** Real on-device version probes. Never substitutes mock or host binaries. */
public final class RuntimeHealth {
    private RuntimeHealth() {}
    private static final String[] COMMANDS={"bash","python","git","llama-cli","node","code-server"};

    public static void assertHealthy(File filesDir) throws IOException {
        Map<String,String> result=probe(filesDir);
        for(Map.Entry<String,String> entry:result.entrySet()) {
            if(!entry.getValue().startsWith("PASS:"))
                throw new IOException("Android ARM64 runtime failed: "+entry.getKey()+" ("+entry.getValue()+")");
        }
    }

    public static Map<String,String> probe(File filesDir) {
        Map<String,String> result=new LinkedHashMap<>();
        for(String name:COMMANDS) result.put(name,version(filesDir,name));
        return result;
    }

    public static String version(File filesDir,String name) {
        if (!Arrays.asList(COMMANDS).contains(name)) return "BLOCKED: unrecognized command";
        File binary=new File(filesDir,"usr/bin/"+name);
        if (!binary.canExecute()) return "MISSING";
        Process process=null;
        try {
            ProcessBuilder builder=new ProcessBuilder(binary.getAbsolutePath(),"--version");
            builder.directory(filesDir);builder.redirectErrorStream(true);
            RuntimeEnvironment.configure(builder.environment(),filesDir);
            process=builder.start();
            // Version output is expected to be small; read concurrently to avoid pipe deadlock.
            final Process current=process;
            final StringBuilder buffer=new StringBuilder();
            Thread reader=new Thread(()->{
                try(InputStream stream=current.getInputStream()){
                    byte[] b=new byte[1024];int n;
                    while((n=stream.read(b))!=-1){
                        synchronized(buffer){if(buffer.length()<4096)buffer.append(new String(b,0,Math.min(n,4096-buffer.length()),StandardCharsets.UTF_8));}
                    }
                }catch(IOException ignored){}
            },"omega-version-probe");reader.setDaemon(true);reader.start();
            if(!process.waitFor(8,TimeUnit.SECONDS)){
                process.destroyForcibly();reader.join(1000);return "TIMEOUT";
            }
            reader.join(1000);
            if(process.exitValue()!=0)return "FAILED: exit="+process.exitValue();
            synchronized(buffer){
                String version=buffer.toString().replace('\n',' ').trim();
                return version.isEmpty()?"FAILED: empty version output":"PASS: "+version;
            }
        }catch(Exception e){return "FAILED: "+e.getClass().getSimpleName();}
        finally{if(process!=null&&process.isAlive())process.destroyForcibly();}
    }
}
