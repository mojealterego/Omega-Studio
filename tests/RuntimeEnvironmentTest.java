import org.omega.actions.RuntimeEnvironment;
import java.io.File;
import java.nio.file.Files;
import java.util.HashMap;
import java.util.Map;

public final class RuntimeEnvironmentTest {
    public static void main(String[] args) throws Exception {
        File root=Files.createTempDirectory("omega-runtime-env-").toFile();
        Map<String,String> env=new HashMap<>();
        env.put("LD_PRELOAD","/tmp/evil.so");
        env.put("PYTHONHOME","/tmp/fake");
        RuntimeEnvironment.configure(env,root);
        if(env.containsKey("LD_PRELOAD")||env.containsKey("PYTHONHOME"))throw new AssertionError("Inherited environment injection");
        if(!env.get("PREFIX").equals(new File(root,"usr").getAbsolutePath()))throw new AssertionError("Incorrect prefix");
        if(!env.get("PATH").startsWith(new File(root,"usr/bin").getAbsolutePath()))throw new AssertionError("Incorrect PATH");
        if(!new File(root,"home").isDirectory()||!new File(root,"usr/tmp").isDirectory())throw new AssertionError("Runtime directories missing");
        System.out.println("RUNTIME_ENVIRONMENT_PASS");
    }
}
