package org.omega.actions;

import android.content.Context;
import android.system.Os;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/** Installs an explicitly bundled, package-prefix-compatible Termux bootstrap.
 * No public com.termux binaries may be installed into org.omega.actions prefix.
 */
public final class TermuxBootstrapInstaller {
    private TermuxBootstrapInstaller() {}
    private static final long MAX_UNCOMPRESSED=2L*1024*1024*1024;
    private static final String ZIP="bootstrap-aarch64-v8a.zip";
    private static final String DIGEST="bootstrap-aarch64-v8a.sha256";
    private static final String PREFIX="bootstrap-prefix.txt";
    public static boolean isBundled(Context c){
        try(InputStream a=c.getAssets().open(ZIP);InputStream b=c.getAssets().open(DIGEST);InputStream p=c.getAssets().open(PREFIX)){return a.read()>=0&&b.read()>=0&&p.read()>=0;}
        catch(IOException e){return false;}
    }
    public static void install(Context c)throws Exception{
        File files=c.getFilesDir(),prefix=new File(files,"usr"),staging=new File(files,"usr-staging");
        if(new File(prefix,"bin/bash").canExecute())return;
        if(prefix.exists()||staging.exists())throw new IOException("Existing prefix or staging directory requires manual recovery");
        if(!isBundled(c))throw new IOException("Compatible bootstrap archive not bundled in APK");
        String declaredPrefix;
        try(InputStream in=c.getAssets().open(PREFIX)){
            ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] b=new byte[1024];int n;
            while((n=in.read(b))!=-1){if(out.size()+n>4096)throw new IOException("Bootstrap prefix manifest too large");out.write(b,0,n);}
            declaredPrefix=out.toString("UTF-8").trim();
        }
        String requiredPrefix="/data/data/"+c.getPackageName()+"/files/usr";
        if(!requiredPrefix.equals(declaredPrefix))throw new SecurityException("Bootstrap was built for a different Android package");
        String expected;
        try(InputStream in=c.getAssets().open(DIGEST)){expected=new BufferedReader(new InputStreamReader(in,StandardCharsets.US_ASCII)).readLine().trim().split("\\s+")[0];}
        if(!expected.matches("[a-fA-F0-9]{64}"))throw new IOException("Invalid bootstrap digest manifest");
        MessageDigest sha=MessageDigest.getInstance("SHA-256");
        try(InputStream in=c.getAssets().open(ZIP)){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)sha.update(b,0,n);}
        if(!expected.equalsIgnoreCase(hex(sha.digest())))throw new SecurityException("Bootstrap SHA-256 mismatch");
        if(!staging.mkdirs())throw new IOException("Cannot create staging prefix");
        List<String[]> symlinks=new ArrayList<>();long extracted=0;int entries=0;
        try(InputStream input=c.getAssets().open(ZIP);ZipInputStream zip=new ZipInputStream(input)){
            ZipEntry e;byte[] b=new byte[65536];
            while((e=zip.getNextEntry())!=null){
                if(++entries>200000)throw new IOException("Too many bootstrap entries");
                String name=e.getName();
                if(name.equals("SYMLINKS.txt")){
                    BufferedReader reader=new BufferedReader(new InputStreamReader(zip,StandardCharsets.UTF_8));String line;
                    while((line=reader.readLine())!=null){String[] pair=line.split("←",2);if(pair.length!=2)throw new IOException("Malformed bootstrap symlink");symlinks.add(pair);}
                    continue;
                }
                File target=new File(staging,name);
                if(!target.getCanonicalPath().startsWith(staging.getCanonicalPath()+File.separator))throw new SecurityException("Zip path traversal");
                if(e.isDirectory()){if(!target.isDirectory()&&!target.mkdirs())throw new IOException("Cannot create directory");continue;}
                File parent=target.getParentFile();if(!parent.isDirectory()&&!parent.mkdirs())throw new IOException("Cannot create parent directory");
                try(OutputStream out=new FileOutputStream(target)){
                    int n;while((n=zip.read(b))!=-1){extracted+=n;if(extracted>MAX_UNCOMPRESSED)throw new IOException("Bootstrap size limit exceeded");out.write(b,0,n);}
                }
                if(name.startsWith("bin/")||name.startsWith("libexec/")||name.startsWith("lib/apt/"))Os.chmod(target.getAbsolutePath(),0700);
            }
        }catch(Exception e){deleteTree(staging);throw e;}
        // SYMLINKS.txt is required by the release gate; it may validly contain no entries.
        try{
            for(String[] pair:symlinks){
                String target=pair[0],link=pair[1];
                File dest=new File(staging,link);
                if(!dest.getCanonicalPath().startsWith(staging.getCanonicalPath()+File.separator))throw new SecurityException("Symlink path traversal");
                if(target.startsWith("/")){
                    if(!target.startsWith(prefix.getAbsolutePath()+"/")&&!target.startsWith("/system/"))
                        throw new SecurityException("Symlink target outside trusted prefixes");
                }else{
                    File resolved=new File(dest.getParentFile(),target);
                    if(!resolved.getCanonicalPath().startsWith(staging.getCanonicalPath()+File.separator))
                        throw new SecurityException("Relative symlink escapes bootstrap prefix");
                }
                File parent=dest.getParentFile();if(!parent.exists()&&!parent.mkdirs())throw new IOException("Cannot create symlink parent");
                Os.symlink(target,dest.getAbsolutePath());
            }
            if(!staging.renameTo(prefix))throw new IOException("Unable to finalize bootstrap");
        }catch(Exception e){deleteTree(staging);throw e;}
        if(!new File(prefix,"bin/bash").canExecute())throw new IOException("Bootstrap does not contain executable bash");
    }
    private static String hex(byte[] bytes){StringBuilder s=new StringBuilder();for(byte b:bytes)s.append(String.format(Locale.ROOT,"%02x",b&255));return s.toString();}
    private static void deleteTree(File root){File[] list=root.listFiles();if(list!=null)for(File f:list){if(f.isDirectory()&&!java.nio.file.Files.isSymbolicLink(f.toPath()))deleteTree(f);else f.delete();}root.delete();}
}
