/** Audited source registry: repository identity is not a network MCP endpoint.
 * All entries are disabled until a transport, exact tool inventory, and operator approval exist.
 */
export type IntegrationKind='mcp-server'|'unity-extension'|'cli-core'|'agent-library'|'sdk';
export interface GameIntegration {
 readonly id:string;
 readonly repository:string;
 readonly kind:IntegrationKind;
 readonly enabled:false;
 readonly transport:'unconfigured';
 readonly trust:'unverified';
 readonly notes:string;
}
const owner='mojealterego/';
const entry=(id:string,kind:IntegrationKind,notes:string):GameIntegration=>Object.freeze({
 id,repository:'https://github.com/'+owner+id,kind,enabled:false as const,
 transport:'unconfigured' as const,trust:'unverified' as const,notes
});
export const GAME_INTEGRATIONS:readonly GameIntegration[]=Object.freeze([
 entry('Unity-MCP2','mcp-server','Unity Editor bridge; requires runtime discovery of tools and compatible server'),
 entry('AI-Game-Dev-CLI-Core','cli-core','Shared CLI core; not itself a verified MCP endpoint'),
 entry('Unity-AI-Animation','unity-extension','Unity animation MCP extension'),
 entry('Unity-AI-Timeline','unity-extension','Unity timeline MCP extension'),
 entry('Unity-AI-Tilemap','unity-extension','Unity tilemap MCP extension'),
 entry('Unity-AI-Terrain','unity-extension','Unity terrain MCP extension'),
 entry('Unity-AI-Splines','unity-extension','Unity splines MCP extension'),
 entry('Unity-AI-ProBuilder','unity-extension','Unity ProBuilder MCP extension'),
 entry('Unity-AI-ParticleSystem','unity-extension','Unity particle system MCP extension'),
 entry('Unity-AI-InputSystem','unity-extension','Unity input system MCP extension'),
 entry('Unity-AI-Navigation','unity-extension','Unity navigation MCP extension'),
 entry('Unity-AI-Cinemachine','unity-extension','Unity Cinemachine MCP extension'),
 entry('Unity-AI-Tools-Template','unity-extension','Template for authoring tools; not a server'),
 entry('GameDev-MCP-Server','mcp-server','Engine-agnostic MCP host; requires runtime setup and authentication'),
 entry('mobile-ai-agents','agent-library','Mobile development agents, skills and workflows; not an MCP server'),
 entry('unity','sdk','ElevenAgents Unity SDK; not the Unity Editor or an MCP server')
]);
export function integrationById(id:string):GameIntegration|undefined {
 return GAME_INTEGRATIONS.find(item=>item.id===id);
}
export function validateIntegrationRegistry():void {
 const seen=new Set<string>();
 for(const item of GAME_INTEGRATIONS){
  if(seen.has(item.id))throw new Error('DUPLICATE_INTEGRATION');
  seen.add(item.id);
  if(item.enabled!==false||item.transport!=='unconfigured'||item.trust!=='unverified')
   throw new Error('UNSAFE_INTEGRATION_DEFAULT');
  if(item.repository!==`https://github.com/mojealterego/${item.id}`)
   throw new Error('INVALID_INTEGRATION_SOURCE');
 }
}
