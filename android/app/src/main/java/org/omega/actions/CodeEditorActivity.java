package org.omega.actions;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/** Dedicated VS Code browser surface with NO privileged JavaScript interface. */
public final class CodeEditorActivity extends Activity {
    private WebView web;
    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        String url=CodeServerManager.get().activeUrl();
        if(url==null){finish();return;}
        web=new WebView(this);setContentView(web);
        WebSettings settings=web.getSettings();
        settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);settings.setAllowContentAccess(false);
        settings.setAllowFileAccessFromFileURLs(false);settings.setAllowUniversalAccessFromFileURLs(false);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
                String requested=request.getUrl().toString();
                return !requested.startsWith(url);
            }
        });
        web.loadUrl(url);
    }
    @Override protected void onDestroy(){if(web!=null)web.destroy();super.onDestroy();}
}
