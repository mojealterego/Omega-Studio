package org.omega.actions;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.SecureRandom;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** AndroidKeyStore AES-256-GCM. Secret values are never returned to JavaScript. */
public final class SecureVault {
    private static final String ALIAS="omega.studio.keys.v4";
    private final SharedPreferences prefs;
    public SecureVault(Context context){prefs=context.getSharedPreferences("omega_secure",Context.MODE_PRIVATE);}
    private static void validate(String name){
        if(name==null||(!name.equals("GITHUB_TOKEN")&&!name.equals("HF_TOKEN")&&
            !name.matches("[A-Z][A-Z0-9_]{2,55}_API_KEY")))
            throw new IllegalArgumentException("Invalid secret name");
    }
    private SecretKey key()throws Exception{
        KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);
        if(!store.containsAlias(ALIAS)){
            KeyGenerator gen=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
            gen.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256).setRandomizedEncryptionRequired(true).build());gen.generateKey();
        }
        return (SecretKey)store.getKey(ALIAS,null);
    }
    public synchronized void put(String name,String value)throws Exception{
        validate(name);if(value==null||value.isBlank()||value.length()>16384)throw new IllegalArgumentException("Invalid secret value");
        Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.ENCRYPT_MODE,key());
        c.updateAAD(name.getBytes(StandardCharsets.UTF_8));
        byte[] data=c.doFinal(value.getBytes(StandardCharsets.UTF_8));
        prefs.edit().putString(name,Base64.encodeToString(c.getIV(),Base64.NO_WRAP)+":"+Base64.encodeToString(data,Base64.NO_WRAP)).apply();
    }
    public synchronized String get(String name)throws Exception{
        validate(name);String encrypted=prefs.getString(name,null);if(encrypted==null)return null;
        String[] parts=encrypted.split(":",2);if(parts.length!=2)throw new SecurityException("Corrupt secret record");
        byte[] iv=Base64.decode(parts[0],Base64.NO_WRAP),data=Base64.decode(parts[1],Base64.NO_WRAP);
        Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,iv));
        c.updateAAD(name.getBytes(StandardCharsets.UTF_8));
        return new String(c.doFinal(data),StandardCharsets.UTF_8);
    }
    public boolean has(String name){validate(name);return prefs.contains(name);}
    public void remove(String name){validate(name);prefs.edit().remove(name).apply();}
}
