'use strict';
const token=document.querySelector('meta[name="omega-token"]').content;
const $=id=>document.getElementById(id);
const toast=(text)=>{const el=$('toast');el.textContent=text;el.classList.add('visible');setTimeout(()=>el.classList.remove('visible'),3500)};
async function api(path,method='GET',body=null){
  const response=await fetch(path,{method,headers:{'X-OMEGA-Token':token,'Content-Type':'application/json'},body:body===null?undefined:JSON.stringify(body),cache:'no-store'});
  const result=await response.json().catch(()=>({detail:'Invalid response'}));
  if(!response.ok)throw new Error(result.detail||`HTTP ${response.status}`);
  return result;
}
async function safe(fn){try{await fn()}catch(e){toast(e.message);$('signal').classList.remove('ok')}}
function showJson(id,value){$(id).textContent=JSON.stringify(value,null,2)}
function addRow(parent,text,buttons=[]){const row=document.createElement('div');row.className='run';const label=document.createElement('span');label.textContent=text;row.append(label);for(const b of buttons){const btn=document.createElement('button');btn.textContent=b.text;btn.addEventListener('click',()=>safe(b.fn));row.append(btn)}parent.append(row)}
for(const tab of document.querySelectorAll('.tab'))tab.addEventListener('click',()=>{
  for(const t of document.querySelectorAll('.tab'))t.classList.toggle('active',t===tab);
  for(const p of document.querySelectorAll('.panel'))p.classList.toggle('active',p.id===tab.dataset.tab);
});
async function loadStatus(){const status=await api('/api/omega/status');$('signal').classList.add('ok');$('conn').textContent=status.github_connected?'READY':'NOT SET';$('version').textContent='v'+status.version;showJson('policy',status);$('ghMinutes').textContent='0'}
$('loadLocal').onclick=()=>safe(async()=>{const repo=$('repoPath').value.trim();const data=await api('/api/workflows?repo='+encodeURIComponent(repo));const sel=$('workflow');sel.replaceChildren();for(const wf of data.workflows){const opt=document.createElement('option');opt.value=wf;opt.textContent=wf.split('/').pop();sel.append(opt)}toast(`${data.workflows.length} lokalnych workflowów`)});
$('compile').onclick=()=>safe(async()=>{const workflow=$('workflow').value;if(!workflow)throw Error('Wybierz workflow');showJson('dag',{dag:await api('/api/compile','POST',{workflow}),preflight:await api('/api/omega/compatibility','POST',{workflow})})});
$('run').onclick=()=>safe(async()=>{const workflow=$('workflow').value;if(!workflow)throw Error('Wybierz workflow');const data=await api('/api/runs','POST',{workflow,repo:$('repoPath').value,executor:'auto',event:'workflow_dispatch'});toast('Lokalny run: '+data.id.slice(0,10));await refreshRuns();watchRun(data.id)});
async function refreshRuns(){const data=await api('/api/runs');const root=$('runs');root.replaceChildren();$('runCount').textContent=data.length;for(const r of data.slice(0,12)){addRow(root,`${r.id.slice(0,8)} · ${r.status}`, [{text:'Logi',fn:()=>watchRun(r.id)},{text:'Anuluj',fn:()=>api('/api/runs/'+encodeURIComponent(r.id)+'/cancel','POST')}])}}
$('refreshRuns').onclick=()=>safe(refreshRuns);
async function watchRun(id){const log=$('logs');log.textContent='';let after=0;for(let attempt=0;attempt<120;attempt++){const response=await fetch('/api/runs/'+encodeURIComponent(id)+'/events?after='+after,{headers:{'X-OMEGA-Token':token}});if(!response.ok)throw Error('Logs unavailable');const reader=response.body.getReader();const decoder=new TextDecoder();let buffer='';let done=false;while(!done){const part=await reader.read();if(part.done)break;buffer+=decoder.decode(part.value,{stream:true});const blocks=buffer.split('\n\n');buffer=blocks.pop();for(const block of blocks){const line=block.split('\n').find(x=>x.startsWith('data: '));if(!line)continue;try{const entry=JSON.parse(line.slice(6));if(entry.seq)after=entry.seq;if(entry.message)log.textContent+=entry.message;else if(entry.text)log.textContent+=entry.text;else if(entry.status){done=true;break}}catch(_){}}}if(done)break;const run=await api('/api/runs/'+id);if(['success','failure','cancelled'].includes(run.status))break}await refreshRuns()}
$('oauthStart').onclick=()=>safe(async()=>{const data=await api('/api/omega/oauth/start','POST',{client_id:$('clientId').value.trim()});$('deviceCode').textContent=`Kod: ${data.user_code}\nOtwórz: ${data.verification_uri}\nOdczekaj minimum ${data.interval}s przed sprawdzeniem.`;toast('Autoryzuj aplikację w GitHub')});
$('oauthPoll').onclick=()=>safe(async()=>{const data=await api('/api/omega/oauth/poll','POST');showJson('deviceCode',data);if(data.status==='connected')await loadStatus()});
$('agentRun').onclick=()=>safe(async()=>{const data=await api('/api/omega/agent/run','POST',{message:$('message').value,model:$('model').value});showJson('aiResponse',data);await refreshPlans()});
$('getRepos').onclick=()=>safe(async()=>{const data=await api('/api/omega/github/repos');const root=$('repoList');root.replaceChildren();for(const repo of data)addRow(root,repo.full_name+(repo.private?' · PRIVATE':''));if(!data.length)root.textContent='Brak repozytoriów na allowliście'});
$('getWorkflows').onclick=()=>safe(async()=>showJson('remoteWorkflows',await api('/api/omega/github/workflows?repo='+encodeURIComponent($('githubRepo').value))));
$('propose').onclick=()=>safe(async()=>{const data=await api('/api/omega/plans','POST',{operation:$('op').value,repo:$('githubRepo').value,arguments:JSON.parse($('args').value)});toast('Plan utworzony: '+data.id.slice(0,10));await refreshPlans()});
async function refreshPlans(){const plans=await api('/api/omega/plans');const root=$('plans');root.replaceChildren();for(const plan of plans){const buttons=[];if(plan.status==='proposed')buttons.push({text:'Zatwierdź',fn:async()=>{if(!confirm(`Zatwierdzić ${plan.operation} dla ${plan.repo}?`))return;await api('/api/omega/plans/'+plan.id+'/approve','POST');await refreshPlans()}});if(plan.status==='approved')buttons.push({text:'Wykonaj',fn:async()=>{if(!confirm(`Wykonać ${plan.operation} w ${plan.repo}?`))return;await api('/api/omega/plans/'+plan.id+'/execute','POST');await refreshPlans()}});addRow(root,plan.operation+' · '+plan.status+' · '+plan.repo,buttons)}}
$('ask').onclick=()=>safe(async()=>{const data=await api('/api/omega/chat','POST',{message:$('message').value,provider:$('provider').value,model:$('model').value});showJson('aiResponse',data)});
$('provider').onchange=()=>{$('model').value=$('provider').value==='openai'?'gpt-5.5':'qwen2.5:3b'};
safe(async()=>{await loadStatus();await refreshRuns();if($('githubRepo').value)try{await refreshPlans()}catch(_){}});
