'use strict';
const $=s=>document.querySelector(s);
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function highlightCode(code,language){
  const escaped=escapeHtml(code);
  const keywords={python:'def class return if elif else for while import from as with try except finally async await yield lambda pass raise',
    javascript:'const let var function return if else for while class async await import export new throw try catch',
    typescript:'const let var function return if else for while class async await import export new interface type',
    rust:'fn let mut pub impl struct enum use mod match if else for while async await return',
    go:'func package import var const type struct interface return if else for range go defer',
    java:'public private class static void new return if else import package interface final',
    kotlin:'fun val var class object data return if else import package suspend',
    bash:'if then else fi for do done function export case esac',
    yaml:'name on jobs steps run uses needs env strategy matrix',json:'true false null'};
  const list=(keywords[language]||'').split(' ').filter(Boolean);
  if(!list.length)return escaped;
  const kw=new RegExp('\\b('+list.map(x=>x.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|')+')\\b','g');
  return escaped.replace(kw,'<span class="tok-key">$1</span>');
}
const _SEG=/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
function hfUrl(repo,rev,filename){
  const p=String(repo).split('/'),f=String(filename).split('/');
  if(p.length!==2||!p.every(x=>_SEG.test(x)&&x!=='.'&&x!=='..'))throw Error('Repozytorium musi mieć format autor/model');
  if(!_SEG.test(rev)||rev==='.'||rev==='..')throw Error('Niepoprawna rewizja');
  if(!f.length||!f.every(x=>_SEG.test(x)&&x!=='.'&&x!=='..')||!filename.toLowerCase().endsWith('.gguf'))throw Error('Wymagana względna ścieżka pliku .gguf');
  return 'https://huggingface.co/'+p.map(encodeURIComponent).join('/')+'/resolve/'+encodeURIComponent(rev)+'/'+f.map(encodeURIComponent).join('/')+'?download=true';
}
function modelSettings(v){
  const schema={context:[128,131072,'int'],threads:[1,128,'int'],batch:[1,8192,'int'],gpu_layers:[0,512,'int'],temperature:[0,5,'float'],top_k:[0,100000,'int'],top_p:[0,1,'float'],min_p:[0,1,'float'],repeat_penalty:[.1,10,'float'],seed:[-1,2147483647,'int'],max_tokens:[1,131072,'int']};
  const defaults={context:4096,threads:4,batch:256,gpu_layers:0,temperature:.7,top_k:40,top_p:.95,min_p:.05,repeat_penalty:1.1,seed:-1,max_tokens:512};
  const result={...defaults};
  for(const [k,val] of Object.entries(v)){
    if(!Object.hasOwn(schema,k))throw Error('Nieznany parametr: '+k);
    if(val===''||val===null||val===undefined)throw Error('Brak wartości: '+k);
    const n=Number(val),[lo,hi,type]=schema[k];
    if(!Number.isFinite(n)||n<lo||n>hi||(type==='int'&&!Number.isInteger(n)))throw Error('Niepoprawny parametr: '+k);
    result[k]=n;
  }
  return result;
}
function parseGgufHeader(buf){
  const v=new DataView(buf),decoder=new TextDecoder('utf-8',{fatal:true});let pos=0;const MAX=8*1024*1024;
  if(v.byteLength<24)throw Error('Za krótki nagłówek GGUF');
  function need(n){if(n<0||pos+n>v.byteLength||pos+n>MAX)throw Error('Metadane GGUF przekraczają limit odczytu');}
  function read(fmt,size){need(size);const n=v[fmt](pos,true);pos+=size;return n;}
  const u32=()=>read('getUint32',4),u64=()=>{const n=read('getBigUint64',8);if(n>BigInt(Number.MAX_SAFE_INTEGER))throw Error('Nadmierny rozmiar GGUF');return Number(n);};
  function str(){const n=u64();if(n>1024*1024)throw Error('Zbyt długi tekst GGUF');need(n);const s=decoder.decode(new Uint8Array(buf,pos,n));pos+=n;return s;}
  const readers={0:()=>read('getUint8',1),1:()=>read('getInt8',1),2:()=>read('getUint16',2),3:()=>read('getInt16',2),4:u32,5:()=>read('getInt32',4),6:()=>read('getFloat32',4),7:()=>!!read('getUint8',1),8:str,10:u64,11:()=>{const n=read('getBigInt64',8);return n.toString();},12:()=>read('getFloat64',8)};
  function val(t,depth=0){if(depth>2)throw Error('Zbyt głęboka tablica GGUF');if(t===9){const et=u32(),len=u64();if(len>100000)throw Error('Tablica GGUF zbyt długa');return Array.from({length:len},()=>val(et,depth+1));}if(!readers[t])throw Error('Nieznany typ metadanych GGUF: '+t);return readers[t]();}
  const magic=String.fromCharCode(...new Uint8Array(buf,0,4));if(magic!=='GGUF')throw Error('To nie jest plik GGUF');pos=4;
  const version=u32();if(version!==2&&version!==3)throw Error('Nieobsługiwana wersja GGUF');
  const tensors=u64(),count=u64();if(count>100000)throw Error('Nadmierna liczba kluczy GGUF');
  const metadata={};for(let i=0;i<count;i++){const key=str(),type=u32();if(Object.hasOwn(metadata,key))throw Error('Powtórzony klucz GGUF');const value=val(type);if(!Array.isArray(value)||value.length<=16)metadata[key]=value;else metadata[key]=`[${value.length} elementów]`;}
  return {version,tensor_count:tensors,metadata_count:count,metadata};
}
function analyzeWorkflow(text){
  const lines=String(text).split(/\r?\n/),jobs=[];let inJobs=false,steps=0;
  for(const line of lines){if(/^jobs:\s*(?:#.*)?$/.test(line)){inJobs=true;continue;}
    if(/^\S/.test(line))inJobs=false;
    if(inJobs){const m=line.match(/^  ([\w.-]+):\s*(?:#.*)?$/);if(m)jobs.push(m[1]);if(/^\s+-\s+(?:run|uses):/.test(line))steps++;}}
  return {name:(text.match(/^name:\s*(.+)$/m)||[])[1]||'Bez nazwy',jobs,steps,kind:'analiza strukturalna (nie kompilator YAML)'};
}
function normalizeProviderCatalog(payload){
  if(!payload||payload.version!==1||!Array.isArray(payload.providers))throw Error('Niepoprawny katalog dostawców');
  const ids=new Set();
  return payload.providers.map(p=>{
    if(!p||!/^([a-z][a-z0-9-]{1,47})$/.test(p.id)||ids.has(p.id)||typeof p.title!=='string'||p.title.length>100)throw Error('Niepoprawny identyfikator dostawcy');
    ids.add(p.id);
    if(typeof p.endpoint!=='string'||typeof p.secret_name!=='string')throw Error('Niepoprawny endpoint dostawcy');
    const u=new URL(p.endpoint);
    if(u.username||u.password||u.hash||u.search||
       (p.remote ? (u.protocol!=='https:'||(u.port&&u.port!=='443')) :
        (u.protocol!=='http:'||u.hostname!=='127.0.0.1')))
      throw Error('Niezaufany endpoint API');
    if(p.remote&&!/^[A-Z][A-Z0-9_]{2,63}$/.test(p.secret_name))throw Error('Niepoprawna nazwa klucza');
    return {id:p.id,title:p.title,endpoint:p.endpoint,secret_name:p.secret_name,remote:!!p.remote,style:p.style};
  });
}
if(typeof module!=='undefined'&&module.exports)module.exports={parseGgufHeader,hfUrl,analyzeWorkflow,modelSettings,highlightCode,normalizeProviderCatalog};
if(typeof document!=='undefined'){
  const pending=new Map();let nextId=1;
  window.omegaNativeCallback=(id,payload)=>{
    const item=pending.get(id);if(!item)return;pending.delete(id);
    try{const data=JSON.parse(payload);if(data&&data.error)item.reject(new Error(data.error));else item.resolve(data);}
    catch(e){item.reject(e);}
  };
  function nativeCall(method,...args){
    if(typeof omega==='undefined'||typeof omega[method]!=='function')return Promise.reject(new Error('Funkcja wymaga natywnej wersji Android Studio'));
    const id='cb'+nextId++;
    return new Promise((resolve,reject)=>{
      pending.set(id,{resolve,reject});
      try{omega[method](...args,id);}catch(e){pending.delete(id);reject(e);}
      const limit=(method==='downloadHf'||method==='pickModel'||method==='inferModel'||method==='runWorkflow')?3600000:120000;
      setTimeout(()=>{if(pending.has(id)){pending.delete(id);reject(new Error('Limit czasu operacji'))}},limit);
    });
  }
  const providers=normalizeProviderCatalog(JSON.parse($('#providerCatalogJson').textContent));
  for(const provider of providers){
    const opt=document.createElement('option');opt.value=provider.id;opt.textContent=provider.title+(provider.remote?' · API':' · lokalnie');
    $('#chatProvider').appendChild(opt);
    if(provider.secret_name){const key=document.createElement('option');key.value=provider.secret_name;key.textContent=provider.title;$('#keyName').appendChild(key);}
  }
  if(![...$('#keyName').options].some(o=>o.value==='GITHUB_TOKEN')){
    const opt=document.createElement('option');opt.value='GITHUB_TOKEN';opt.textContent='GitHub (repozytoria)';$('#keyName').appendChild(opt);
  }
  $('#chatProvider').value='openai';
  $('#chatProvider').addEventListener('change',()=>{
    const defaults={openai:'gpt-4.1-mini',anthropic:'claude-sonnet-4-5',gemini:'gemini-2.5-flash',ollama:'llama3.2',
                    'llama-cpp':'local-model','lm-studio':'local-model',vllm:'local-model'};
    $('#chatModel').value=defaults[$('#chatProvider').value]||'';
  });
  $('#chatSend').addEventListener('click',async()=>{
    const provider=providers.find(x=>x.id===$('#chatProvider').value);
    const output=$('#chatResult');
    if(provider.remote&&!$('#chatCost').checked){output.textContent='Wymagane potwierdzenie kosztu zewnętrznego API.';return;}
    output.textContent='Oczekiwanie na odpowiedź modelu…';
    try{
      const result=await nativeCall('chatProvider',provider.id,$('#chatModel').value.trim(),$('#chatMessage').value,$('#chatCost').checked);
      output.textContent='Model: '+result.model+'\n\n'+result.text;
    }catch(e){output.textContent='Błąd: '+String(e.message||e);}
  });
  $('#chatClear').addEventListener('click',()=>{$('#chatMessage').value='';$('#chatResult').textContent='Wyczyszczono.';});
  const hasBridge=typeof omega!=='undefined'&&typeof omega.runAsync==='function';
  $('#status').textContent=hasBridge?'SHELL · ONLINE':'PODGLĄD UI';
  document.querySelectorAll('nav button').forEach(b=>b.addEventListener('click',()=>{
    document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('active',x===b));
    document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('active',x.id===b.dataset.tab));
  }));
  const source=$('#source'),hl=$('#highlight'),lines=$('#lines');
  function refresh(){hl.innerHTML=highlightCode(source.value,$('#language').value)+'\n';lines.textContent=source.value.split('\n').map((_,i)=>i+1).join('\n');$('#editorInfo').textContent=$('#language').selectedOptions[0].text+' · '+source.value.length+' znaków';}
  source.addEventListener('input',()=>{refresh();$('#editorState').textContent='Szkic niezapisany';});
  source.addEventListener('scroll',()=>{hl.scrollTop=source.scrollTop;hl.scrollLeft=source.scrollLeft;lines.scrollTop=source.scrollTop;});
  source.addEventListener('keydown',e=>{if(e.key==='Tab'){e.preventDefault();const p=source.selectionStart;source.setRangeText('    ',p,source.selectionEnd,'end');refresh();}});
  $('#language').addEventListener('change',refresh);
  const storeKey='omega.studio.draft.v4';
  try{const d=JSON.parse(localStorage.getItem(storeKey)||'null');if(d){source.value=d.text;$('#filename').value=d.filename;$('#language').value=d.language;$('#editorState').textContent='Odzyskano szkic';}}catch(_){/* storage may be disabled */}
  $('#saveDraft').addEventListener('click',()=>{try{localStorage.setItem(storeKey,JSON.stringify({text:source.value,filename:$('#filename').value,language:$('#language').value}));$('#editorState').textContent='Zapisano lokalnie';}catch(e){$('#editorState').textContent='Brak dostępu do pamięci szkiców';}});
  $('#newDraft').addEventListener('click',()=>{source.value='';$('#filename').value='nowy.py';refresh();});
  $('#nativeSave').addEventListener('click',async()=>{
    try{const r=await nativeCall('saveFile',$('#filename').value,source.value);$('#editorState').textContent='Zapisano: '+r.name;}
    catch(e){$('#editorState').textContent=String(e.message||e);}
  });
  $('#nativeRead').addEventListener('click',async()=>{
    try{const files=await nativeCall('listWorkspace');const name=prompt('Plik z workspace:\n'+files.files.join('\n'));if(!name)return;
      const r=await nativeCall('readFile',name);source.value=r.text;$('#filename').value=r.name;refresh();}
    catch(e){$('#editorState').textContent=String(e.message||e);}
  });

  $('#importCode').addEventListener('click',()=>$('#codeFile').click());
  $('#codeFile').addEventListener('change',async e=>{const file=e.target.files[0];if(!file)return;if(file.size>2*1024*1024){$('#editorState').textContent='Plik przekracza limit 2 MB';return;}source.value=await file.text();$('#filename').value=file.name;refresh();});
  refresh();
  document.querySelectorAll('[data-cmd]').forEach(b=>b.addEventListener('click',()=>$('#command').value=b.dataset.cmd));
  $('#runCommand').addEventListener('click',async()=>{
    const cmd=$('#command').value.trim(),out=$('#terminalOutput');
    if(!cmd||cmd.length>2048){out.textContent+='\nBłędne polecenie (limit 2048 znaków).';return;}
    if(!hasBridge){out.textContent+='\nPowłoka Android niedostępna poza APK.';return;}
    out.textContent+='\n$ '+cmd+'\n';
    try{
      if(typeof omega.runAsync==='function'){const r=await nativeCall('runAsync',cmd);out.textContent+=r.output+'\n[exit '+r.exit_code+']';}
      else out.textContent+=String(omega.run(cmd)).slice(0,30000);
    }catch(e){out.textContent+='Błąd: '+String(e.message||e);}
  });
  $('#installRuntime').addEventListener('click',async()=>{
    $('#runtimeStatus').textContent='Weryfikacja i instalacja zasobów…';
    try{$('#runtimeStatus').textContent=JSON.stringify(await nativeCall('installBootstrap'));}
    catch(e){$('#runtimeStatus').textContent='Runtime niedostępny: '+String(e.message||e);}
  });
  $('#vscodeStart').addEventListener('click',async()=>{
    const out=$('#vscodeStatus');out.textContent='Uruchamianie code-server (maks. 20 sekund)…';
    try{const r=await nativeCall('startCodeServer');out.textContent='Serwer: '+r.url+'\nHasło jednorazowe: '+r.password+'\nStatus: GOTOWY';}
    catch(e){out.textContent='BŁĄD: '+String(e.message||e);}
  });
  $('#vscodeOpen').addEventListener('click',async()=>{
    try{await nativeCall('openCodeServer');}
    catch(e){$('#vscodeStatus').textContent='BŁĄD: '+String(e.message||e);}
  });
  $('#vscodeStop').addEventListener('click',async()=>{
    try{await nativeCall('stopCodeServer');$('#vscodeStatus').textContent='Serwer zatrzymany. Hasło sesji unieważnione.';}
    catch(e){$('#vscodeStatus').textContent='BŁĄD: '+String(e.message||e);}
  });
  $('#runtimeProbe').addEventListener('click',async()=>{
    const out=$('#vscodeStatus');out.textContent='Sprawdzanie rzeczywistego wykonania binariów ARM64…';
    try{out.textContent=JSON.stringify(await nativeCall('runtimeHealth'),null,2);}
    catch(e){out.textContent='BŁĄD: '+String(e.message||e);}
  });
  $('#ciRun').addEventListener('click',async()=>{
    const file=$('#ciFile').files[0];const out=$('#ciRunResult');
    if(!file||file.size>1024*1024){out.textContent='Wybierz workflow YAML do 1 MiB.';return;}
    if(!$('#ciUnsafe').checked){out.textContent='Wymagana zgoda na wykonywanie poleceń CI.';return;}
    if(!/^[A-Za-z0-9._-]{1,128}\.ya?ml$/.test(file.name)){out.textContent='Niepoprawna nazwa workflow.';return;}
    out.textContent='Trwa uruchamianie lokalnego CI…';
    try{
      await nativeCall('saveFile',file.name,await file.text());
      const result=await nativeCall('runWorkflow',file.name,true);
      out.textContent='Kod zakończenia: '+result.exit_code+'\n'+result.output;
    }catch(e){out.textContent='Błąd: '+String(e.message||e);}
  });
  $('#ciFile').addEventListener('change',async e=>{const f=e.target.files[0];if(!f)return;if(f.size>1024*1024){$('#ciResult').textContent='Limit 1 MB';return;}try{$('#ciResult').textContent=JSON.stringify(analyzeWorkflow(await f.text()),null,2);}catch(e){$('#ciResult').textContent=String(e);}});
  $('#ggufFile').addEventListener('change',async e=>{const f=e.target.files[0];if(!f)return;try{const b=await f.slice(0,Math.min(f.size,8*1024*1024)).arrayBuffer();const d=parseGgufHeader(b);const summary={file:f.name,bytes:f.size,version:d.version,tensors:d.tensor_count,metadata_count:d.metadata_count,metadata:{}};for(const k of ['general.name','general.architecture','general.file_type','llama.context_length','general.quantization_version'])if(Object.hasOwn(d.metadata,k))summary.metadata[k]=d.metadata[k];$('#ggufInfo').textContent=JSON.stringify(summary,null,2);}catch(e){$('#ggufInfo').textContent='Błąd odczytu GGUF: '+String(e.message||e);}});
  const settingsKey='omega.studio.model.v4';
  try{const stored=JSON.parse(localStorage.getItem(settingsKey)||'null');if(stored)for(const [k,v] of Object.entries(stored))if(document.getElementById(k))document.getElementById(k).value=v;}catch(_){/* storage disabled */}
  $('#saveModelSettings').addEventListener('click',()=>{try{const obj={};for(const id of ['context','threads','batch','gpu_layers','temperature','top_k','top_p','min_p','repeat_penalty','seed','max_tokens'])obj[id]=$('#'+id).value;const v=modelSettings(obj);localStorage.setItem(settingsKey,JSON.stringify(v));$('#modelSettingsStatus').textContent='Zapisano';}catch(e){$('#modelSettingsStatus').textContent=String(e.message||e);}});
  $('#hfGenerate').addEventListener('click',()=>{try{$('#hfUrl').textContent=hfUrl($('#hfRepo').value.trim(),$('#hfRevision').value.trim(),$('#hfFile').value.trim());}catch(e){$('#hfUrl').textContent='Błąd: '+String(e.message||e);}});
  $('#hfCopy').addEventListener('click',()=>{const u=$('#hfUrl').textContent;if(u.startsWith('https://')){source.value=u;refresh();document.querySelector('nav [data-tab=editor]').click();}});
  $('#nativeImport').addEventListener('click',async()=>{try{$('#nativeModelResult').textContent=JSON.stringify(await nativeCall('pickModel'),null,2);}catch(e){$('#nativeModelResult').textContent=String(e.message||e);}});
  $('#modelList').addEventListener('click',async()=>{try{$('#nativeModelResult').textContent=JSON.stringify(await nativeCall('listModels'),null,2);}catch(e){$('#nativeModelResult').textContent=String(e.message||e);}});
  $('#inferRun').addEventListener('click',async()=>{
    try{const obj={};for(const id of ['context','threads','batch','gpu_layers','temperature','top_k','top_p','min_p','repeat_penalty','seed','max_tokens'])obj[id]=$('#'+id).value;
      $('#inferResult').textContent='Trwa inferencja…';
      $('#inferResult').textContent=JSON.stringify(await nativeCall('inferModel',$('#inferModelName').value.trim(),$('#inferPrompt').value,JSON.stringify(modelSettings(obj))),null,2);
    }catch(e){$('#inferResult').textContent=String(e.message||e);}
  });

  $('#hfDownloadNative').addEventListener('click',async()=>{
    $('#hfNativeResult').textContent='Pobieranie modelu — operacja może potrwać kilka minut…';
    try{$('#hfNativeResult').textContent=JSON.stringify(await nativeCall('downloadHf',$('#hfRepo').value.trim(),$('#hfRevision').value.trim(),$('#hfFile').value.trim(),$('#hfSha').value.trim()),null,2);}
    catch(e){$('#hfNativeResult').textContent=String(e.message||e);}
  });
  $('#githubNative').addEventListener('click',async()=>{
    const repo=$('#repoName').value.trim();if(!/^[\w.-]+\/[\w.-]+$/.test(repo))return;
    try{$('#repoResult').textContent=JSON.stringify(await nativeCall('githubGet','/repos/'+repo),null,2);}
    catch(e){$('#repoResult').textContent=String(e.message||e);}
  });
  $('#saveKey').addEventListener('click',async()=>{
    try{await nativeCall('saveSecret',$('#keyName').value,$('#keyValue').value);$('#keyValue').value='';$('#keyResult').textContent='Klucz zaszyfrowany w Android Keystore.';}
    catch(e){$('#keyResult').textContent=String(e.message||e);}
  });
  $('#keyStatus').addEventListener('click',async()=>{
    try{$('#keyResult').textContent=JSON.stringify(await nativeCall('secretStatus',$('#keyName').value),null,2);}
    catch(e){$('#keyResult').textContent=String(e.message||e);}
  });
  if(typeof omega!=='undefined'&&typeof omega.capabilities==='function'){
    try{$('#capabilities').textContent=JSON.stringify(JSON.parse(omega.capabilities()),null,2);}catch(e){$('#capabilities').textContent='Błąd odczytu możliwości';}
  }else $('#capabilities').textContent='APK podglądowy: dostępna tylko powłoka Android, bez natywnego SDK.';
  $('#repoOpen').addEventListener('click',()=>{const r=$('#repoName').value.trim();$('#repoResult').textContent=/^[\w.-]+\/[\w.-]+$/.test(r)?'https://github.com/'+r:'Niepoprawny identyfikator repozytorium';});
}
