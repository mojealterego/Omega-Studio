/** OMEGA cinematic branching narrative core. Deterministic, engine-agnostic,
 * suitable for Android touch UI and offline save-state serialization.
 * Original story data only; no copyrighted game content.
 */
const ID=/^[A-Za-z][A-Za-z0-9_-]{0,95}$/;
const own=(obj,key)=>Object.prototype.hasOwnProperty.call(obj,key);
const fail=(message)=>{throw new Error(message);};
function validateStory(story){
 if(!story||!ID.test(story.id)||!ID.test(story.start)||!Array.isArray(story.scenes)||story.scenes.length===0||story.scenes.length>2000)fail('INVALID_STORY');
 const byId=new Map();
 for(const scene of story.scenes){
  if(!scene||!ID.test(scene.id)||byId.has(scene.id)||typeof scene.text!=='string'||scene.text.length>10000||!Array.isArray(scene.choices)||scene.choices.length>32)fail('INVALID_SCENE');
  const choices=new Set();
  for(const choice of scene.choices){
   if(!choice||!ID.test(choice.id)||choices.has(choice.id)||!ID.test(choice.to)||typeof choice.label!=='string'||choice.label.length>512||
   (choice.requires!==undefined&&(!Array.isArray(choice.requires)||choice.requires.some(r=>!r||!ID.test(r.flag)||typeof r.equals!=='boolean')))||
   (choice.effects!==undefined&&(!Array.isArray(choice.effects)||choice.effects.some(e=>!e||!ID.test(e.flag)||typeof e.value!=='boolean')))||
   (choice.timeoutMs!==undefined&&(!Number.isSafeInteger(choice.timeoutMs)||choice.timeoutMs<1000||choice.timeoutMs>600000)))fail('INVALID_CHOICE');
   choices.add(choice.id);
  }
  byId.set(scene.id,scene);
 }
 if(!byId.has(story.start))fail('MISSING_START');
 for(const scene of story.scenes)for(const choice of scene.choices)if(!byId.has(choice.to))fail('MISSING_TARGET');
 return byId;
}
const clone=value=>JSON.parse(JSON.stringify(value));
export class CinematicNarrativeRuntime{
 constructor(story,save){
  this.story=clone(story);this.scenes=validateStory(this.story);
  this.state=save?clone(save):{storyId:story.id,sceneId:story.start,flags:{},history:[],revision:0};
  this.validateState();
 }
 validateState(){
  const s=this.state;
  if(!s||s.storyId!==this.story.id||!this.scenes.has(s.sceneId)||!Number.isSafeInteger(s.revision)||s.revision<0||
  !s.flags||typeof s.flags!=='object'||Array.isArray(s.flags)||!Array.isArray(s.history)||s.history.length>100000)fail('INVALID_SAVE');
  for(const [key,value] of Object.entries(s.flags))if(!ID.test(key)||typeof value!=='boolean')fail('INVALID_SAVE_FLAG');
  for(const item of s.history)if(!item||!this.scenes.has(item.sceneId)||!ID.test(item.choiceId))fail('INVALID_SAVE_HISTORY');
 }
 snapshot(){return clone(this.state);}
 view(){
  const scene=this.scenes.get(this.state.sceneId);
  return {id:scene.id,text:scene.text,revision:this.state.revision,
   choices:scene.choices.filter(c=>(c.requires??[]).every(r=>this.state.flags[r.flag]===r.equals))
    .map(c=>({id:c.id,label:c.label,timeoutMs:c.timeoutMs??null})),
   ending:scene.choices.length===0};
 }
 choose(choiceId,expectedRevision){
  if(expectedRevision!==this.state.revision)fail('REVISION_CONFLICT');
  const scene=this.scenes.get(this.state.sceneId);
  const choice=scene.choices.find(c=>c.id===choiceId);
  if(!choice||(choice.requires??[]).some(r=>this.state.flags[r.flag]!==r.equals))fail('CHOICE_NOT_AVAILABLE');
  const next=clone(this.state);
  for(const effect of choice.effects??[])next.flags[effect.flag]=effect.value;
  next.history.push({sceneId:scene.id,choiceId:choice.id});
  next.sceneId=choice.to;next.revision++;
  this.state=next;return this.view();
 }
}
