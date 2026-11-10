package org.omega.actions;

import android.content.Context;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/** Verified atomic extraction of OMEGA Python sources into app-private storage. */
public final class RuntimeAssetsInstaller {
    private static final String ZIP="omega-backend.zip";
    private static final String DIGEST="omega-backend.sha256";
    private static final long LIMIT=32L*1024*1024;
    private RuntimeAssetsInstaller(){}

    public static File install(Context c) throws Exception {
        File target=new File(c.getFilesDir(),"omega-backend");
        File marker=new File(target,".sha256");
        String expected;
        try(InputStream in=c.getAssets().open(DIGEST)){
            byte[] bytes=new byte[128];int n=in.read(bytes);
            if(n<64)throw new IllegalArgumentException("Invalid backend SHA-256 manifest");
            expected=new String(bytes,0,n,StandardCharsets.US_ASCII).trim();
        }
        if(!expected.matches("[a-fA-F0-9]{64}"))throw new SecurityException("Invalid backend digest");
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        try(InputStream in=c.getAssets().open(ZIP)){
            byte[] buffer=new byte[65536];int n;
            while((n=in.read(buffer))!=-1)digest.update(buffer,0,n);
        }
        StringBuilder actual=new StringBuilder();
        for(byte b:digest.digest())actual.append(String.format(Locale.ROOT,"%02x",b&255));
        if(!expected.equalsIgnoreCase(actual.toString()))throw new SecurityException("Backend digest mismatch");
        if(target.isDirectory()&&marker.isFile()){
            try(InputStream in=new FileInputStream(marker)){
                byte[] b=new byte[64];if(in.read(b)==64&&expected.equalsIgnoreCase(new String(b,StandardCharsets.US_ASCII))&&
                    new File(target,"omega_actions/__main__.py").isFile())return target;
            }
            throw new SecurityException("Existing backend differs from bundled payload");
        }
        File staging=new File(c.getFilesDir(),"omega-backend-staging");
        if(target.exists()||staging.exists())throw new SecurityException("Backend extraction state requires recovery");
        if(!staging.mkdir())throw new IllegalStateException("Cannot create backend staging directory");
        try(InputStream in=c.getAssets().open(ZIP);ZipInputStream zip=new ZipInputStream(in)){
            ZipEntry e;byte[] b=new byte[65536];long total=0;int count=0;
            while((e=zip.getNextEntry())!=null){
                if(++count>3000)throw new SecurityException("Too many backend entries");
                File out=new File(staging,e.getName());
                if(e.getName().startsWith("/")||e.getName().contains("\\")||
                    !out.getCanonicalPath().startsWith(staging.getCanonicalPath()+File.separator))
                    throw new SecurityException("Backend ZIP path traversal");
                if(e.isDirectory()){
                    if(!out.isDirectory()&&!out.mkdirs())throw new IllegalStateException("Cannot create backend directory");
                }else{
                    File parent=out.getParentFile();
                    if(!parent.isDirectory()&&!parent.mkdirs())throw new IllegalStateException("Cannot create backend parent");
                    try(OutputStream output=new FileOutputStream(out)){
                        int n;while((n=zip.read(b))!=-1){
                            total+=n;if(total>LIMIT)throw new SecurityException("Backend exceeds size limit");
                            output.write(b,0,n);
                        }
                    }
                }
            }
        }catch(Exception e){deleteTree(staging);throw e;}
        if(!new File(staging,"omega_actions/__main__.py").isFile()){
            deleteTree(staging);throw new SecurityException("Backend entrypoint missing");
        }
        try(OutputStream out=new FileOutputStream(new File(staging,".sha256"))){
            out.write(expected.getBytes(StandardCharsets.US_ASCII));
        }
        if(!staging.renameTo(target)){deleteTree(staging);throw new IllegalStateException("Cannot activate backend");}
        return target;
    }
    private static void deleteTree(File root){
        File[] files=root.listFiles();
        if(files!=null)for(File f:files){if(f.isDirectory())deleteTree(f);else f.delete();}
        root.delete();
    }
}
