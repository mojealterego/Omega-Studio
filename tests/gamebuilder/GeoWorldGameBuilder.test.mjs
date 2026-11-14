import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildGeoWorld } from '../../src/gamebuilder/GeoWorldCore.mjs';
import { importGeoWorldToGameBuilder } from '../../src/gamebuilder/GeoWorldGameBuilderAdapter.mjs';
import { GameBuilderProject } from '../../src/gamebuilder/GameBuilderProject.ts';

test('real GLB tiles import into existing Code/NoCode GameBuilder schema losslessly',async()=>{
  const root=await mkdtemp(join(tmpdir(),'omega-geoworld-project-'));
  try{
    const spec={schemaVersion:1,origin:{lat:49.748,lon:18.634,altMeters:285},width:9,height:9,
      tileCells:8,lodLevels:3,sampleSpacingMeters:2,maxOutputBytes:1_000_000,
      elevationsMeters:Array(81).fill(285)};
    await buildGeoWorld(spec,root,'Game01');
    for(const engine of ['godot','unity','unreal']){
      const model=await importGeoWorldToGameBuilder(root,'Game01',engine);
      assert.equal(model.nodes.length,2);
      assert.equal(model.nodes[1].properties.lod,0);
      const game=new GameBuilderProject(model);
      const serialized=game.exportCode();
      assert.deepEqual(serialized.losses,[]);
      assert.deepEqual(GameBuilderProject.importCode(serialized.source).snapshot(),model);
    }
    await assert.rejects(importGeoWorldToGameBuilder(root,'Game01','unknown'),/UNSUPPORTED_GAME_ENGINE/);
  }finally{await rm(root,{recursive:true,force:true});}
});
