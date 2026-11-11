/** MCP client discovery over an injected request/notification transport.
 * No endpoint, credentials or tool permissions are inferred from a GitHub repository.
 */
export interface McpWire {
 request(method:string,params:Record<string,unknown>,signal:AbortSignal):Promise<unknown>;
 notify(method:string,params:Record<string,unknown>,signal:AbortSignal):Promise<void>;
}
export interface McpToolDescriptor {
 name:string;
 description?:string;
 inputSchema:Record<string,unknown>;
}
export interface McpSessionConfig {
 protocolVersion:string;
 clientName:string;
 clientVersion:string;
 timeoutMs:number;
 maxTools:number;
 approvedTools:readonly string[];
}
export class McpSessionError extends Error {
 constructor(readonly code:string){super(code);this.name='McpSessionError';}
}
const NAME=/^[a-zA-Z0-9_.:/-]{1,128}$/;
const hasOwn=(o:object,k:string)=>Object.prototype.hasOwnProperty.call(o,k);
function object(value:unknown):value is Record<string,unknown>{
 return value!==null&&typeof value==='object'&&!Array.isArray(value);
}
function text(value:unknown):value is string {return typeof value==='string'&&value.length>0&&value.length<=4096;}
export class McpDiscoverySession {
 private ready=false;
 private readonly approved:Set<string>;
 private readonly tools=new Map<string,McpToolDescriptor>();
 constructor(private readonly wire:McpWire,private readonly config:McpSessionConfig){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(config.protocolVersion)||!text(config.clientName)||
    !text(config.clientVersion)||!Number.isSafeInteger(config.timeoutMs)||config.timeoutMs<1||
    config.timeoutMs>300000||!Number.isSafeInteger(config.maxTools)||config.maxTools<1||
    config.maxTools>10000||config.approvedTools.some(n=>!NAME.test(n)))
    throw new McpSessionError('INVALID_CONFIG');
  this.approved=new Set(config.approvedTools);
 }
 private async invoke<T>(fn:(signal:AbortSignal)=>Promise<T>,external?:AbortSignal):Promise<T>{
  const controller=new AbortController();
  const abort=()=>controller.abort();
  external?.addEventListener('abort',abort,{once:true});
  const timer=setTimeout(abort,this.config.timeoutMs);
  try{
   if(external?.aborted)throw new McpSessionError('CANCELLED');
   return await fn(controller.signal);
  }catch(e){
   if(controller.signal.aborted)throw new McpSessionError(external?.aborted?'CANCELLED':'TIMEOUT');
   throw e;
  }finally{clearTimeout(timer);external?.removeEventListener('abort',abort);}
 }
 async initialize(signal?:AbortSignal):Promise<void>{
  if(this.ready)throw new McpSessionError('ALREADY_INITIALIZED');
  const result=await this.invoke(s=>this.wire.request('initialize',{
   protocolVersion:this.config.protocolVersion,
   capabilities:{},
   clientInfo:{name:this.config.clientName,version:this.config.clientVersion}
  },s),signal);
  if(!object(result)||result.protocolVersion!==this.config.protocolVersion||
    !object(result.serverInfo)||!text(result.serverInfo.name)||!object(result.capabilities))
    throw new McpSessionError('INVALID_INITIALIZE_RESPONSE');
  await this.invoke(s=>this.wire.notify('notifications/initialized',{},s),signal);
  this.ready=true;
 }
 async discover(signal?:AbortSignal):Promise<readonly McpToolDescriptor[]>{
  if(!this.ready)throw new McpSessionError('NOT_INITIALIZED');
  const discovered=new Map<string,McpToolDescriptor>();
  const cursors=new Set<string>();
  let cursor:string|undefined;
  for(let page=0;page<100;page++){
   const params:Record<string,unknown>={};
   if(cursor)params.cursor=cursor;
   const response=await this.invoke(s=>this.wire.request('tools/list',params,s),signal);
   if(!object(response)||!Array.isArray(response.tools))throw new McpSessionError('INVALID_TOOL_LIST');
   for(const item of response.tools){
    if(!object(item)||typeof item.name!=='string'||!NAME.test(item.name)||
      !object(item.inputSchema)||item.inputSchema.type!=='object'||
      (hasOwn(item,'description')&&typeof item.description!=='string'))
      throw new McpSessionError('INVALID_TOOL_DESCRIPTOR');
    if(discovered.has(item.name))throw new McpSessionError('DUPLICATE_TOOL');
    if(discovered.size>=this.config.maxTools)throw new McpSessionError('TOOL_LIMIT');
    if(this.approved.has(item.name))discovered.set(item.name,{
     name:item.name,
     ...(typeof item.description==='string'?{description:item.description}:{}),
     inputSchema:item.inputSchema
    });
   }
   if(response.nextCursor===undefined||response.nextCursor===null) {
    this.tools.clear();for(const [name,tool] of discovered)this.tools.set(name,tool);
    return this.listApproved();
   }
   if(!text(response.nextCursor)||cursors.has(response.nextCursor))
    throw new McpSessionError('INVALID_PAGINATION');
   cursors.add(response.nextCursor);cursor=response.nextCursor;
  }
  throw new McpSessionError('PAGE_LIMIT');
 }
 listApproved():readonly McpToolDescriptor[]{return [...this.tools.values()].map(t=>structuredClone(t));}
 isApproved(name:string):boolean{return this.ready&&this.tools.has(name);}
}
