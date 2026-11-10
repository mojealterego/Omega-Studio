package org.omega.actions;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.URL;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.Base64;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/** Loopback-only authenticated code-server supervisor; no shell or remote bind. */
public final class CodeServerManager {
    private static final CodeServerManager INSTANCE = new CodeServerManager();
    private Process process;
    private String password;
    private int port;
    private Thread outputDrainer;

    private CodeServerManager() {}
    public static CodeServerManager get() {return INSTANCE;}

    public synchronized Session start(File filesDir) throws Exception {
        if (process != null && process.isAlive() && health(port)) return new Session(url(port),password);
        stop();
        File prefix=new File(filesDir,"usr");
        File editor=new File(prefix,"bin/code-server");
        File node=new File(prefix,"bin/node");
        if (!editor.canExecute() || !node.canExecute())
            throw new IOException("code-server lub Node ARM64 nie jest zainstalowany w aplikacji");
        File userData=new File(filesDir,"vscode/user-data");
        File extensions=new File(filesDir,"vscode/extensions");
        if ((!userData.isDirectory()&&!userData.mkdirs()) || (!extensions.isDirectory()&&!extensions.mkdirs()))
            throw new IOException("Cannot initialize VS Code directories");
        try(ServerSocket listener=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"))) {
            port=listener.getLocalPort();
        }
        byte[] secret=new byte[32];new SecureRandom().nextBytes(secret);
        password=Base64.getUrlEncoder().withoutPadding().encodeToString(secret);
        ProcessBuilder builder=new ProcessBuilder(Arrays.asList(editor.getAbsolutePath(),
            "--bind-addr","127.0.0.1:"+port,"--auth","password","--disable-telemetry",
            "--disable-update-check","--user-data-dir",userData.getAbsolutePath(),
            "--extensions-dir",extensions.getAbsolutePath()));
        builder.directory(filesDir);builder.redirectErrorStream(true);
        Map<String,String> env=builder.environment();RuntimeEnvironment.configure(env,filesDir);
        env.put("PASSWORD",password);
        try {
            process=builder.start();
            final Process current=process;
            outputDrainer=new Thread(()->drain(current.getInputStream()),"omega-code-server-logs");
            outputDrainer.setDaemon(true);outputDrainer.start();
            long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(20);
            while(System.nanoTime()<deadline) {
                if (!process.isAlive()) throw new IOException("code-server exited with code "+process.exitValue());
                if (health(port)) return new Session(url(port),password);
                Thread.sleep(200);
            }
            throw new IOException("code-server did not become ready within 20 seconds");
        } catch(Exception failure) {
            stop();throw failure;
        }
    }

    private static void drain(InputStream in) {
        try(InputStream stream=in) {
            byte[] buffer=new byte[8192];
            while(stream.read(buffer)!=-1) { /* discard logs: never expose credentials */ }
        } catch(IOException ignored) { }
    }

    private static boolean health(int port) {
        if (port<1 || port>65535) return false;
        HttpURLConnection connection=null;
        try {
            connection=(HttpURLConnection)new URL(url(port)+"healthz").openConnection();
            connection.setConnectTimeout(400);connection.setReadTimeout(400);
            connection.setInstanceFollowRedirects(false);
            return connection.getResponseCode()==200;
        } catch(IOException ignored) {return false;}
        finally {if(connection!=null)connection.disconnect();}
    }
    private static String url(int port) {return "http://127.0.0.1:"+port+"/";}

    public synchronized boolean isRunning() {return process!=null && process.isAlive();}
    public synchronized String activeUrl() {return isRunning()?url(port):null;}
    public synchronized void stop() {
        if(process!=null) {
            process.destroy();
            try {if(!process.waitFor(3,TimeUnit.SECONDS))process.destroyForcibly();}
            catch(InterruptedException e) {Thread.currentThread().interrupt();process.destroyForcibly();}
        }
        process=null;password=null;port=0;
    }

    public static final class Session {
        public final String url;
        public final String password;
        private Session(String url,String password){this.url=url;this.password=password;}
    }
}
