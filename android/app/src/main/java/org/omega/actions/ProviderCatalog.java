package org.omega.actions;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

/** Bundled, pinned endpoints: no arbitrary URL can be supplied by the WebView. */
public final class ProviderCatalog {
    private final JSONObject catalog;
    public ProviderCatalog(Context context) throws Exception {
        try(InputStream in=context.getAssets().open("providers.json");ByteArrayOutputStream out=new ByteArrayOutputStream()) {
            byte[] b=new byte[4096];int n;
            while((n=in.read(b))!=-1) {
                if(out.size()+n>65536)throw new IllegalArgumentException("Provider registry too large");
                out.write(b,0,n);
            }
            catalog=new JSONObject(out.toString("UTF-8"));
            if(catalog.getInt("version")!=1)throw new IllegalArgumentException("Unsupported provider registry version");
        }
    }
    public JSONObject get(String providerId) throws Exception {
        if(providerId==null||!providerId.matches("[a-z][a-z0-9-]{1,47}"))throw new IllegalArgumentException("Invalid provider ID");
        JSONArray providers=catalog.getJSONArray("providers");
        for(int i=0;i<providers.length();i++){
            JSONObject provider=providers.getJSONObject(i);
            if(providerId.equals(provider.getString("id")))return provider;
        }
        throw new IllegalArgumentException("Unknown provider ID");
    }
    public String publicCatalog(){return catalog.toString();}
}
