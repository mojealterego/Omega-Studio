/** GAME.PDF execution layer: resumable, fail-closed Factory Core workflow.
 * Workers are injected; a successful build requires a verified artifact receipt.
 */
export type FactoryStage='research'|'game-dna'|'gdd'|'world'|'mechanics'|'code'|'assets'|'audio'|'animation'|'cinematics'|'prototype'|'playtest'|'qa'|'optimization'|'build'|'release';
export const FACTORY_STAGES:readonly FactoryStage[]=['research','game-dna','gdd','world','mechanics','code','assets','audio','animation','cinematics','prototype','playtest','qa','optimization','build','release'] as const;
export type FactoryStatus='pending'|'running'|'succeeded'|'failed'|'paused';
export interface StageReceipt {
 stage:FactoryStage;
 inputDigest:string;
 outputDigest:string;
 evidence:string[];
 artifact?:{kind:'apk'|'aab'|'web'|'desktop';uri:string;sha256:string;bytes:number};
}
export interface FactoryState {
 projectId:string;
 revision:number;
 status:FactoryStatus;
 nextIndex:number;
 receipts:StageReceipt[];
 lastError?:string;
}
export interface FactoryWorker {
 execute(stage:FactoryStage,context:Readonly<FactoryState>,signal:AbortSignal):Promise<StageReceipt>;
}
export interface StateStore {
 load(projectId:string):Promise<FactoryState|null>;
 save(state:FactoryState,expectedRevision:number):Promise<void>;
}
const DIGEST=/^[a-fA-F0-9]{64}$/;
const PROJECT=/^[a-zA-Z][a-zA-Z0-9_-]{0,95}$/;
function verify(receipt:StageReceipt,stage:FactoryStage):void {
 if(!receipt||receipt.stage!==stage||!DIGEST.test(receipt.inputDigest)||!DIGEST.test(receipt.outputDigest)||
 !Array.isArray(receipt.evidence)||receipt.evidence.length===0||
 receipt.evidence.some(e=>typeof e!=='string'||e.length<1||e.length>4096))throw Error('INVALID_STAGE_RECEIPT');
 if(stage==='build'||stage==='release'){
  if(!receipt.artifact||!['apk','aab','web','desktop'].includes(receipt.artifact.kind)||
  !receipt.artifact.uri||!DIGEST.test(receipt.artifact.sha256)||
  !Number.isSafeInteger(receipt.artifact.bytes)||receipt.artifact.bytes<1)throw Error('MISSING_BUILD_ARTIFACT');
 }
}
export class FactoryRunner {
 constructor(private readonly store:StateStore,private readonly workers:Partial<Record<FactoryStage,FactoryWorker>>){}
 async create(projectId:string):Promise<FactoryState>{
  if(!PROJECT.test(projectId))throw Error('INVALID_PROJECT_ID');
  if(await this.store.load(projectId))throw Error('PROJECT_EXISTS');
  const state:FactoryState={projectId,revision:0,status:'pending',nextIndex:0,receipts:[]};
  await this.store.save(state,-1);return structuredClone(state);
 }
 async run(projectId:string,signal:AbortSignal):Promise<FactoryState>{
  if(signal.aborted)throw Error('CANCELLED');
  const initial=await this.store.load(projectId);
  if(!initial)throw Error('PROJECT_NOT_FOUND');
  if(initial.status==='running')throw Error('ALREADY_RUNNING');
  if(initial.status==='succeeded')return structuredClone(initial);
  let state=initial;
  while(state.nextIndex<FACTORY_STAGES.length){
   if(signal.aborted){state=await this.transition(state,{status:'paused'});break;}
   const stage=FACTORY_STAGES[state.nextIndex];
   const worker=this.workers[stage];
   if(!worker){state=await this.transition(state,{status:'failed',lastError:'WORKER_UNAVAILABLE:'+stage});break;}
   state=await this.transition(state,{status:'running',lastError:undefined});
   let receipt:StageReceipt;
   try{
    receipt=await worker.execute(stage,structuredClone(state),signal);
    verify(receipt,stage);
    if(state.receipts.length&&receipt.inputDigest!==state.receipts[state.receipts.length-1].outputDigest)
     throw Error('INPUT_DIGEST_MISMATCH');
   }catch(error){
    const message=signal.aborted?'CANCELLED':error instanceof Error?error.message:'UNKNOWN_ERROR';
    state=await this.transition(state,{status:signal.aborted?'paused':'failed',lastError:message});break;
   }
   state=await this.transition(state,{status:'pending',nextIndex:state.nextIndex+1,receipts:[...state.receipts,structuredClone(receipt)],lastError:undefined});
  }
  if(state.nextIndex===FACTORY_STAGES.length&&state.status!=='succeeded')
   state=await this.transition(state,{status:'succeeded'});
  return structuredClone(state);
 }
 private async transition(previous:FactoryState,patch:Partial<FactoryState>):Promise<FactoryState>{
  const next={...previous,...patch,revision:previous.revision+1};
  await this.store.save(next,previous.revision);return next;
 }
}
/** Development/test store. Production must use a durable transactional StateStore. */
export class InMemoryFactoryStore implements StateStore {
 private readonly data=new Map<string,FactoryState>();
 async load(id:string):Promise<FactoryState|null>{const state=this.data.get(id);return state?structuredClone(state):null;}
 async save(state:FactoryState,expectedRevision:number):Promise<void>{
  const current=this.data.get(state.projectId);
  if((current?.revision??-1)!==expectedRevision)throw Error('OPTIMISTIC_LOCK_CONFLICT');
  this.data.set(state.projectId,structuredClone(state));
 }
}
