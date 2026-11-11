/** OMEGA GameBuilder: engine-neutral, reversible Code/NoCode scene model.
 * Code mode emits declarative TypeScript; importing arbitrary TS is intentionally unsupported.
 */
export type Engine='unity'|'unreal'|'godot';
export type Value=string|number|boolean|null;
export interface Node {id:string;type:'scene'|'entity'|'camera'|'light'|'trigger'|'ui';parentId:string|null;name:string;properties:Record<string,Value>}
export interface Project {schemaVersion:1;projectId:string;engine:Engine;revision:number;nodes:Node[]}
export type Command=
 |{kind:'add';node:Node;expectedRevision:number}
 |{kind:'update';id:string;properties:Record<string,Value>;expectedRevision:number}
 |{kind:'rename';id:string;name:string;expectedRevision:number}
 |{kind:'move';id:string;parentId:string|null;expectedRevision:number}
 |{kind:'remove';id:string;expectedRevision:number};
export interface Conversion {source:string;losses:string[];revision:number}
const ID=/^[A-Za-z][A-Za-z0-9_-]{0,95}$/;
const ENGINES=new Set<Engine>(['unity','unreal','godot']);
const TYPES=new Set<Node['type']>(['scene','entity','camera','light','trigger','ui']);
const forbidden=new Set(['__proto__','constructor','prototype']);
function fail(message:string):never {throw new Error(message);}
function plain(value:unknown):value is Record<string,unknown> {
 return value!==null&&typeof value==='object'&&!Array.isArray(value)&&
 (Object.getPrototypeOf(value)===Object.prototype||Object.getPrototypeOf(value)===null);
}
function props(value:unknown):asserts value is Record<string,Value>{
 if(!plain(value)||Object.keys(value).length>128)fail('INVALID_PROPERTIES');
 for(const [key,v] of Object.entries(value)){
  if(!ID.test(key)||forbidden.has(key)||!(v===null||typeof v==='string'||typeof v==='boolean'||typeof v==='number'&&Number.isFinite(v))||
     typeof v==='string'&&v.length>8192)fail('INVALID_PROPERTY');
 }
}
function validName(value:unknown):value is string{return typeof value==='string'&&value.trim().length>0&&value.length<=256;}
export function validateProject(value:unknown):asserts value is Project {
 if(!plain(value)||value.schemaVersion!==1||!ID.test(String(value.projectId))||
 !ENGINES.has(value.engine as Engine)||!Number.isSafeInteger(value.revision)||Number(value.revision)<0||
 !Array.isArray(value.nodes)||value.nodes.length>10000)fail('INVALID_PROJECT');
 const ids=new Set<string>();
 for(const node of value.nodes){
  if(!plain(node)||typeof node.id!=='string'||!ID.test(node.id)||ids.has(node.id)||
  !TYPES.has(node.type as Node['type'])||!validName(node.name)||
  !(node.parentId===null||typeof node.parentId==='string'&&ID.test(node.parentId)))fail('INVALID_NODE');
  props(node.properties);ids.add(node.id);
 }
 const nodes=value.nodes as unknown as Node[];
 const byId=new Map(nodes.map(n=>[n.id,n]));
 for(const node of nodes){
  if(node.parentId!==null&&!byId.has(node.parentId))fail('MISSING_PARENT');
  if(node.type==='scene'&&node.parentId!==null)fail('SCENE_MUST_BE_ROOT');
  if(node.parentId!==null&&byId.get(node.parentId)?.type==='ui'&&node.type==='scene')fail('INVALID_HIERARCHY');
  const visited=new Set<string>();let current:Node|undefined=node;
  while(current){if(visited.has(current.id))fail('PARENT_CYCLE');visited.add(current.id);current=current.parentId===null?undefined:byId.get(current.parentId);}
 }
}
export class GameBuilderProject {
 private state:Project;
 private readonly history:Project[]=[];
 constructor(project:Project){validateProject(project);this.state=structuredClone(project);}
 snapshot():Project{return structuredClone(this.state);}
 apply(command:Command):Project {
  if(command.expectedRevision!==this.state.revision)fail('REVISION_CONFLICT');
  const draft=structuredClone(this.state);
  if(command.kind==='add'){if(draft.nodes.some(n=>n.id===command.node.id))fail('DUPLICATE_ID');draft.nodes.push(structuredClone(command.node));}
  else {
   const index=draft.nodes.findIndex(n=>n.id===command.id);
   if(index<0)fail('NODE_NOT_FOUND');
   const node=draft.nodes[index];
   switch(command.kind){
    case 'update':props(command.properties);node.properties={...node.properties,...command.properties};break;
    case 'rename':node.name=command.name;break;
    case 'move':node.parentId=command.parentId;break;
    case 'remove':{
     const removed=new Set([command.id]);let changed=true;
     while(changed){changed=false;for(const child of draft.nodes)if(child.parentId!==null&&removed.has(child.parentId)&&!removed.has(child.id)){removed.add(child.id);changed=true;}}
     draft.nodes=draft.nodes.filter(n=>!removed.has(n.id));break;
    }
   }
  }
  draft.revision++;validateProject(draft);
  this.history.push(this.state);this.state=draft;return this.snapshot();
 }
 undo(expectedRevision:number):Project {
  if(this.state.revision!==expectedRevision)fail('REVISION_CONFLICT');
  const previous=this.history.pop();if(!previous)fail('NO_UNDO');
  this.state={...structuredClone(previous),revision:this.state.revision+1};return this.snapshot();
 }
 exportCode():Conversion {
  const serialized=JSON.stringify(this.state,null,2);
  return {source:'// OMEGA-GAMEBUILDER-SCHEMA:1\nexport const gameProject = '+serialized+' as const;\n',
   losses:[],revision:this.state.revision};
 }
 static importCode(source:string):GameBuilderProject {
  const prefix='// OMEGA-GAMEBUILDER-SCHEMA:1\nexport const gameProject = ';
  const suffix=' as const;\n';
  if(!source.startsWith(prefix)||!source.endsWith(suffix)||source.length>2_000_000)fail('UNSUPPORTED_CODE_FORMAT');
  let parsed:unknown;try{parsed=JSON.parse(source.slice(prefix.length,-suffix.length));}catch{fail('INVALID_CODE_JSON');}
  validateProject(parsed);return new GameBuilderProject(parsed);
 }
}
