/** OMEGA Studio Ultimate x GAME — deterministic game DNA and fail-closed QA. */
export interface GameDna { projectId:string; title:string; coreTheme:string; genres:string[]; playableHeroesCount:number; targetEndingsCount:number; targetPlatforms:string[] }
export interface Agent { code:string; subsystem:string }
export interface SceneObject { instanceId:string; name:string; position:[number,number,number]; components:Array<{type:string;properties:Record<string,unknown>}> }
export interface Certificate { assetId:string; commercialUseAllowed:boolean }
export interface QaResult { passed:boolean; failures:string[]; healingAgents:string[]; signedArtifacts:string[] }
const SAFE_ID=/^[A-Za-z0-9_-]{1,96}$/;
function requireValid(value:unknown,message:string):asserts value { if(!value) throw new Error(message); }
function hash(value:string):string {
  let n=0x811c9dc5;
  for(const byte of new TextEncoder().encode(value)){ n^=byte; n=Math.imul(n,0x01000193)>>>0; }
  return n.toString(16).padStart(8,'0');
}
function jsonSafe(value:unknown,depth=0):void {
  requireValid(depth<=16,'Scene nesting limit');
  if(value===null||typeof value==='string'||typeof value==='boolean')return;
  if(typeof value==='number'){requireValid(Number.isFinite(value),'Nonfinite scene number');return;}
  if(Array.isArray(value)){requireValid(value.length<=2048,'Scene array limit');for(const x of value)jsonSafe(x,depth+1);return;}
  requireValid(typeof value==='object','Unsupported scene property');
  const keys=Object.keys(value);
  requireValid(keys.length<=2048,'Scene object limit');
  for(const key of keys){requireValid(!['__proto__','constructor','prototype'].includes(key),'Unsafe scene key');jsonSafe((value as Record<string,unknown>)[key],depth+1);}
}
export class UnifiedGameFactoryCore {
  readonly agents:ReadonlyMap<string,Agent>;
  constructor(){
    const registry=new Map<string,Agent>();
    for(let i=0;i<=61;i++){
      const code='A'+i.toString().padStart(2,'0');
      const subsystem=i<=9?'Research':i<=21?'Narrative':i<=34?'Assets3D':i<=41?'Audio':i<=49?'EngineAdapter':'SelfHealingQA';
      registry.set(code,{code,subsystem});
    }
    this.agents=registry;
  }
  generateGameDnaFromPrompt(prompt:string):GameDna {
    requireValid(typeof prompt==='string'&&prompt.trim().length>0&&prompt.length<=8192,'Invalid game prompt');
    const theme=prompt.trim().normalize('NFC');
    const horror=/horror|szpital|hospital|survival/i.test(theme);
    return {projectId:'omega-game-'+hash(theme),title:horror?'Echoes of Saint Lazarus Ward':'Omega Chronicles',coreTheme:theme,
      genres:horror?['Survival Horror','Interactive Drama']:['Action RPG','Adventure'],
      playableHeroesCount:3,targetEndingsCount:5,targetPlatforms:['android-apk','android-aab','web']};
  }
  buildUnityMcpSceneMutation(scene:SceneObject):string {
    requireValid(scene&&typeof scene==='object','Invalid scene');
    requireValid(typeof scene.instanceId==='string'&&SAFE_ID.test(scene.instanceId),'Invalid instance ID');
    requireValid(typeof scene.name==='string'&&scene.name.trim().length>0&&scene.name.length<=256,'Invalid scene name');
    requireValid(Array.isArray(scene.position)&&scene.position.length===3&&scene.position.every(Number.isFinite),'Invalid position');
    requireValid(Array.isArray(scene.components)&&scene.components.length<=128,'Invalid components');
    for(const c of scene.components){requireValid(c&&typeof c.type==='string'&&SAFE_ID.test(c.type),'Invalid component');jsonSafe(c.properties);}
    return JSON.stringify({jsonrpc:'2.0',id:'unity-scene-'+scene.instanceId,method:'tools/call',
      params:{name:'unity_scene_upsert_gameobject',arguments:{name:scene.name,position:scene.position,components:scene.components}}});
  }
  runQa(dna:GameDna,certificates:Certificate[],buildLog=''):QaResult {
    requireValid(dna&&typeof dna.projectId==='string'&&SAFE_ID.test(dna.projectId),'Invalid project ID');
    requireValid(Array.isArray(certificates),'Invalid certificates');
    const failures:string[]=[];
    if(certificates.some(c=>!c||typeof c.assetId!=='string'||!c.commercialUseAllowed))failures.push('QA14_LICENSE_OR_PROVENANCE');
    if(typeof buildLog!=='string'||buildLog.length>65536)failures.push('QA_BUILD_LOG_INVALID');
    else if(buildLog.trim())failures.push('QA_BUILD_ERROR_UNRESOLVED');
    if(!Array.isArray(dna.targetPlatforms)||dna.targetPlatforms.length===0)failures.push('QA_TARGET_PLATFORMS');
    if(!Number.isInteger(dna.playableHeroesCount)||dna.playableHeroesCount<1||!Number.isInteger(dna.targetEndingsCount)||dna.targetEndingsCount<1)failures.push('QA_GAME_DNA');
    return {passed:failures.length===0,failures,healingAgents:failures.includes('QA_BUILD_ERROR_UNRESOLVED')?['A50','A52','A55','A60']:[],signedArtifacts:[]};
  }
}
