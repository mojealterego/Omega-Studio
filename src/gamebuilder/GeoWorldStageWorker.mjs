/** Real deterministic 'world' stage adapter for existing OMEGA FactoryRunner contract. */
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import { open } from 'node:fs/promises';
import { constants } from 'node:fs';
import { buildGeoWorld, verifyGeoWorld } from './GeoWorldCore.mjs';

const DIGEST=/^[a-f0-9]{64}$/;
const PROJECT=/^[A-Za-z][A-Za-z0-9_-]{0,95}$/;
export class GeoWorldStageWorker {
  constructor({worldSpec,outputRoot}){
    if(!worldSpec||typeof outputRoot!=='string'||!outputRoot.trim())throw Error('INVALID_WORLD_WORKER_CONFIGURATION');
    this.worldSpec=structuredClone(worldSpec);
    this.outputRoot=outputRoot;
  }
  async execute(stage,context,signal){
    if(stage!=='world')throw Error('UNSUPPORTED_FACTORY_STAGE');
    if(signal?.aborted)throw Error('CANCELLED');
    if(!context||typeof context.projectId!=='string'||!PROJECT.test(context.projectId)||
      !Array.isArray(context.receipts))throw Error('INVALID_FACTORY_CONTEXT');
    const last=context.receipts.at(-1);
    if(!last||typeof last.outputDigest!=='string'||!DIGEST.test(last.outputDigest))
      throw Error('WORLD_STAGE_REQUIRES_PREVIOUS_DIGEST');
    const manifest=await buildGeoWorld(this.worldSpec,this.outputRoot,context.projectId,{signal});
    await verifyGeoWorld(this.outputRoot,context.projectId,manifest.specSha256);
    const handle=await open(join(this.outputRoot,context.projectId,'manifest.json'),constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);
    let bytes;try{bytes=await handle.readFile();}finally{await handle.close();}
    return {stage:'world',inputDigest:last.outputDigest,
      outputDigest:createHash('sha256').update(bytes).digest('hex'),
      evidence:[`manifest:manifest.json sha256=${createHash('sha256').update(bytes).digest('hex')}`,
        `glb_tiles=${manifest.tiles.length}; verified_spec_sha256=${manifest.specSha256}`]};
  }
}
