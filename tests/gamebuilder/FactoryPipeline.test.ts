import {strict as assert} from 'node:assert';
import {test} from 'node:test';
import {FactoryRunner,InMemoryFactoryStore,FACTORY_STAGES,type FactoryWorker,type FactoryStage,type StageReceipt} from '../../src/gamebuilder/FactoryPipeline';
const hash=(c:string)=>c.repeat(64);
const receipt=(stage:FactoryStage,index:number):StageReceipt=>({
 stage,inputDigest:hash(index===0?'a':String((index-1)%10)),
 outputDigest:hash(String(index%10)),evidence:['worker-log'],
 ...(['build','release'].includes(stage)?{artifact:{kind:'apk' as const,uri:'file:///build/app.apk',sha256:hash('f'),bytes:1024}}:{})
});
function workers():Partial<Record<FactoryStage,FactoryWorker>>{
 return Object.fromEntries(FACTORY_STAGES.map((stage,index)=>[stage,{async execute(){return receipt(stage,index);}}]));
}
test('full pipeline requires real stage receipts and reaches success',async()=>{
 const store=new InMemoryFactoryStore();const runner=new FactoryRunner(store,workers());await runner.create('Demo');
 const result=await runner.run('Demo',new AbortController().signal);
 assert.equal(result.status,'succeeded');assert.equal(result.receipts.length,FACTORY_STAGES.length);
 assert.equal(result.receipts.at(-1)?.artifact?.kind,'apk');
});
test('missing worker stops without claiming success',async()=>{
 const runner=new FactoryRunner(new InMemoryFactoryStore(),{});
 await runner.create('Demo');const result=await runner.run('Demo',new AbortController().signal);
 assert.equal(result.status,'failed');assert.equal(result.nextIndex,0);
 assert.match(result.lastError??'',/WORKER_UNAVAILABLE/);
});
test('failed stage can resume from checkpoint',async()=>{
 const store=new InMemoryFactoryStore();const w=workers();delete w['game-dna'];
 const runner=new FactoryRunner(store,w);await runner.create('Demo');
 const failed=await runner.run('Demo',new AbortController().signal);
 assert.equal(failed.nextIndex,1);
 const resumed=new FactoryRunner(store,workers());
 assert.equal((await resumed.run('Demo',new AbortController().signal)).status,'succeeded');
});
test('build requires verifiable artifact metadata',async()=>{
 const w=workers();w.build={async execute(){return {stage:'build',inputDigest:hash('3'),outputDigest:hash('4'),evidence:['log']};}};
 const runner=new FactoryRunner(new InMemoryFactoryStore(),w);await runner.create('Demo');
 const state=await runner.run('Demo',new AbortController().signal);
 assert.equal(state.status,'failed');assert.equal(state.nextIndex,14);
 assert.equal(state.lastError,'MISSING_BUILD_ARTIFACT');
});
test('rejects stale state writes',async()=>{
 const store=new InMemoryFactoryStore();const runner=new FactoryRunner(store,{});
 const initial=await runner.create('Demo');
 await assert.rejects(store.save(initial,-1),/OPTIMISTIC_LOCK_CONFLICT/);
});
test('cancellation does not run workers',async()=>{
 const runner=new FactoryRunner(new InMemoryFactoryStore(),workers());await runner.create('Demo');
 const controller=new AbortController();controller.abort();
 await assert.rejects(runner.run('Demo',controller.signal),/CANCELLED/);
});
