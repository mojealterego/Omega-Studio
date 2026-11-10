import org.omega.actions.RuntimeHealth;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.util.Map;

/** Host logic test, not proof that ARM64 ELF binaries run on Android. */
public final class RuntimeHealthTest {
    public static void main(String[] args) throws Exception {
        File root=Files.createTempDirectory("omega-health-host-").toFile();
        File bin=new File(root,"usr/bin");if(!bin.mkdirs())throw new AssertionError();
        for(String name:new String[]{"bash","python","git","llama-cli","node","code-server"}) {
            File script=new File(bin,name);
            Files.writeString(script.toPath(),"#!/bin/sh\necho '"+name+" test version'\n");
            if(!script.setExecutable(true))throw new AssertionError();
        }
        RuntimeHealth.assertHealthy(root);
        Map<String,String> probes=RuntimeHealth.probe(root);
        if(probes.size()!=6)throw new AssertionError("Missing probe");
        for(String value:probes.values())if(!value.startsWith("PASS:"))throw new AssertionError(value);
        if(!new File(bin,"git").delete())throw new AssertionError();
        try {RuntimeHealth.assertHealthy(root);throw new AssertionError("Missing Git was accepted");}
        catch(IOException expected) {if(!expected.getMessage().contains("git"))throw expected;}
        // An executable that exits 0 without a version string is not a valid proof.
        File silent=new File(bin,"git");
        Files.writeString(silent.toPath(),"#!/bin/sh\nexit 0\n");silent.setExecutable(true);
        try {RuntimeHealth.assertHealthy(root);throw new AssertionError("Silent executable was accepted");}
        catch(IOException expected) {if(!expected.getMessage().contains("git"))throw expected;}
        System.out.println("RUNTIME_HEALTH_FAIL_CLOSED_PASS");
    }
}
