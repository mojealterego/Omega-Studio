/**
 * GAME.PDF Instant Playable: a deterministic 2D browser prototype compiled
 * from the existing Code/NoCode scene IR. No remote assets or script injection.
 */
import { createHash } from 'node:crypto';

const id = /^[A-Za-z][A-Za-z0-9_-]{0,95}$/;
const types = new Set(['scene','entity','camera','light','trigger','ui']);
const engines = new Set(['unity','unreal','godot']);
const validNumber = (v, fallback, min, max) => typeof v === 'number' && Number.isFinite(v) ? Math.min(max,Math.max(min,v)) : fallback;
function validate(project) {
 if (!project || typeof project !== 'object' || Array.isArray(project) ||
 project.schemaVersion !== 1 || !id.test(project.projectId) || !engines.has(project.engine) ||
 !Number.isSafeInteger(project.revision) || project.revision < 0 ||
 !Array.isArray(project.nodes) || project.nodes.length > 10000) throw Error('INVALID_PROJECT');
 const ids = new Set();
 for (const node of project.nodes) {
  if (!node || typeof node !== 'object' || !id.test(node.id) || ids.has(node.id) ||
  !types.has(node.type) || typeof node.name !== 'string' || node.name.length > 256 ||
  (node.parentId !== null && !id.test(node.parentId)) ||
  !node.properties || typeof node.properties !== 'object' || Array.isArray(node.properties))
   throw Error('INVALID_NODE');
  for (const [key,value] of Object.entries(node.properties)) {
   if (!id.test(key) || ['__proto__','constructor','prototype'].includes(key) ||
   !(value === null || typeof value === 'boolean' || typeof value === 'string' && value.length <= 8192 ||
   typeof value === 'number' && Number.isFinite(value))) throw Error('INVALID_PROPERTY');
  }
  ids.add(node.id);
 }
 for (const node of project.nodes) if (node.parentId !== null && !ids.has(node.parentId)) throw Error('MISSING_PARENT');
}
function belongsToScene(node, sceneId, byId) {
 const seen = new Set();
 let cursor = node;
 while (cursor) {
  if (seen.has(cursor.id)) throw Error('PARENT_CYCLE');
  seen.add(cursor.id);
  if (cursor.id === sceneId) return true;
  cursor = cursor.parentId === null ? null : byId.get(cursor.parentId);
 }
 return false;
}
export function compileInstantPlayable(project, { sceneId } = {}) {
 validate(project);
 const scenes = project.nodes.filter(n=>n.type === 'scene');
 const scene = sceneId ? scenes.find(s=>s.id===sceneId) : scenes[0];
 if (!scene) throw Error('SCENE_NOT_FOUND');
 const byId = new Map(project.nodes.map(n=>[n.id,n]));
 const objects = project.nodes.filter(n=>n.type==='entity' && belongsToScene(n,scene.id,byId))
 .map(n=>({
  id:n.id,name:n.name.slice(0,80),
  x:validNumber(n.properties.x,40,0,760),
  y:validNumber(n.properties.y,40,0,520),
  width:validNumber(n.properties.width,32,8,160),
  height:validNumber(n.properties.height,32,8,160),
  speed:validNumber(n.properties.speed,180,20,500),
  role:['player','collectible','obstacle'].includes(n.properties.role) ? n.properties.role : 'obstacle'
 }));
 if (!objects.some(o=>o.role==='player')) throw Error('PLAYER_REQUIRED');
 if (objects.filter(o=>o.role==='player').length!==1) throw Error('EXACTLY_ONE_PLAYER_REQUIRED');
 const world={projectId:project.projectId,revision:project.revision,scene:scene.name,objects};
 const encoded=Buffer.from(JSON.stringify(world),'utf8').toString('base64');
 const html=`<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
<title>OMEGA Instant Playable</title>
<style>body{background:#07080a;color:#f4f1ea;font:16px system-ui;margin:0;padding:18px;text-align:center}h1{color:#d4af37;font-size:22px}canvas{display:block;width:min(100%,800px);aspect-ratio:4/3;background:#111723;border:1px solid #aa8222;margin:auto;touch-action:none}.controls{display:flex;gap:12px;justify-content:center;margin:12px}button{font-size:20px;padding:14px 22px;background:#242936;color:#fff;border:1px solid #d4af37;border-radius:12px}</style>
</head><body><h1>OMEGA Instant Playable</h1><p id="status" aria-live="polite"></p>
<canvas id="game" width="800" height="600" aria-label="Podgląd gry"></canvas>
<div class="controls"><button data-key="ArrowLeft">◀</button><button data-key="ArrowUp">▲</button><button data-key="ArrowDown">▼</button><button data-key="ArrowRight">▶</button></div>
<script>
'use strict';
const world=JSON.parse(new TextDecoder().decode(Uint8Array.from(atob('${encoded}'),c=>c.charCodeAt(0))));
const canvas=document.getElementById('game'),ctx=canvas.getContext('2d'),status=document.getElementById('status');
const objects=world.objects.map(o=>({...o,active:true})),player=objects.find(o=>o.role==='player');
const keys=new Set();let last=0,score=0;
function overlap(a,b){return a.x<b.x+b.width&&a.x+a.width>b.x&&a.y<b.y+b.height&&a.y+a.height>b.y;}
function update(dt){
 const dx=Number(keys.has('ArrowRight')||keys.has('d'))-Number(keys.has('ArrowLeft')||keys.has('a'));
 const dy=Number(keys.has('ArrowDown')||keys.has('s'))-Number(keys.has('ArrowUp')||keys.has('w'));
 const length=Math.hypot(dx,dy)||1;
 const oldX=player.x,oldY=player.y;
 player.x=Math.max(0,Math.min(800-player.width,player.x+dx/length*player.speed*dt));
 player.y=Math.max(0,Math.min(600-player.height,player.y+dy/length*player.speed*dt));
 for(const o of objects)if(o!==player&&o.active&&overlap(player,o)){
  if(o.role==='obstacle'){player.x=oldX;player.y=oldY;}
  if(o.role==='collectible'){o.active=false;score++;}
 }
 status.textContent=world.scene+' — punkty: '+score+' / '+objects.filter(o=>o.role==='collectible').length;
}
function draw(){
 ctx.clearRect(0,0,800,600);
 ctx.fillStyle='#151d29';ctx.fillRect(0,0,800,600);
 for(const o of objects)if(o.active){
  ctx.fillStyle=o.role==='player'?'#d4af37':o.role==='collectible'?'#2a7b62':'#b8333a';
  ctx.fillRect(o.x,o.y,o.width,o.height);
  ctx.fillStyle='#fff';ctx.font='12px sans-serif';ctx.fillText(o.name,o.x,o.y-5);
 }
}
function frame(now){const dt=Math.min((now-last)/1000||0,0.05);last=now;update(dt);draw();requestAnimationFrame(frame);}
const allowed=new Set(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','w','a','s','d']);
document.addEventListener('keydown',e=>{if(allowed.has(e.key)){e.preventDefault();keys.add(e.key);}});
document.addEventListener('keyup',e=>keys.delete(e.key));
for(const b of document.querySelectorAll('button[data-key]')){
 const key=b.dataset.key;
 b.addEventListener('pointerdown',e=>{e.preventDefault();keys.add(key);b.setPointerCapture(e.pointerId);});
 for(const name of ['pointerup','pointercancel','lostpointercapture'])b.addEventListener(name,()=>keys.delete(key));
}
requestAnimationFrame(frame);
</script></body></html>`;
 return {html,sha256:createHash('sha256').update(html).digest('hex'),sceneId:scene.id,entityCount:objects.length,format:'html'};
}
