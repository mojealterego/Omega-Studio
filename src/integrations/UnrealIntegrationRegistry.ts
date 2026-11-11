/** Unreal integrations supplied by project owner; source registry, not active connections. */
export type UnrealIntegrationKind='engine-plugin'|'rql-extension'|'extension-template'|'shared-mcp-host'|'cli-library'|'agent-library';
export interface UnrealIntegration {
 readonly id:string;readonly source:string;readonly kind:UnrealIntegrationKind;
 readonly enabled:false;readonly endpoint:null;readonly approvedTools:readonly string[];
 readonly requiresEditor:boolean;readonly notes:string;
}
function make(id:string,kind:UnrealIntegrationKind,requiresEditor:boolean,notes:string):UnrealIntegration {
 return Object.freeze({id,source:'https://github.com/mojealterego/'+id,kind,enabled:false as const,endpoint:null,approvedTools:Object.freeze([]),requiresEditor,notes});
}
export const UNREAL_INTEGRATIONS:readonly UnrealIntegration[]=Object.freeze([
 make('Unreal-MCP','engine-plugin',true,'Unreal Editor plugin and bridge; runtime handshake required'),
 make('AI-Game-Dev-CLI-Core','cli-library',false,'Shared CLI core; already present in Unity registry'),
 make('GameDev-MCP-Server','shared-mcp-host',false,'Shared host for Unity and Unreal; already present in Unity registry'),
 make('mobile-ai-agents','agent-library',false,'Mobile agent workflows; not an MCP server'),
 make('Unreal-AI-Template','extension-template',true,'Extension authoring template'),
 make('Unreal-AI-PCG','rql-extension',true,'Procedural Content Generation RQL'),
 make('Unreal-AI-Niagara','rql-extension',true,'Niagara VFX; repository README appears to describe a template: inspect before enabling'),
 make('Unreal-AI-Landscape','rql-extension',true,'Landscape and terrain RQL'),
 make('Unreal-AI-GAS','rql-extension',true,'Gameplay Ability System RQL'),
 make('Unreal-AI-EnhancedInput','rql-extension',true,'Enhanced Input RQL')
]);
export function validateUnrealIntegrations():void {
 const ids=new Set<string>();
 for(const item of UNREAL_INTEGRATIONS){
  if(ids.has(item.id))throw new Error('DUPLICATE_INTEGRATION');
  ids.add(item.id);
  if(item.enabled!==false||item.endpoint!==null||item.approvedTools.length!==0)throw new Error('INSECURE_DEFAULT');
  if(item.source!=='https://github.com/mojealterego/'+item.id)throw new Error('SOURCE_MISMATCH');
 }
}
export function unrealIntegration(id:string):UnrealIntegration|undefined {return UNREAL_INTEGRATIONS.find(x=>x.id===id);}
