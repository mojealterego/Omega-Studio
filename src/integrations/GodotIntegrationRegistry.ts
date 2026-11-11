/** Godot source integrations; no implicit MCP execution or native loading. */
export type GodotIntegrationKind='visual-scripting-gdextension'|'mcp-tool-template';
export interface GodotIntegration {
 readonly id:string;
 readonly source:string;
 readonly kind:GodotIntegrationKind;
 readonly enabled:false;
 readonly approvedTools:readonly string[];
 readonly endpoint:null;
 readonly compatibility:readonly {godot:string;orchestrator:string}[];
 readonly notes:string;
}
export const GODOT_INTEGRATIONS:readonly GodotIntegration[]=Object.freeze([
 Object.freeze({
  id:'godot-orchestrator',source:'https://github.com/mojealterego/godot-orchestrator',
  kind:'visual-scripting-gdextension' as const,enabled:false as const,
  approvedTools:Object.freeze([]),endpoint:null,
  compatibility:Object.freeze([
   Object.freeze({godot:'4.8.x',orchestrator:'2.6.x'}),
   Object.freeze({godot:'4.7.x',orchestrator:'2.5.x'}),
   Object.freeze({godot:'4.6.x',orchestrator:'2.4.x'})
  ]),
  notes:'Native Godot GDExtension visual scripting; not an MCP server. Check editor ABI before loading.'
 }),
 Object.freeze({
  id:'Godot-AI-Tools-Template',source:'https://github.com/mojealterego/Godot-AI-Tools-Template',
  kind:'mcp-tool-template' as const,enabled:false as const,
  approvedTools:Object.freeze([]),endpoint:null,
  compatibility:Object.freeze([]),
  notes:'C# AiToolType source-only NuGet template; requires compatible Godot-MCP host and a consumer project.'
 })
]);
export function godotIntegration(id:string):GodotIntegration|undefined {
 return GODOT_INTEGRATIONS.find(entry=>entry.id===id);
}
export function compatibleOrchestrator(godotVersion:string):string|undefined {
 const match=/^(4\.(?:6|7|8))\.(?:\d+)(?:[.-].*)?$/.exec(godotVersion);
 if(!match)return undefined;
 return GODOT_INTEGRATIONS[0].compatibility.find(item=>item.godot.startsWith(match[1]))?.orchestrator;
}
export function validateGodotIntegrations():void {
 const seen=new Set<string>();
 for(const entry of GODOT_INTEGRATIONS){
  if(seen.has(entry.id))throw new Error('DUPLICATE_INTEGRATION');
  seen.add(entry.id);
  if(entry.source!==`https://github.com/mojealterego/${entry.id}`)throw new Error('INVALID_SOURCE');
  if(entry.enabled!==false||entry.endpoint!==null||entry.approvedTools.length!==0)throw new Error('UNSAFE_DEFAULT');
 }
}
