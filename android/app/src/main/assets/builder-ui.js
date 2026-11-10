/* Visual Code/NoCode studio: local-first, deterministic, no external scripts. */
(function(){
'use strict';
if(typeof document==='undefined'||!document.getElementById('builder'))return;
const B=globalThis.OmegaBuilder;
const $=id=>document.getElementById(id);
const KEY='omega.studio.builder.v1';
const names={heading:'Nagłówek',paragraph:'Akapit',card:'Karta',button:'Przycisk',input:'Pole tekstowe',divider:'Separator'};
let project=B.sample(),active='home',counter=0;
try{const saved=localStorage.getItem(KEY);if(saved)project=B.validate(JSON.parse(saved));}catch(e){$('builderStatus').textContent='Nie udało się odczytać poprzedniego projektu. Utworzono nowy.';}
active=project.pages[0].id;
function message(text,err=false){$('builderStatus').textContent=text;$('builderStatus').style.borderLeftColor=err?'#ce6060':'#b69a57';}
function persist(){try{localStorage.setItem(KEY,JSON.stringify(B.validate(project)));}catch(e){message('Błąd zapisu: '+e.message,true);}}
function node(tag,cls,text){const el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=text;return el;}
function unique(prefix,existing){let id;do{id=prefix+'_'+(++counter).toString(36);}while(existing.includes(id));return id;}
function page(){return project.pages.find(p=>p.id===active)||project.pages[0];}
function preview(){
 try{
  const p=B.validate(project);
  const i=p.pages.findIndex(x=>x.id===active);
  if(i>0)p.pages.unshift(p.pages.splice(i,1)[0]);
  $('builderPreview').srcdoc=B.preview(p);
 }catch(e){message('Podgląd: '+e.message,true);}
}
function field(label,value,onInput,kind='input'){
 const wrapper=node('label','builder-field',label);
 const input=node(kind);input.value=value||'';input.maxLength=kind==='textarea'?2000:120;
 input.addEventListener('input',()=>{onInput(input.value);preview();persist();});
 wrapper.appendChild(input);return wrapper;
}
function renderPages(){
 const target=$('builderPages');target.replaceChildren();
 for(const p of project.pages){
  const button=node('button',p.id===active?'selected':'',p.title);
  button.type='button';button.addEventListener('click',()=>{active=p.id;render();});target.appendChild(button);
 }
 $('builderPageTitle').value=page().title;
 $('builderRemovePage').disabled=project.pages.length===1;
}
function renderComponents(){
 const target=$('builderComponents');target.replaceChildren();
 const components=page().components;
 for(let index=0;index<components.length;index++){
  const c=components[index],box=node('div','builder-component'),top=node('div','builder-component-top');
  top.appendChild(node('strong','',String(index+1).padStart(2,'0')+' / '+names[c.type]));
  const actions=node('div','builder-component-actions');
  for(const [symbol,delta] of [['↑',-1],['↓',1]]){
   const button=node('button','',symbol);button.type='button';button.disabled=index+delta<0||index+delta>=components.length;
   button.setAttribute('aria-label',delta<0?'Przenieś w górę':'Przenieś w dół');
   button.addEventListener('click',()=>{const other=index+delta;[components[index],components[other]]=[components[other],components[index]];render();persist();});
   actions.appendChild(button);
  }
  const remove=node('button','builder-danger','×');remove.type='button';remove.setAttribute('aria-label','Usuń komponent');
  remove.addEventListener('click',()=>{components.splice(index,1);render();persist();});actions.appendChild(remove);
  top.appendChild(actions);box.appendChild(top);
  if(c.type!=='divider'){
   if(c.type==='input')box.appendChild(field('Etykieta',c.label||'',v=>{c.label=v;}));
   else box.appendChild(field('Treść',c.text||'',v=>{c.text=v;},c.type==='paragraph'||c.type==='card'?'textarea':'input'));
   if(c.type==='button'){
    const label=node('label','builder-field','Przejście do strony');
    const select=node('select');
    const none=node('option','','Brak akcji');none.value='';select.appendChild(none);
    for(const p of project.pages){const opt=node('option','',p.title);opt.value='page:'+p.id;select.appendChild(opt);}
    select.value=c.action||'';
    select.addEventListener('change',()=>{c.action=select.value;preview();persist();});
    label.appendChild(select);box.appendChild(label);
   }
  }
  target.appendChild(box);
 }
}
function render(){
 $('builderName').value=project.name;$('builderSlug').value=project.slug;$('builderPackage').value=project.package;
 $('builderPlatform').value=project.platform;$('builderTheme').value=project.theme;
 renderPages();renderComponents();preview();
}
for(const [id,key] of [['builderName','name'],['builderSlug','slug'],['builderPackage','package']]){
 $(id).addEventListener('input',e=>{project[key]=e.target.value;preview();persist();});
}
for(const [id,key] of [['builderPlatform','platform'],['builderTheme','theme']]){
 $(id).addEventListener('change',e=>{project[key]=e.target.value;preview();persist();});
}
$('builderPageTitle').addEventListener('input',e=>{page().title=e.target.value;renderPages();preview();persist();});
$('builderAddPage').addEventListener('click',()=>{
 if(project.pages.length>=16){message('Limit: 16 stron.',true);return;}
 const id=unique('page',project.pages.map(p=>p.id));project.pages.push({id,title:'Nowa strona',components:[]});active=id;render();persist();
});
$('builderRemovePage').addEventListener('click',()=>{
 if(project.pages.length===1)return;
 const id=active;project.pages=project.pages.filter(p=>p.id!==id);
 for(const p of project.pages)for(const c of p.components)if(c.action==='page:'+id)c.action='';
 active=project.pages[0].id;render();persist();
});
$('builderPalette').addEventListener('click',e=>{
 const button=e.target.closest('button[data-type]');if(!button)return;
 const type=button.dataset.type;if(!B.types.includes(type))return;
 const p=page();if(p.components.length>=100){message('Limit: 100 komponentów.',true);return;}
 const id=unique('component',p.components.map(c=>c.id));
 const defaults={heading:'Nowy nagłówek',paragraph:'Opis aplikacji',card:'Treść karty',button:'Przejdź dalej',input:'',divider:''};
 p.components.push({id,type,text:defaults[type],label:type==='input'?'Wpisz tekst':'',action:''});
 renderComponents();preview();persist();message('Dodano komponent: '+names[type]);
});
$('builderSave').addEventListener('click',()=>{try{persist();message('Projekt zapisany lokalnie na tym urządzeniu.');}catch(e){message(e.message,true);}});
$('builderReset').addEventListener('click',()=>{if(!confirm('Utworzyć nowy projekt? Niezapisane zmiany zostaną utracone.'))return;project=B.sample();active='home';render();persist();message('Utworzono nowy projekt.');});
$('builderLoad').addEventListener('click',()=>$('builderImport').click());
$('builderImport').addEventListener('change',async e=>{
 const file=e.target.files[0];if(!file)return;
 if(file.size>1024*1024){message('Plik JSON jest za duży.',true);return;}
 try{project=B.validate(JSON.parse(await file.text()));active=project.pages[0].id;render();persist();message('Zaimportowano projekt '+project.name);}
 catch(err){message('Import nieudany: '+err.message,true);}
 e.target.value='';
});
$('builderExport').addEventListener('click',()=>{
 try{
  const valid=B.validate(project),data=B.zip(B.files(valid));
  const blob=new Blob([data],{type:'application/zip'});
  const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='OMEGA_'+valid.slug+'_source.zip';
  document.body.appendChild(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),30000);
  message('Wygenerowano ZIP: '+data.length+' bajtów. Zawiera kod '+(valid.platform==='both'?'Web i Android':valid.platform)+'.');
 }catch(e){message('Eksport nieudany: '+e.message,true);}
});
render();
})();
