/** Deterministic GAME.PDF narrative state machine; no external runtime dependencies. */
export type Flag=string|number|boolean;
export interface Character {id:string;playable:boolean;alive:boolean;relationships:Record<string,number>}
export interface Consequence {id:string;trigger:string;flags:Record<string,Flag>;relations:Array<{from:string;to:string;delta:number}>}
export interface Choice {id:string;target:string;flags:Record<string,Flag>;deferred:Consequence[]}
export interface Scene {id:string;primary:string;fallback:string;requires:Record<string,Flag>;choices:Choice[];ending:boolean}
const forbidden=new Set(['__proto__','prototype','constructor']);
function check(flags:Record<string,Flag>):void {for(const [key,value] of Object.entries(flags)){if(!key||forbidden.has(key)||!['string','number','boolean'].includes(typeof value)||(typeof value==='number'&&!Number.isFinite(value)))throw Error('INVALID_FLAG');}}
function satisfied(actual:Record<string,Flag>,required:Record<string,Flag>):boolean{return Object.entries(required).every(([key,value])=>actual[key]===value);}
export class DeterministicNarrativeEngine {
 readonly scenes=new Map<string,Scene>();
 readonly characters=new Map<string,Character>();
 flags:Record<string,Flag>=Object.create(null);
 pending:Consequence[]=[];
 readonly timeline:string[]=[];
 addScene(scene:Scene):void{if(!scene.id||this.scenes.has(scene.id))throw Error('DUPLICATE_SCENE');check(scene.requires);for(const c of scene.choices){check(c.flags);for(const d of c.deferred)check(d.flags);}this.scenes.set(scene.id,structuredClone(scene));}
 addCharacter(character:Character):void{if(!character.id||this.characters.has(character.id))throw Error('DUPLICATE_CHARACTER');this.characters.set(character.id,structuredClone(character));}
 private hero(scene:Scene,characters=this.characters):string{const p=characters.get(scene.primary);if(p?.alive&&p.playable)return p.id;const f=characters.get(scene.fallback);if(f?.alive&&f.playable)return f.id;throw Error('NO_PLAYABLE_HERO');}
 enter(id:string):string{const scene=this.scenes.get(id);if(!scene)throw Error('MISSING_SCENE');if(!satisfied(this.flags,scene.requires))throw Error('SCENE_PRECONDITION');return this.hero(scene);}
 decide(sceneId:string,choiceId:string):string{
  const scene=this.scenes.get(sceneId);if(!scene)throw Error('MISSING_SCENE');this.enter(sceneId);
  const choice=scene.choices.find(c=>c.id===choiceId);if(!choice)throw Error('MISSING_CHOICE');
  check(choice.flags);for(const d of choice.deferred)check(d.flags);
  const target=this.scenes.get(choice.target);if(!target)throw Error('MISSING_TARGET');
  const flags:Record<string,Flag>={...this.flags,...choice.flags};
  const pending=[...this.pending,...choice.deferred];
  const triggered=pending.filter(d=>d.trigger===target.id);
  for(const d of triggered)Object.assign(flags,d.flags);
  if(!satisfied(flags,target.requires))throw Error('SCENE_PRECONDITION');
  const characters=new Map([...this.characters].map(([id,c])=>[id,structuredClone(c)]));
  for(const d of triggered)for(const r of d.relations){if(!Number.isFinite(r.delta))throw Error('INVALID_RELATION');const c=characters.get(r.from);if(c)c.relationships[r.to]=Math.max(-100,Math.min(100,(c.relationships[r.to]??0)+r.delta));}
  this.hero(target,characters);
  this.flags=Object.assign(Object.create(null),flags);this.pending=pending.filter(d=>d.trigger!==target.id);
  this.characters.clear();for(const [id,c] of characters)this.characters.set(id,c);
  this.timeline.push(`${sceneId}:${choiceId}->${target.id}`);return target.id;
 }
 audit(entry:string):{consistent:boolean;endings:number;orphans:string[];errors:string[]}{
  const seen=new Set<string>();const queue=[entry];const errors:string[]=[];let endings=0;
  for(let i=0;i<queue.length;i++){const id=queue[i];if(seen.has(id))continue;seen.add(id);const s=this.scenes.get(id);if(!s){errors.push('MISSING_SCENE:'+id);continue;}if(s.ending)endings++;try{this.hero(s);}catch{errors.push('NO_PLAYABLE_HERO:'+id);}for(const c of s.choices)queue.push(c.target);}
  const orphans=[...this.scenes.keys()].filter(id=>!seen.has(id));return {consistent:errors.length===0&&orphans.length===0,endings,orphans,errors};
 }
}
