package org.omega.actions;

import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import org.json.JSONArray;
import org.json.JSONObject;
import org.omega.actions.core.GgufMetadataReader;
import org.omega.actions.core.HfUrl;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;

/** Scoped asynchronous native operations. All callbacks return JSON strings, never raw JavaScript. */
public final class NativeBridge {
    private final MainActivity activity;
    private final WebView web;
    private final SecureVault vault;
    private final ExecutorService workers=Executors.newFixedThreadPool(3);
    private static final int MAX_COMMAND=2048;
    private static final long MAX_MODEL=50L*1024*1024*1024;
    public NativeBridge(MainActivity activity,WebView web){this.activity=activity;this.web=web;this.vault=new SecureVault(activity);}
    public void shutdown(){workers.shutdownNow();}
    private static String error(Exception e){try{return new JSONObject().put("error",e.getClass().getSimpleName()+": "+String.valueOf(e.getMessage())).toString();}catch(Exception ignored){return "{\"error\":\"Native operation failed\"}";}}
    public void callback(String id,String json){
        if(id==null||!id.matches("[a-zA-Z0-9_-]{1,48}"))return;
        activity.runOnUiThread(()->web.evaluateJavascript("window.omegaNativeCallback&&window.omegaNativeCallback("+
                JSONObject.quote(id)+","+JSONObject.quote(json)+")",null));
    }
    private void task(String id,Callable<String> op){workers.execute(()->{try{callback(id,op.call());}catch(Exception e){callback(id,error(e));}});}
    private File prefix(){return new File(activity.getFilesDir(),"usr");}
    private File bin(String name){return new File(prefix(),"bin/"+name);}
    @JavascriptInterface public String providerCatalog(){
        try{return new ProviderCatalog(activity).publicCatalog();}
        catch(Exception e){return "{\"error\":\"Provider catalog unavailable\"}";}
    }
    @JavascriptInterface public String capabilities(){
        JSONObject out=new JSONObject();
        try{out.put("android_shell",true).put("termux_bootstrap",bin("bash").canExecute())
                .put("python",bin("python").canExecute()).put("git",bin("git").canExecute())
                .put("llama_cli",bin("llama-cli").canExecute()).put("keystore",true)
                .put("hf_download",true).put("gguf_import",true).put("bootstrap_bundled",TermuxBootstrapInstaller.isBundled(activity));
        }catch(Exception ignored){}
        return out.toString();
    }
    private String execute(String command)throws Exception{
        if(command==null||command.trim().isEmpty()||command.length()>MAX_COMMAND)throw new IllegalArgumentException("Command exceeds 2048 chars");
        if(!bin("bash").canExecute())throw new IOException("Brak zgodnego bootstrap Termux; nie uruchomiono polecenia");
        String shell=bin("bash").getAbsolutePath();
        ProcessBuilder builder=new ProcessBuilder(shell,"-c",command);
        builder.directory(activity.getFilesDir());builder.redirectErrorStream(true);
        if(shell.equals(bin("bash").getAbsolutePath())){
            Map<String,String> env=builder.environment();env.put("PREFIX",prefix().getAbsolutePath());
            env.put("HOME",new File(activity.getFilesDir(),"home").getAbsolutePath());
            env.put("PATH",new File(prefix(),"bin").getAbsolutePath()+":/system/bin");
        }
        Process p=builder.start();
        StringBuilder output=new StringBuilder();
        Thread drainer=new Thread(()->{
            byte[] buffer=new byte[4096];int n;
            try(InputStream in=p.getInputStream()){
                while((n=in.read(buffer))!=-1){
                    synchronized(output){if(output.length()<65536)output.append(new String(buffer,0,Math.min(n,65536-output.length()),StandardCharsets.UTF_8));}
                }
            }catch(IOException ignored){}
        },"omega-output-drain");
        drainer.setDaemon(true);drainer.start();
        if(!p.waitFor(30,TimeUnit.SECONDS)){p.destroyForcibly();drainer.join(1000);throw new TimeoutException("Shell command exceeded 30 seconds");}
        drainer.join(5000);
        return new JSONObject().put("exit_code",p.exitValue()).put("output",output.toString()).toString();
    }
    @JavascriptInterface public void runAsync(String command,String id){task(id,()->execute(command));}
    @JavascriptInterface public String run(String command){
        try{return new JSONObject(execute(command)).optString("output");}
        catch(Exception e){return "ERROR: "+e.getClass().getSimpleName();}
    }
    @JavascriptInterface public void saveSecret(String name,String value,String id){task(id,()->{vault.put(name,value);return new JSONObject().put("saved",true).toString();});}
    @JavascriptInterface public void secretStatus(String name,String id){task(id,()->new JSONObject().put("saved",vault.has(name)).toString());}
    @JavascriptInterface public void deleteSecret(String name,String id){task(id,()->{vault.remove(name);return new JSONObject().put("deleted",true).toString();});}
    @JavascriptInterface public void chatProvider(String providerId,String model,String message,boolean confirmCost,String id){
        task(id,()->{
            JSONObject provider=new ProviderCatalog(activity).get(providerId);
            if(!provider.getBoolean("remote"))throw new IOException("Lokalny model uruchom przez GGUF/llama.cpp");
            if(!confirmCost)throw new SecurityException("Zewnętrzne API wymaga zgody na koszt");
            if(model==null||!model.matches("[A-Za-z0-9][A-Za-z0-9._:/+\\-]{0,127}"))
                throw new IllegalArgumentException("Invalid model name");
            if(message==null||message.isEmpty()||message.length()>16000)
                throw new IllegalArgumentException("Message must have 1..16000 characters");
            String secretName=provider.getString("secret_name");
            String secret=vault.get(secretName);
            if(secret==null||secret.isEmpty())throw new SecurityException("Brak klucza API dla dostawcy");
            String style=provider.getString("style");
            String url=provider.getString("endpoint");
            JSONObject payload=new JSONObject();
            if(style.equals("gemini")){
                if(!model.matches("[A-Za-z0-9][A-Za-z0-9._-]{0,127}"))throw new IllegalArgumentException("Invalid Gemini model name");
                url+="/"+model+":generateContent";
                payload.put("contents",new JSONArray().put(new JSONObject().put("role","user")
                    .put("parts",new JSONArray().put(new JSONObject().put("text",message)))));
                payload.put("generationConfig",new JSONObject().put("maxOutputTokens",512));
            }else{
                payload.put("model",model);
                payload.put("messages",new JSONArray().put(new JSONObject().put("role","user").put("content",message)));
                if(style.equals("anthropic"))payload.put("max_tokens",512);
                else {payload.put("max_tokens",512);payload.put("stream",false);}
            }
            java.net.URI endpoint=new java.net.URI(url);
            if(!"https".equals(endpoint.getScheme())||endpoint.getUserInfo()!=null||
                endpoint.getPort()!=-1&&endpoint.getPort()!=443)throw new SecurityException("Invalid provider endpoint");
            HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection();
            c.setRequestMethod("POST");c.setInstanceFollowRedirects(false);
            c.setConnectTimeout(10000);c.setReadTimeout(60000);c.setDoOutput(true);
            c.setRequestProperty("Content-Type","application/json");
            c.setRequestProperty("Accept","application/json");
            if(style.equals("anthropic")){
                c.setRequestProperty("x-api-key",secret);
                c.setRequestProperty("anthropic-version","2023-06-01");
            }else if(style.equals("gemini"))c.setRequestProperty("x-goog-api-key",secret);
            else c.setRequestProperty("Authorization","Bearer "+secret);
            try{
                try(OutputStream out=c.getOutputStream()){out.write(payload.toString().getBytes(StandardCharsets.UTF_8));}
                int status=c.getResponseCode();
                if(status!=200)throw new IOException("Provider HTTP "+status);
                JSONObject response=new JSONObject(readLimited(c.getInputStream(),1024*1024));
                String answer;
                if(style.equals("anthropic")){
                    StringBuilder b=new StringBuilder();JSONArray content=response.getJSONArray("content");
                    for(int i=0;i<content.length();i++){
                        JSONObject part=content.getJSONObject(i);
                        if("text".equals(part.optString("type")))b.append(part.optString("text"));
                    }
                    answer=b.toString();
                }else if(style.equals("gemini")){
                    JSONArray parts=response.getJSONArray("candidates").getJSONObject(0).getJSONObject("content").getJSONArray("parts");
                    StringBuilder b=new StringBuilder();
                    for(int i=0;i<parts.length();i++)b.append(parts.getJSONObject(i).optString("text"));
                    answer=b.toString();
                }else answer=response.getJSONArray("choices").getJSONObject(0).getJSONObject("message").getString("content");
                if(answer.isEmpty())throw new IOException("Empty provider response");
                return new JSONObject().put("provider",providerId).put("model",model).put("text",answer).toString();
            }finally{c.disconnect();}
        });
    }
    @JavascriptInterface public void pickModel(String id){activity.pickModel(id);}
    @JavascriptInterface public void installBootstrap(String id){task(id,()->{
        TermuxBootstrapInstaller.install(activity);
        File backend=RuntimeAssetsInstaller.install(activity);
        return new JSONObject().put("installed",true).put("backend",backend.getAbsolutePath()).toString();
    });}
    @JavascriptInterface public void runWorkflow(String name,boolean confirmUnsafe,String id){task(id,()->{
        if(!confirmUnsafe)throw new SecurityException("Wykonywanie kodu CI wymaga jawnej zgody");
        if(name==null||!name.matches("[A-Za-z0-9._-]{1,128}\\.ya?ml"))
            throw new IllegalArgumentException("Niepoprawna nazwa workflow YAML");
        File workflow=new File(new File(activity.getFilesDir(),"workspace"),name);
        if(!workflow.isFile()||workflow.length()>1024*1024)throw new IOException("Workflow nie istnieje lub przekracza 1 MiB");
        File python=bin("python"),git=bin("git");
        if(!python.canExecute()||!git.canExecute())throw new IOException("Brak binariów Python/Git w runtime");
        File backend=RuntimeAssetsInstaller.install(activity);
        File workspace=workflow.getParentFile();
        List<String> args=Arrays.asList(python.getAbsolutePath(),"-m","omega_actions","run",workflow.getAbsolutePath(),
            "--repo",workspace.getAbsolutePath(),"--executor","native","--unsafe-native");
        ProcessBuilder pb=new ProcessBuilder(args);pb.directory(workspace);pb.redirectErrorStream(true);
        Map<String,String> env=pb.environment();
        env.put("PREFIX",prefix().getAbsolutePath());
        env.put("HOME",new File(activity.getFilesDir(),"home").getAbsolutePath());
        env.put("PYTHONPATH",backend.getAbsolutePath());
        env.put("PATH",new File(prefix(),"bin").getAbsolutePath()+":/system/bin");
        env.put("OMEGA_ACTIONS_HOME",new File(activity.getFilesDir(),"omega-state").getAbsolutePath());
        Process process=pb.start();StringBuilder output=new StringBuilder();
        Thread drain=new Thread(()->{try(InputStream in=process.getInputStream()){
            byte[] b=new byte[4096];int n;
            while((n=in.read(b))!=-1){synchronized(output){
                if(output.length()<1024*1024)output.append(new String(b,0,Math.min(n,1024*1024-output.length()),StandardCharsets.UTF_8));
            }}
        }catch(IOException ignored){}});drain.setDaemon(true);drain.start();
        if(!process.waitFor(1800,TimeUnit.SECONDS)){
            process.destroyForcibly();drain.join(1000);throw new TimeoutException("CI exceeded 30 minutes");
        }
        drain.join(5000);
        return new JSONObject().put("exit_code",process.exitValue()).put("output",output.toString()).toString();
    });}
    public void importModel(Uri uri,String id){task(id,()->{
        String name="imported.gguf";
        try(Cursor cursor=activity.getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){
            if(cursor!=null&&cursor.moveToFirst())name=cursor.getString(0);
        }
        if(name==null||!name.toLowerCase(Locale.ROOT).endsWith(".gguf"))throw new IOException("Only GGUF models can be imported");
        name=name.replaceAll("[^a-zA-Z0-9._-]","_");
        File dir=new File(activity.getFilesDir(),"models");if(!dir.exists()&&!dir.mkdirs())throw new IOException("Unable to create model directory");
        File dest=new File(dir,name),partial=new File(dir,name+".part");
        if(dest.exists())throw new IOException("Model already exists");
        MessageDigest sha=MessageDigest.getInstance("SHA-256");long total=0;
        try(InputStream in=activity.getContentResolver().openInputStream(uri);OutputStream out=new FileOutputStream(partial)){
            if(in==null)throw new IOException("Model source unavailable");
            byte[] b=new byte[1024*1024];int n;
            while((n=in.read(b))!=-1){total+=n;if(total>MAX_MODEL)throw new IOException("Model exceeds 50 GiB limit");out.write(b,0,n);sha.update(b,0,n);}
        }catch(Exception e){partial.delete();throw e;}
        try{GgufMetadataReader.inspect(partial);}catch(Exception e){partial.delete();throw e;}
        if(!partial.renameTo(dest)){partial.delete();throw new IOException("Cannot finish model import");}
        return new JSONObject().put("name",dest.getName()).put("bytes",total).put("sha256",hex(sha.digest())).toString();
    });}
    @JavascriptInterface public void listModels(String id){task(id,()->{
        File dir=new File(activity.getFilesDir(),"models");JSONArray arr=new JSONArray();File[] files=dir.listFiles();
        if(files!=null)for(File f:files)if(f.isFile()&&f.getName().toLowerCase(Locale.ROOT).endsWith(".gguf"))arr.put(new JSONObject().put("name",f.getName()).put("bytes",f.length()));
        return new JSONObject().put("models",arr).toString();
    });}
    @JavascriptInterface public void modelInfo(String name,String id){task(id,()->{
        if(name==null||!name.matches("[A-Za-z0-9._-]+\\.gguf"))throw new IllegalArgumentException("Invalid model name");
        return new JSONObject(GgufMetadataReader.inspect(new File(new File(activity.getFilesDir(),"models"),name))).toString();
    });}
    @JavascriptInterface public void saveFile(String name,String content,String id){task(id,()->{
        if(name==null||!name.matches("[A-Za-z0-9._-]{1,128}")||name.equals(".")||name.equals(".."))
            throw new IllegalArgumentException("Invalid filename");
        if(content==null||content.length()>2*1024*1024)throw new IllegalArgumentException("File exceeds 2 MB limit");
        File dir=new File(activity.getFilesDir(),"workspace");if(!dir.exists()&&!dir.mkdirs())throw new IOException("Workspace unavailable");
        File dest=new File(dir,name),tmp=new File(dir,name+".tmp");
        try(OutputStream out=new FileOutputStream(tmp)){out.write(content.getBytes(StandardCharsets.UTF_8));}
        if(dest.exists()&&!dest.delete())throw new IOException("Cannot replace workspace file");
        if(!tmp.renameTo(dest))throw new IOException("Cannot save workspace file");
        return new JSONObject().put("name",name).put("saved",true).toString();
    });}
    @JavascriptInterface public void readFile(String name,String id){task(id,()->{
        if(name==null||!name.matches("[A-Za-z0-9._-]{1,128}")||name.equals(".")||name.equals(".."))
            throw new IllegalArgumentException("Invalid filename");
        File f=new File(new File(activity.getFilesDir(),"workspace"),name);
        if(!f.isFile()||f.length()>2*1024*1024)throw new IOException("File not found or too large");
        return new JSONObject().put("name",name).put("text",readLimited(new FileInputStream(f),2*1024*1024)).toString();
    });}
    @JavascriptInterface public void listWorkspace(String id){task(id,()->{
        File[] files=new File(activity.getFilesDir(),"workspace").listFiles();JSONArray a=new JSONArray();
        if(files!=null)for(File f:files)if(f.isFile()&&!f.getName().endsWith(".tmp"))a.put(f.getName());
        return new JSONObject().put("files",a).toString();
    });}
    @JavascriptInterface public void inferModel(String name,String prompt,String configJson,String id){task(id,()->{
        if(name==null||!name.matches("[A-Za-z0-9._-]+\\.gguf"))throw new IllegalArgumentException("Invalid GGUF model name");
        if(prompt==null||prompt.isEmpty()||prompt.length()>32768)throw new IllegalArgumentException("Prompt must have 1..32768 characters");
        File model=new File(new File(activity.getFilesDir(),"models"),name);
        File llama=bin("llama-cli");
        if(!model.isFile()||!llama.canExecute())throw new IOException("Model or llama-cli executable unavailable");
        JSONObject cfg=new JSONObject(configJson);
        int context=cfg.optInt("context",4096),threads=cfg.optInt("threads",4),batch=cfg.optInt("batch",256),gpu=cfg.optInt("gpu_layers",0);
        int topK=cfg.optInt("top_k",40),seed=cfg.optInt("seed",-1),tokens=cfg.optInt("max_tokens",512);
        double temp=cfg.optDouble("temperature",0.7),topP=cfg.optDouble("top_p",0.95),minP=cfg.optDouble("min_p",0.05),repeat=cfg.optDouble("repeat_penalty",1.1);
        if(context<128||context>131072||threads<1||threads>128||batch<1||batch>8192||gpu<0||gpu>512||topK<0||topK>100000||tokens<1||tokens>131072||seed< -1||
           !Double.isFinite(temp)||temp<0||temp>5||!Double.isFinite(topP)||topP<0||topP>1||!Double.isFinite(minP)||minP<0||minP>1||!Double.isFinite(repeat)||repeat<0.1||repeat>10)
            throw new IllegalArgumentException("Invalid inference parameters");
        List<String> args=Arrays.asList(llama.getAbsolutePath(),"-m",model.getAbsolutePath(),"-c",String.valueOf(context),
            "-t",String.valueOf(threads),"-b",String.valueOf(batch),"-ngl",String.valueOf(gpu),
            "--temp",String.valueOf(temp),"--top-k",String.valueOf(topK),"--top-p",String.valueOf(topP),
            "--min-p",String.valueOf(minP),"--repeat-penalty",String.valueOf(repeat),"-s",String.valueOf(seed),
            "-n",String.valueOf(tokens),"-p",prompt);
        ProcessBuilder builder=new ProcessBuilder(args);builder.directory(activity.getFilesDir());builder.redirectErrorStream(true);
        Map<String,String> env=builder.environment();env.put("PREFIX",prefix().getAbsolutePath());env.put("HOME",new File(activity.getFilesDir(),"home").getAbsolutePath());
        env.put("PATH",new File(prefix(),"bin").getAbsolutePath()+":/system/bin");
        Process process=builder.start();StringBuilder output=new StringBuilder();
        Thread drain=new Thread(()->{try(InputStream in=process.getInputStream()){
            byte[] b=new byte[4096];int n;while((n=in.read(b))!=-1){if(output.length()<1024*1024)output.append(new String(b,0,Math.min(n,1024*1024-output.length()),StandardCharsets.UTF_8));}
        }catch(IOException ignored){}});drain.setDaemon(true);drain.start();
        if(!process.waitFor(600,TimeUnit.SECONDS)){process.destroyForcibly();drain.join(1000);throw new TimeoutException("Model inference exceeded 10 minutes");}
        drain.join(5000);
        return new JSONObject().put("exit_code",process.exitValue()).put("output",output.toString()).toString();
    });}
    @JavascriptInterface public void githubGet(String path,String id){task(id,()->{
        if(path==null||path.contains("/../")||path.endsWith("/..")||!path.matches("/(user|repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(/contents(/[A-Za-z0-9_./-]+)?)?"))
            throw new IllegalArgumentException("Only read-only GitHub endpoints are allowed");
        String token=vault.get("GITHUB_TOKEN");if(token==null)throw new IllegalStateException("GitHub token missing");
        HttpURLConnection c=(HttpURLConnection)new URL("https://api.github.com"+path).openConnection();
        c.setRequestMethod("GET");c.setInstanceFollowRedirects(false);c.setConnectTimeout(15000);c.setReadTimeout(30000);
        c.setRequestProperty("Authorization","Bearer "+token);c.setRequestProperty("Accept","application/vnd.github+json");
        try{int status=c.getResponseCode();if(status!=200)throw new IOException("GitHub HTTP "+status);
            return readLimited(c.getInputStream(),1024*1024);
        }finally{c.disconnect();}
    });}
    @JavascriptInterface public void downloadHf(String repo,String revision,String filename,String expectedSha,String id){task(id,()->{
        String url=HfUrl.resolve(repo,revision,filename);
        if(expectedSha!=null&&!expectedSha.isEmpty()&&!expectedSha.matches("[0-9a-fA-F]{64}"))throw new IllegalArgumentException("Invalid SHA-256 digest");
        String name=filename.substring(filename.lastIndexOf('/')+1);
        File dir=new File(activity.getFilesDir(),"models");if(!dir.exists()&&!dir.mkdirs())throw new IOException("Model directory unavailable");
        File dest=new File(dir,name),partial=new File(dir,name+".part");
        if(dest.exists())throw new IOException("Model already exists");
        long offset=partial.isFile()?partial.length():0;
        if(offset>MAX_MODEL)throw new IOException("Partial model too large");
        String token=vault.get("HF_TOKEN");
        for(int redirect=0;redirect<6;redirect++){
            if(!HfUrl.trusted(url))throw new SecurityException("Untrusted Hugging Face redirect");
            HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection();
            c.setInstanceFollowRedirects(false);c.setConnectTimeout(15000);c.setReadTimeout(120000);
            if(url.startsWith("https://huggingface.co/")&&token!=null)c.setRequestProperty("Authorization","Bearer "+token);
            if(offset>0)c.setRequestProperty("Range","bytes="+offset+"-");
            try{int status=c.getResponseCode();
                if(status==301||status==302||status==303||status==307||status==308){
                    String location=c.getHeaderField("Location");if(location==null)throw new IOException("Redirect missing Location");
                    url=new URL(new URL(url),location).toString();continue;
                }
                if(status!=200&&status!=206)throw new IOException("Hugging Face HTTP "+status);
                if(offset>0&&(status!=206||!String.valueOf(c.getHeaderField("Content-Range")).startsWith("bytes "+offset+"-")))
                    throw new IOException("Server rejected resume range");
                long total=offset;
                try(InputStream in=c.getInputStream();OutputStream out=new FileOutputStream(partial,offset>0)){
                    byte[] b=new byte[1024*1024];int n;
                    while((n=in.read(b))!=-1){total+=n;if(total>MAX_MODEL)throw new IOException("Model exceeds 50 GiB");out.write(b,0,n);}
                }
                GgufMetadataReader.inspect(partial);
                MessageDigest sha=MessageDigest.getInstance("SHA-256");
                try(InputStream in=new FileInputStream(partial)){byte[] b=new byte[1024*1024];int n;while((n=in.read(b))!=-1)sha.update(b,0,n);}
                String actual=hex(sha.digest());
                if(expectedSha!=null&&!expectedSha.isEmpty()&&!actual.equalsIgnoreCase(expectedSha))throw new SecurityException("Model SHA-256 mismatch");
                if(!partial.renameTo(dest))throw new IOException("Unable to finalize model");
                return new JSONObject().put("name",name).put("bytes",total).put("sha256",actual).toString();
            }finally{c.disconnect();}
        }
        throw new IOException("Too many download redirects");
    });}
    private static String readLimited(InputStream in,int limit)throws IOException{
        try(InputStream stream=in;ByteArrayOutputStream out=new ByteArrayOutputStream()){
            byte[] b=new byte[8192];int n,total=0;
            while((n=stream.read(b))!=-1){total+=n;if(total>limit)throw new IOException("Response exceeds limit");out.write(b,0,n);}
            return out.toString("UTF-8");
        }
    }
    private static String hex(byte[] b){StringBuilder s=new StringBuilder();for(byte x:b)s.append(String.format(Locale.ROOT,"%02x",x&255));return s.toString();}
}
