package org.omega.actions.core;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Set;
import java.util.HashSet;
import java.util.Arrays;
import java.util.Collections;

public final class HfUrl {
    private HfUrl() {}
    private static final Set<String> HOSTS=Collections.unmodifiableSet(new HashSet<>(Arrays.asList("huggingface.co","cdn-lfs.huggingface.co",
        "cdn-lfs-us-1.huggingface.co","cdn-lfs-eu-1.huggingface.co",
        "cas-bridge.xethub.hf.co","transfer.xethub.hf.co","cas-server.xethub.hf.co")));
    private static boolean valid(String s){return s!=null && s.matches("[A-Za-z0-9][A-Za-z0-9._-]{0,127}") && !s.equals(".") && !s.equals("..");}
    public static String resolve(String repo,String revision,String filename){
        if(repo==null||filename==null||revision==null)throw new IllegalArgumentException("Missing Hugging Face fields");
        String[] r=repo.split("/",-1),f=filename.split("/",-1);
        if(r.length!=2||!valid(r[0])||!valid(r[1])||!valid(revision)||f.length==0||!filename.toLowerCase().endsWith(".gguf"))
            throw new IllegalArgumentException("Invalid Hugging Face model path");
        StringBuilder b=new StringBuilder("https://huggingface.co/").append(r[0]).append('/').append(r[1]).append("/resolve/").append(revision);
        for(String segment:f){if(!valid(segment))throw new IllegalArgumentException("Invalid filename segment");b.append('/').append(segment);}
        return b.append("?download=true").toString();
    }
    public static boolean trusted(String url){
        try {java.net.URI u=new java.net.URI(url);return "https".equals(u.getScheme())&&HOSTS.contains(u.getHost()==null?"":u.getHost().toLowerCase(java.util.Locale.ROOT))&&
                u.getUserInfo()==null&&u.getRawFragment()==null&&(u.getPort()==-1||u.getPort()==443);}
        catch(Exception e){return false;}
    }
}
