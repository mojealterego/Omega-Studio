/* OMEGA Studio AppBuilder — offline Code/NoCode compiler and deterministic ZIP exporter. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  root.OmegaBuilder=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
const THEMES={
  'obsidian-gold':['#07090d','#141923','#d4af37','#f4f1e9'],
  'graphite-silver':['#101319','#1c222b','#bac7d6','#f4f6f9'],
  'midnight-blue':['#071222','#12263e','#6cc7f7','#e9f6ff']
};
const TYPES=['heading','paragraph','card','button','input','divider'];
const ID=/^[a-z][a-z0-9_-]{0,47}$/;
const PKG=/^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){2,5}$/;
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const assert=(condition,message)=>{if(!condition)throw Error(message);};
function validate(project){
 assert(project&&typeof project==='object'&&!Array.isArray(project),'Niepoprawny projekt');
 assert(project.schema_version===1,'Nieobsługiwana wersja schematu');
 assert(typeof project.name==='string'&&project.name.trim()&&project.name.length<=80,'Niepoprawna nazwa');
 assert(typeof project.slug==='string'&&ID.test(project.slug),'Niepoprawny identyfikator projektu');
 assert(typeof project.package==='string'&&PKG.test(project.package)&&! /^(java|android|com\.android)\./.test(project.package),'Niepoprawny pakiet');
 assert(['web','android','both'].includes(project.platform),'Nieobsługiwana platforma');
 assert(Object.hasOwn(THEMES,project.theme),'Niepoprawny motyw');
 assert(Array.isArray(project.pages)&&project.pages.length>0&&project.pages.length<=16,'Wymagane 1–16 stron');
 const pages=new Set();
 for(const page of project.pages){
  assert(page&&typeof page==='object'&&typeof page.id==='string'&&ID.test(page.id)&&!pages.has(page.id),'Niepoprawny identyfikator strony');
  pages.add(page.id);
  assert(typeof page.title==='string'&&page.title.trim()&&page.title.length<=80,'Niepoprawny tytuł strony');
  assert(Array.isArray(page.components)&&page.components.length<=100,'Limit 100 komponentów na stronę');
  const ids=new Set();
  for(const c of page.components){
   assert(c&&TYPES.includes(c.type),'Nieznany typ komponentu');
   assert(typeof c.id==='string'&&ID.test(c.id)&&!ids.has(c.id),'Powtórzony identyfikator komponentu');ids.add(c.id);
   for(const key of ['text','label'])assert(c[key]===undefined||(typeof c[key]==='string'&&c[key].length<=(key==='text'?2000:120)),'Niepoprawny tekst');
   assert(c.action===undefined||c.action===''||(typeof c.action==='string'&&/^page:[a-z][a-z0-9_-]{0,47}$/.test(c.action)),'Niebezpieczna akcja');
  }
 }
 for(const page of project.pages)for(const c of page.components)if(c.action)assert(pages.has(c.action.slice(5)),'Nieistniejąca strona docelowa');
 return JSON.parse(JSON.stringify(project));
}
function sample(){return {
 schema_version:1,name:'Moja aplikacja',slug:'moja-aplikacja',package:'pl.omega.mojaaplikacja',platform:'both',theme:'obsidian-gold',
 pages:[{id:'home',title:'Strona główna',components:[
  {id:'welcome',type:'heading',text:'Witaj w przyszłości'},
  {id:'intro',type:'paragraph',text:'Zaprojektowano w OMEGA Studio — autorskim AppBuilderze Code / NoCode.'},
  {id:'feature',type:'card',text:'Luksusowy interfejs. Własne zasoby. Pełna kontrola nad kodem.'},
  {id:'open',type:'button',text:'Odkryj więcej',action:'page:about'}
 ]},{id:'about',title:'O aplikacji',components:[{id:'info',type:'paragraph',text:'Twoja aplikacja może działać lokalnie, bez usług chmurowych.'}]}]
};}
function componentHTML(c){
 const text=esc(c.text||'');
 switch(c.type){
  case 'heading':return `<h2>${text}</h2>`;
  case 'paragraph':return `<p>${text}</p>`;
  case 'card':return `<article class="feature">${text}</article>`;
  case 'divider':return '<hr>';
  case 'input':return `<label class="field">${esc(c.label||'')}<input type="text" maxlength="200" autocomplete="off"></label>`;
  case 'button':return `<button class="cta" type="button" data-target="${esc((c.action||'').replace(/^page:/,''))}">${text}</button>`;
  default:throw Error('Nieznany komponent');
 }
}
function css(theme){
 const [bg,panel,accent,fg]=THEMES[theme];
 return `:root{--bg:${bg};--panel:${panel};--gold:${accent};--fg:${fg}}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:var(--bg);color:var(--fg);font:16px/1.65 system-ui,sans-serif}header{display:flex;gap:14px;align-items:center;padding:22px 24px;border-bottom:1px solid #7775;font-weight:700;letter-spacing:.06em}header b{font:36px Georgia,serif;color:var(--gold)}main{max-width:820px;margin:auto;padding:40px 24px 140px}.page[hidden]{display:none}.overline{color:var(--gold);letter-spacing:.25em;font-size:10px}h1{font:500 clamp(32px,7vw,56px) Georgia,serif;margin:12px 0 36px}h2{font:500 28px Georgia,serif}p{color:#b7bdc8;line-height:1.8}.feature{border:1px solid #bda26355;background:var(--panel);padding:24px;border-radius:14px;margin:18px 0}.field{display:block;margin:20px 0}.field input{display:block;width:100%;background:var(--panel);border:1px solid #7775;border-radius:9px;padding:14px;color:var(--fg)}button{cursor:pointer}.cta{background:var(--gold);color:#080a0c;padding:14px 22px;border:0;border-radius:10px;font-weight:700}nav{position:fixed;bottom:0;left:0;right:0;display:flex;gap:8px;overflow:auto;background:var(--panel);border-top:1px solid #7775;padding:12px}nav button{background:transparent;color:var(--fg);border:1px solid #7775;border-radius:10px;padding:9px 12px;white-space:nowrap}nav button[aria-current=page]{color:var(--gold);border-color:var(--gold)}`;
}
const WEB_JS=`'use strict';const pages=[...document.querySelectorAll('.page')];function openPage(id){if(!pages.some(p=>p.dataset.page===id))return;for(const p of pages)p.hidden=p.dataset.page!==id;for(const b of document.querySelectorAll('nav button')){if(b.dataset.target===id)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');}scrollTo(0,0);}document.addEventListener('click',e=>{const b=e.target.closest('button[data-target]');if(b&&b.dataset.target)openPage(b.dataset.target);});openPage(pages[0].dataset.page);`;
function html(project){
 const p=validate(project);
 const pages=p.pages.map((page,i)=>`<section class="page" data-page="${esc(page.id)}" ${i?'hidden':''}><p class="overline">OMEGA APP BUILDER</p><h1>${esc(page.title)}</h1>${page.components.map(componentHTML).join('')}</section>`).join('');
 const nav=p.pages.map(page=>`<button type="button" data-target="${esc(page.id)}">${esc(page.title)}</button>`).join('');
 return `<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'none'; base-uri 'none'; form-action 'none'"><title>${esc(p.name)}</title><link rel="stylesheet" href="style.css"></head><body><header><b>Ω</b>${esc(p.name)}</header><main>${pages}</main><nav>${nav}</nav><script src="app.js"></script></body></html>`;
}
function preview(project){
 const p=validate(project);
 const pages=p.pages.map((page,i)=>`<section class="page" data-page="${esc(page.id)}" ${i?'hidden':''}><p class="overline">PODGLĄD APLIKACJI</p><h1>${esc(page.title)}</h1>${page.components.map(componentHTML).join('')}</section>`).join('');
 return `<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>${css(p.theme)}</style></head><body><header><b>Ω</b>${esc(p.name)}</header><main>${pages}</main></body></html>`;
}
function b64(s){const bytes=new TextEncoder().encode(s);let raw='';for(const x of bytes)raw+=String.fromCharCode(x);return btoa(raw);}
function java(project){
 const p=validate(project),[bg,panel,gold,fg]=THEMES[p.theme];
 const pages=p.pages.map(page=>{
  const items=page.components.map(c=>{
   if(c.type==='divider')return 'divider(root);';
   if(c.type==='input')return `field(root,dec("${b64(c.label||'')}"));`;
   if(c.type==='button')return `button(root,dec("${b64(c.text||'')}"),"${(c.action||'').replace(/^page:/,'')}");`;
   return `${c.type}(root,dec("${b64(c.text||'')}"));`;
  }).join('\n');
  return `case "${page.id}":title(dec("${b64(page.title)}"));${items}break;`;
 }).join('\n');
 const nav=p.pages.map(page=>`button(nav,dec("${b64(page.title)}"),"${page.id}");`).join('\n');
 return `package ${p.package};
import android.app.Activity;import android.os.Bundle;import android.graphics.Color;import android.graphics.Typeface;import android.graphics.drawable.GradientDrawable;import android.view.View;import android.widget.Button;import android.widget.EditText;import android.widget.LinearLayout;import android.widget.ScrollView;import android.widget.TextView;import android.util.Base64;import java.nio.charset.StandardCharsets;
public final class MainActivity extends Activity {
 private LinearLayout root;
 private final int BG=Color.parseColor("${bg}"),PANEL=Color.parseColor("${panel}"),GOLD=Color.parseColor("${gold}"),FG=Color.parseColor("${fg}");
 private static String dec(String s){return new String(Base64.decode(s,Base64.NO_WRAP),StandardCharsets.UTF_8);}
 private int dp(int x){return (int)(getResources().getDisplayMetrics().density*x+.5f);}
 private GradientDrawable shape(int c){GradientDrawable d=new GradientDrawable();d.setColor(c);d.setCornerRadius(dp(12));return d;}
 private TextView text(String s,int size,int color){TextView t=new TextView(this);t.setText(s);t.setTextSize(size);t.setTextColor(color);t.setPadding(dp(4),dp(12),dp(4),dp(12));return t;}
 private void heading(LinearLayout l,String s){TextView t=text(s,27,FG);t.setTypeface(Typeface.SERIF,Typeface.BOLD);l.addView(t);}
 private void title(String s){TextView t=text(s,34,GOLD);t.setTypeface(Typeface.SERIF,Typeface.NORMAL);root.addView(t);}
 private void paragraph(LinearLayout l,String s){l.addView(text(s,16,FG));}
 private void card(LinearLayout l,String s){TextView t=text(s,17,FG);t.setPadding(dp(20),dp(22),dp(20),dp(22));t.setBackground(shape(PANEL));LinearLayout.LayoutParams q=new LinearLayout.LayoutParams(-1,-2);q.setMargins(0,dp(12),0,dp(12));l.addView(t,q);}
 private void divider(LinearLayout l){View v=new View(this);v.setBackgroundColor(GOLD);LinearLayout.LayoutParams q=new LinearLayout.LayoutParams(-1,dp(1));q.setMargins(0,dp(12),0,dp(12));l.addView(v,q);}
 private void field(LinearLayout l,String label){l.addView(text(label,14,GOLD));EditText e=new EditText(this);e.setSingleLine(true);e.setTextColor(FG);e.setBackground(shape(PANEL));e.setPadding(dp(14),dp(12),dp(14),dp(12));l.addView(e);}
 private void button(LinearLayout l,String label,String target){Button b=new Button(this);b.setText(label);b.setTextColor(BG);b.setAllCaps(false);b.setBackground(shape(GOLD));LinearLayout.LayoutParams q=new LinearLayout.LayoutParams(-1,-2);q.setMargins(0,dp(8),0,dp(8));l.addView(b,q);if(!target.isEmpty())b.setOnClickListener(v->showPage(target));}
 @Override public void onCreate(Bundle b){super.onCreate(b);showPage("${p.pages[0].id}");}
 private void showPage(String id){ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(BG);root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setPadding(dp(20),dp(30),dp(20),dp(30));scroll.addView(root);switch(id){${pages}default:throw new IllegalArgumentException("Unknown page");}divider(root);LinearLayout nav=new LinearLayout(this);nav.setOrientation(LinearLayout.VERTICAL);${nav}root.addView(nav);setContentView(scroll);}
}`;
}
function files(project){
 const p=validate(project),out={};
 out['appbuilder.project.json']=JSON.stringify(p,null,2)+'\n';
 if(p.platform!=='android'){
  out['web/index.html']=html(p);out['web/style.css']=css(p.theme);out['web/app.js']=WEB_JS;
 }
 if(p.platform!=='web'){
  out[`android/app/src/main/java/${p.package.replace(/\./g,'/')}/MainActivity.java`]=java(p);
  out['android/app/src/main/AndroidManifest.xml']=`<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application android:label="${esc(p.name)}" android:theme="@android:style/Theme.Material.NoActionBar" android:usesCleartextTraffic="false" android:allowBackup="false"><activity android:name=".MainActivity" android:exported="true"><intent-filter><action android:name="android.intent.action.MAIN"/><category android:name="android.intent.category.LAUNCHER"/></intent-filter></activity></application></manifest>`;
  out['android/app/build.gradle']=`plugins { id 'com.android.application' }\nandroid { namespace '${p.package}'; compileSdk 35; defaultConfig { applicationId '${p.package}'; minSdk 26; targetSdk 35; versionCode 1; versionName '1.0.0' }; compileOptions { sourceCompatibility JavaVersion.VERSION_17; targetCompatibility JavaVersion.VERSION_17 } }`;
  out['android/build.gradle']="plugins { id 'com.android.application' version '8.7.3' apply false }";
  out['android/settings.gradle']="pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }\ndependencyResolutionManagement { repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS); repositories { google(); mavenCentral() } }\nrootProject.name='OmegaGeneratedApp'\ninclude ':app'";
  out['android/gradle.properties']='org.gradle.jvmargs=-Xmx2g -Dfile.encoding=UTF-8\nandroid.useAndroidX=true\n';
 }
 out['README.md']=`# ${p.name}\nProjekt wygenerowany lokalnie w OMEGA AppBuilder. Web: folder web/. Android: folder android/, kompilacja Gradle + Android SDK 35. Android korzysta z natywnych widżetów, nie z WebView.\n`;
 return out;
}
// Store-only ZIP writer. No remote dependencies, deterministic file ordering and timestamps.
const crcTable=(()=>{const t=new Uint32Array(256);for(let n=0;n<256;n++){let c=n;for(let k=0;k<8;k++)c=(c&1)?0xedb88320^(c>>>1):c>>>1;t[n]=c>>>0;}return t;})();
function crc32(bytes){let c=0xffffffff;for(const b of bytes)c=crcTable[(c^b)&255]^(c>>>8);return(c^0xffffffff)>>>0;}
function zip(files){
 const enc=new TextEncoder(),parts=[],central=[];let offset=0;
 const u16=n=>[n&255,(n>>>8)&255],u32=n=>[n&255,(n>>>8)&255,(n>>>16)&255,(n>>>24)&255];
 const add=a=>{const b=Uint8Array.from(a);parts.push(b);offset+=b.length;};
 for(const name of Object.keys(files).sort()){
  assert(!name.startsWith('/')&&!name.split('/').includes('..'),'Niebezpieczna ścieżka ZIP');
  const fname=enc.encode(name),data=enc.encode(files[name]),crc=crc32(data),start=offset;
  assert(fname.length<=65535&&data.length<=20000000,'Przekroczony limit ZIP');
  add([...u32(0x04034b50),...u16(20),...u16(0x800),...u16(0),...u16(0),...u16(0),...u32(crc),...u32(data.length),...u32(data.length),...u16(fname.length),...u16(0)]);add(fname);add(data);
  central.push([...u32(0x02014b50),...u16(20),...u16(20),...u16(0x800),...u16(0),...u16(0),...u16(0),...u32(crc),...u32(data.length),...u32(data.length),...u16(fname.length),...u16(0),...u16(0),...u16(0),...u16(0),...u32(0),...u32(start),...fname]);
 }
 const dirOffset=offset;for(const entry of central)add(entry);const dirSize=offset-dirOffset;
 add([...u32(0x06054b50),...u16(0),...u16(0),...u16(central.length),...u16(central.length),...u32(dirSize),...u32(dirOffset),...u16(0)]);
 const result=new Uint8Array(offset);let cursor=0;for(const p of parts){result.set(p,cursor);cursor+=p.length;}return result;
}
return Object.freeze({validate,sample,html,preview,css,java,files,zip,types:TYPES});
});
