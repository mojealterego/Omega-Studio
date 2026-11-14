import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { FACTORY_STAGES, FactoryRunner, InMemoryFactoryStore } from '../../src/gamebuilder/FactoryPipeline.ts';
import { GeoWorldStageWorker } from '../../src/gamebuilder/GeoWorldStageWorker.mjs';
import { verifyGeoWorld } from '../../src/gamebuilder/GeoWorldCore.mjs';

const hash=s=>createHash('sha256').update(s).digest('hex');
const worldSpec=()=>({schemaVersion:1,origin:{lat:49.748,lon:18.634,altMeters:285},width:9,height:9,
  tileCells:8,lodLevels:3,sampleSpacingMeters:2,maxOutputBytes:1_000_000,
  elevationsMeters:Array.from({length:81},(_,i)=>280+i%9)});

test('actual FactoryRunner executes real deterministic world worker and chains receipts',async()=>{
  const root=await mkdtemp(join(tmpdir(),'omega-factory-geoworld-'));
  try{
    const store=new InMemoryFactoryStore();
    const workers={};
    for(const stage of FACTORY_STAGES){
      if(stage==='world'){workers[stage]=new GeoWorldStageWorker({worldSpec:worldSpec(),outputRoot:root});continue;}
      workers[stage]={async execute(name,state){
        const previous=state.receipts.at(-1)?.outputDigest??hash('input:Game01');
        const result={stage:name,inputDigest:previous,outputDigest:hash(previous+':'+name),evidence:['SIMULATED_OTHER_STAGE']};
        if(name==='build'||name==='release')result.artifact={kind:'web',uri:'simulation://not-a-real-build',sha256:hash('simulation'),bytes:1};
        return result;
      }};
    }
    const runner=new FactoryRunner(store,workers);
    await runner.create('Game01');
    const state=await runner.run('Game01',new AbortController().signal);
    assert.equal(state.status,'succeeded');
    assert.equal(state.receipts.length,16);
    const receipt=state.receipts.find(r=>r.stage==='world');
    assert.equal(receipt.inputDigest,state.receipts[2].outputDigest);
    assert.equal((await verifyGeoWorld(root,'Game01')).tiles.length,3);
    assert.ok(receipt.evidence[0].includes('manifest'));
    // Only world stage is real; all other workers are intentionally simulated.
  }finally{await rm(root,{recursive:true,force:true});}
});
