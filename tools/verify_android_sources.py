"""Compile Java against local API-surface stubs; not a replacement for Android SDK build."""
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
STUBS={
 'android/content/Context.java':'''package android.content; public class Context { public static final int MODE_PRIVATE=0; public java.io.File getFilesDir(){return null;}public String getPackageName(){return "org.omega.actions";} public ContentResolver getContentResolver(){return null;}public android.content.res.AssetManager getAssets(){return null;} public SharedPreferences getSharedPreferences(String a,int b){return null;} }''',
 'android/content/ContentResolver.java':'''package android.content; public class ContentResolver {public android.database.Cursor query(android.net.Uri u,String[] a,String b,String[] c,String d){return null;} public java.io.InputStream openInputStream(android.net.Uri u){return null;}}''',
 'android/content/SharedPreferences.java':'''package android.content; public interface SharedPreferences {String getString(String n,String v);boolean contains(String n);Editor edit();interface Editor{Editor putString(String n,String v);Editor remove(String n);void apply();}}''',
 'android/content/Intent.java':'''package android.content;public class Intent{public static final String ACTION_VIEW="",ACTION_OPEN_DOCUMENT="",CATEGORY_OPENABLE="";public Intent(){}public Intent(String s,android.net.Uri u){}public Intent(String s){}public Intent addCategory(String s){return this;}public Intent setType(String s){return this;}public android.net.Uri getData(){return null;}}''',
 'android/database/Cursor.java':'''package android.database;public interface Cursor extends AutoCloseable{boolean moveToFirst();String getString(int n);void close();}''',
 'android/net/Uri.java':'''package android.net;public class Uri{public String getScheme(){return "";}public String toString(){return "";}}''',
 'android/content/res/AssetManager.java':'''package android.content.res;public class AssetManager{public java.io.InputStream open(String n)throws java.io.IOException{return null;}}''',
 'android/system/Os.java':'''package android.system;public class Os{public static void chmod(String p,int mode){}public static void symlink(String t,String p){}}''',
 'android/os/Bundle.java':'''package android.os;public class Bundle{}''',
 'android/os/Build.java':'''package android.os;public class Build{public static class VERSION{public static int SDK_INT=35;}}''',
 'android/view/View.java':'''package android.view;public class View{}''',
 'android/app/Activity.java':'''package android.app;public class Activity extends android.content.Context{public static final int RESULT_OK=-1;protected void onCreate(android.os.Bundle b){}protected void onDestroy(){}protected void onActivityResult(int a,int b,android.content.Intent c){}public void setContentView(android.view.View v){}public void runOnUiThread(Runnable r){}public void startActivity(android.content.Intent i){}public void startActivityForResult(android.content.Intent i,int n){} }''',
 'android/webkit/WebSettings.java':'''package android.webkit;public class WebSettings{public void setJavaScriptEnabled(boolean b){}public void setDomStorageEnabled(boolean b){}public void setAllowFileAccess(boolean b){}public void setAllowContentAccess(boolean b){}public void setAllowFileAccessFromFileURLs(boolean b){}public void setAllowUniversalAccessFromFileURLs(boolean b){}public void setSafeBrowsingEnabled(boolean b){}}''',
 'android/webkit/WebView.java':'''package android.webkit;public class WebView extends android.view.View{public WebView(android.content.Context c){}public WebSettings getSettings(){return null;}public void addJavascriptInterface(Object o,String s){}public void loadUrl(String s){}public void setWebViewClient(WebViewClient w){}public void setWebChromeClient(WebChromeClient w){}public void evaluateJavascript(String s,ValueCallback<String> cb){}public void destroy(){}}''',
 'android/webkit/WebViewClient.java':'''package android.webkit;public class WebViewClient{public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest r){return false;}}''',
 'android/webkit/WebResourceRequest.java':'''package android.webkit;public interface WebResourceRequest{android.net.Uri getUrl();}''',
 'android/webkit/WebChromeClient.java':'''package android.webkit;public class WebChromeClient{public static class FileChooserParams{public android.content.Intent createIntent(){return null;}}public boolean onShowFileChooser(WebView w,ValueCallback<android.net.Uri[]> c,FileChooserParams p){return false;}}''',
 'android/webkit/ValueCallback.java':'''package android.webkit;public interface ValueCallback<T>{void onReceiveValue(T value);}''',
 'android/webkit/JavascriptInterface.java':'''package android.webkit;@java.lang.annotation.Retention(java.lang.annotation.RetentionPolicy.RUNTIME)public @interface JavascriptInterface{}''',
 'android/provider/OpenableColumns.java':'''package android.provider;public interface OpenableColumns{String DISPLAY_NAME="_display_name";}''',
 'android/security/keystore/KeyProperties.java':'''package android.security.keystore;public class KeyProperties{public static final String KEY_ALGORITHM_AES="AES",BLOCK_MODE_GCM="GCM",ENCRYPTION_PADDING_NONE="NoPadding";public static final int PURPOSE_ENCRYPT=1,PURPOSE_DECRYPT=2;}''',
 'android/security/keystore/KeyGenParameterSpec.java':'''package android.security.keystore;public class KeyGenParameterSpec implements java.security.spec.AlgorithmParameterSpec{public static class Builder{public Builder(String s,int i){}public Builder setBlockModes(String... v){return this;}public Builder setEncryptionPaddings(String... v){return this;}public Builder setKeySize(int n){return this;}public Builder setRandomizedEncryptionRequired(boolean b){return this;}public KeyGenParameterSpec build(){return new KeyGenParameterSpec();}}}''',
 'android/util/Base64.java':'''package android.util;public class Base64{public static final int NO_WRAP=2;public static String encodeToString(byte[] b,int f){return "";}public static byte[] decode(String b,int f){return new byte[0];}}''',
 'org/json/JSONObject.java':'''package org.json;public class JSONObject{public JSONObject(){}public JSONObject(String s){}public JSONObject(java.util.Map m){}public JSONObject put(String s,Object v){return this;}public String optString(String s){return "";}public String getString(String s){return "";}public boolean getBoolean(String s){return true;}public int getInt(String s){return 0;}public JSONArray getJSONArray(String s){return null;}public JSONObject getJSONObject(String s){return null;}public int optInt(String s,int d){return d;}public double optDouble(String s,double d){return d;}public static String quote(String s){return "";}public String toString(){return "";}}''',
 'org/json/JSONArray.java':'''package org.json;public class JSONArray{public JSONArray put(Object o){return this;}public int length(){return 0;}public JSONObject getJSONObject(int i){return null;}}'''
}

def main():
    with tempfile.TemporaryDirectory(prefix='omega-stubs-') as d:
        root=Path(d);paths=[]
        for name,src in STUBS.items():
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(src);paths.append(str(p))
        paths.extend(str(p) for p in (ROOT/'android/app/src/main/java').rglob('*.java'))
        out=root/'classes'
        p=subprocess.run(['javac','-source','17','-target','17','-d',str(out),*paths],capture_output=True,text=True,timeout=45)
        if p.returncode:raise RuntimeError(p.stderr)
        return {'status':'PASS','java_sources':len(paths)-len(STUBS),'android_sdk':'NOT_USED (stubs only)'}

if __name__=='__main__':print(main())
