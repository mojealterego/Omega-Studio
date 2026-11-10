package org.omega.actions;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/** Trusted, packaged UI only. External pages never inherit the native JS bridge. */
public final class MainActivity extends Activity {
    private WebView web;
    private NativeBridge bridge;
    private ValueCallback<Uri[]> pendingFiles;
    private String pendingModelCallback;
    private static final int PICK_FILE=400;
    private static final int PICK_MODEL=401;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        web=new WebView(this);
        setContentView(web);
        WebSettings settings=web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        if(Build.VERSION.SDK_INT>=26)settings.setSafeBrowsingEnabled(true);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String url=request.getUrl().toString();
                if(url.startsWith("file:///android_asset/"))return false;
                if("https".equals(request.getUrl().getScheme())) {
                    try {startActivity(new Intent(Intent.ACTION_VIEW,request.getUrl()));}catch(Exception ignored){}
                }
                return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if(pendingFiles!=null)pendingFiles.onReceiveValue(null);
                pendingFiles=callback;
                try {startActivityForResult(params.createIntent(),PICK_FILE);return true;}
                catch(Exception e){pendingFiles=null;callback.onReceiveValue(null);return false;}
            }
        });
        bridge=new NativeBridge(this,web);
        web.addJavascriptInterface(bridge,"omega");
        web.loadUrl("file:///android_asset/index.html");
    }
    public void openEditor(){runOnUiThread(()->startActivity(new Intent(this,CodeEditorActivity.class)));}
    public void pickModel(String callbackId){
        runOnUiThread(()->{
            pendingModelCallback=callbackId;
            Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT);
            i.addCategory(Intent.CATEGORY_OPENABLE);i.setType("*/*");
            try{startActivityForResult(i,PICK_MODEL);}catch(Exception e){bridge.callback(callbackId,"{\"error\":\"Nie można otworzyć wyboru pliku\"}");}
        });
    }
    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data){
        super.onActivityResult(requestCode,resultCode,data);
        if(requestCode==PICK_FILE){
            if(pendingFiles!=null){pendingFiles.onReceiveValue(resultCode==RESULT_OK&&data!=null&&data.getData()!=null?new Uri[]{data.getData()}:null);pendingFiles=null;}
        }else if(requestCode==PICK_MODEL){
            if(pendingModelCallback!=null){
                String cb=pendingModelCallback;pendingModelCallback=null;
                if(resultCode==RESULT_OK&&data!=null&&data.getData()!=null)bridge.importModel(data.getData(),cb);
                else bridge.callback(cb,"{\"error\":\"Anulowano wybór modelu\"}");
            }
        }
    }
    @Override protected void onDestroy(){if(bridge!=null)bridge.shutdown();if(web!=null)web.destroy();super.onDestroy();}
}
