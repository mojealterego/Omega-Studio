import org.omega.actions.core.GgufMetadataReader;
import org.omega.actions.core.HfUrl;
import java.io.*;
import java.nio.file.*;
public class NativeCoreTest {
  public static void main(String[] args)throws Exception{
    String u=HfUrl.resolve("org/model","main","model.Q4_K_M.gguf");
    if(!u.equals("https://huggingface.co/org/model/resolve/main/model.Q4_K_M.gguf?download=true"))throw new AssertionError(u);
    for(String bad:new String[]{"../model.gguf","x/../m.gguf"}){
      try{HfUrl.resolve("org/model","main",bad);throw new AssertionError("accepted "+bad);}catch(IllegalArgumentException expected){}
    }
    if(HfUrl.trusted("https://127.0.0.1/file")||HfUrl.trusted("http://huggingface.co/file"))throw new AssertionError("untrusted redirect accepted");
    Path p=Files.createTempFile("omega-gguf",".gguf");
    try(DataOutputStream o=new DataOutputStream(Files.newOutputStream(p))){o.writeBytes("GGUF");o.write(new byte[]{3,0,0,0});o.write(new byte[16]);}
    if(!GgufMetadataReader.inspect(p.toFile()).get("version").equals(3L))throw new AssertionError("bad version");
    Files.write(p,new byte[]{1,2,3});
    try{GgufMetadataReader.inspect(p.toFile());throw new AssertionError("accepted invalid GGUF");}catch(IOException expected){}
    Files.delete(p);
    System.out.println("NATIVE_CORE_TEST_PASS");
  }
}
