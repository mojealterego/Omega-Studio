/** Policy-gated MCP JSON-RPC 2.0 gateway. Network transport is injected, never implicit. */
export type Json = null | boolean | number | string | Json[] | {[key:string]:Json};
export interface ToolPolicy {serverId:string;tools:readonly string[];maxRequestBytes:number;maxResponseBytes:number;timeoutMs:number}
export interface Transport {exchange(serverId:string,request:string,signal:AbortSignal):Promise<string>}
export interface McpResult {content?:Json;isError?:boolean;[key:string]:Json|undefined}
export class McpGatewayError extends Error {readonly code:string;constructor(code:string){super(code);this.code=code;this.name='McpGatewayError';}}
const ID=/^[a-zA-Z0-9_-]{1,80}$/;
const TOOL=/^[a-zA-Z0-9_.:/-]{1,128}$/;
function checkJson(value:unknown,depth=0):asserts value is Json {
  if(depth>24)throw new McpGatewayError('JSON_DEPTH_LIMIT');
  if(value===null||typeof value==='boolean'||typeof value==='string')return;
  if(typeof value==='number'&&Number.isFinite(value))return;
  if(Array.isArray(value)){if(value.length>4096)throw new McpGatewayError('JSON_ARRAY_LIMIT');for(const x of value)checkJson(x,depth+1);return;}
  if(typeof value==='object'){
    const keys=Object.keys(value);
    if(keys.length>4096)throw new McpGatewayError('JSON_OBJECT_LIMIT');
    for(const key of keys){
      if(key==='__proto__'||key==='prototype'||key==='constructor')throw new McpGatewayError('UNSAFE_JSON_KEY');
      checkJson((value as Record<string,unknown>)[key],depth+1);
    }
    return;
  }
  throw new McpGatewayError('INVALID_JSON_VALUE');
}
export class McpToolGateway {
  private readonly policies=new Map<string,ToolPolicy>();
  private sequence=0;
  private readonly transport:Transport;
  constructor(transport:Transport,policies:readonly ToolPolicy[]){
    this.transport=transport;
    for(const policy of policies){
      if(!ID.test(policy.serverId)||this.policies.has(policy.serverId)||policy.tools.length===0||
        policy.tools.some(t=>!TOOL.test(t))||!Number.isSafeInteger(policy.maxRequestBytes)||
        !Number.isSafeInteger(policy.maxResponseBytes)||!Number.isSafeInteger(policy.timeoutMs)||
        policy.maxRequestBytes<128||policy.maxRequestBytes>1048576||
        policy.maxResponseBytes<128||policy.maxResponseBytes>4194304||
        policy.timeoutMs<1||policy.timeoutMs>300000)throw new McpGatewayError('INVALID_POLICY');
      this.policies.set(policy.serverId,{...policy,tools:[...policy.tools]});
    }
  }
  async call(serverId:string,toolName:string,args:Json,externalSignal?:AbortSignal):Promise<McpResult>{
    const policy=this.policies.get(serverId);
    if(!policy||!policy.tools.includes(toolName))throw new McpGatewayError('TOOL_NOT_ALLOWED');
    checkJson(args);
    if(args===null||Array.isArray(args)||typeof args!=='object')throw new McpGatewayError('INVALID_ARGUMENTS');
    const id=`${serverId}-${++this.sequence}`;
    const request=JSON.stringify({jsonrpc:'2.0',id,method:'tools/call',params:{name:toolName,arguments:args}});
    if(new TextEncoder().encode(request).length>policy.maxRequestBytes)throw new McpGatewayError('REQUEST_TOO_LARGE');
    const controller=new AbortController();
    const onAbort=()=>controller.abort();
    externalSignal?.addEventListener('abort',onAbort,{once:true});
    const timer=setTimeout(()=>controller.abort(),policy.timeoutMs);
    try{
      if(externalSignal?.aborted)throw new McpGatewayError('CANCELLED');
      const raw=await this.transport.exchange(serverId,request,controller.signal);
      if(typeof raw!=='string'||new TextEncoder().encode(raw).length>policy.maxResponseBytes)throw new McpGatewayError('RESPONSE_TOO_LARGE');
      let reply:unknown;
      try{reply=JSON.parse(raw);}catch{throw new McpGatewayError('INVALID_RESPONSE_JSON');}
      checkJson(reply);
      if(!reply||typeof reply!=='object'||Array.isArray(reply))throw new McpGatewayError('INVALID_RESPONSE');
      const envelope=reply as Record<string,Json>;
      if(envelope.jsonrpc!=='2.0'||envelope.id!==id)throw new McpGatewayError('RESPONSE_ID_MISMATCH');
      if('error' in envelope)throw new McpGatewayError('REMOTE_TOOL_ERROR');
      const result=envelope.result;
      if(!result||typeof result!=='object'||Array.isArray(result))throw new McpGatewayError('INVALID_RESULT');
      return result as McpResult;
    }catch(error){
      if(controller.signal.aborted)throw new McpGatewayError(externalSignal?.aborted?'CANCELLED':'TIMEOUT');
      throw error;
    }finally{
      clearTimeout(timer);
      externalSignal?.removeEventListener('abort',onAbort);
    }
  }
}
