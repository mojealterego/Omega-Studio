import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { mkdtemp, readFile, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import {
  geodeticToEcef, ecefToGeodetic, ecefToEnu, enuToEcef,
  validateWorldSpec, makeTileMesh, encodeGlb, buildGeoWorld, verifyGeoWorld,
} from '../../src/gamebuilder/GeoWorldCore.mjs';
import { GeoWorldStageWorker } from '../../src/gamebuilder/GeoWorldStageWorker.mjs';

function sampleSpec() {
  const width=17, height=17;
  return {schemaVersion:1, origin:{lat:49.748,lon:18.634,altMeters:285},
    width,height,sampleSpacingMeters:2,tileCells:8,lodLevels:3,maxOutputBytes:2_000_000,
    elevationsMeters:Array.from({length:width*height},(_,i)=>280 + 0.2*(i%width) + 0.3*Math.floor(i/width))};
}
async function temp(fn){const root=await mkdtemp(join(tmpdir(),'omega-geocore-'));try{return await fn(root);}finally{await rm(root,{recursive:true,force:true});}}
function digest(b){return createHash('sha256').update(b).digest('hex');}

for(const [lat,lon,h] of [[0,0,0],[49.748,18.634,285],[-23.5,179.999,1200],[89.999,-72,-100]]) {
  test(`WGS84 geodetic-ECEF roundtrip ${lat}, ${lon}`,()=>{
    const xyz=geodeticToEcef(lat,lon,h);
    const llh=ecefToGeodetic(...xyz);
    assert.ok(Math.abs(llh.lat-lat)<1e-7);
    assert.ok(Math.abs(llh.lon-lon)<1e-7);
    assert.ok(Math.abs(llh.altMeters-h)<0.002);
  });
}
test('ENU-ECEF roundtrip near reference origin',()=>{
  const origin={lat:49.748,lon:18.634,altMeters:285};
  const xyz=enuToEcef(50,30,10,origin);
  const enu=ecefToEnu(...xyz,origin);
  [50,30,10].forEach((v,i)=>assert.ok(Math.abs(enu[i]-v)<1e-7));
});
test('rejects nonfinite DEM, invalid tile sizes, resource exhaustion and unsupported fields',()=>{
  const s=sampleSpec();s.elevationsMeters[0]=Infinity;
  assert.throws(()=>validateWorldSpec(s),/INVALID_ELEVATION/);
  assert.throws(()=>validateWorldSpec({...sampleSpec(),tileCells:7}),/INVALID_TILE_CELLS/);
  assert.throws(()=>validateWorldSpec({...sampleSpec(),lodLevels:5}),/INVALID_LOD_LEVELS/);
  assert.throws(()=>validateWorldSpec({...sampleSpec(),maxOutputBytes:10}),/INVALID_OUTPUT_BUDGET/);
  assert.throws(()=>validateWorldSpec({...sampleSpec(),origin:{lat:91,lon:0,altMeters:0}}),/INVALID_ORIGIN/);
  assert.throws(()=>validateWorldSpec({...sampleSpec(),url:'https://example.com'}),/UNSUPPORTED_SPEC_FIELD/);
});
test('mesh is right-handed glTF Y-up and preserves normals along shared tile seam',()=>{
  const spec=validateWorldSpec(sampleSpec());
  const left=makeTileMesh(spec,0,0,0),right=makeTileMesh(spec,0,1,0);
  assert.equal(left.vertexCount,81);
  for(let r=0;r<=8;r++){
    const a=r*9+8,b=r*9;
    for(let k=0;k<3;k++)assert.ok(Math.abs(left.normals[a*3+k]-right.normals[b*3+k])<1e-6);
    assert.ok(Math.abs(left.positions[a*3]-16)<1e-5);
    assert.ok(Math.abs(right.positions[b*3])<1e-5);
  }
  const [a,b,c]=left.indices.slice(0,3);
  const pos=i=>left.positions.slice(i*3,i*3+3);
  const A=pos(a),B=pos(b),C=pos(c);
  const ab=B.map((x,i)=>x-A[i]),ac=C.map((x,i)=>x-A[i]);
  const y=ab[2]*ac[0]-ab[0]*ac[2];
  assert.ok(y>0,'glTF triangles must face up');
});
test('GLB 2.0 header, chunk alignment, buffer lengths, JSON and PBR primitives',()=>{
  const spec=validateWorldSpec(sampleSpec());
  const mesh=makeTileMesh(spec,0,0,1),glb=encodeGlb(mesh,{east:0,north:0});
  assert.equal(glb.toString('ascii',0,4),'glTF');
  assert.equal(glb.readUInt32LE(4),2);
  assert.equal(glb.readUInt32LE(8),glb.length);
  const jsonSize=glb.readUInt32LE(12);
  assert.equal(glb.toString('ascii',16,20),'JSON');
  const gltf=JSON.parse(glb.toString('utf8',20,20+jsonSize));
  assert.equal(gltf.asset.version,'2.0');
  assert.equal(gltf.meshes[0].primitives[0].mode,4);
  assert.equal(gltf.accessors[3].count,mesh.indices.length);
  assert.equal(glb.readUInt32LE(20+jsonSize+4),0x004e4942);
  assert.equal(glb.length%4,0);
});
test('build is reproducible, validates every artifact and reuses identical project idempotently',()=>temp(async root=>{
  const spec=sampleSpec();
  const one=await buildGeoWorld(spec,root,'Geo01');
  assert.equal(one.tiles.length,12);
  assert.equal(one.originEcefMeters.length,3);
  assert.equal(one.coordinateSystem,'RH_X_EAST_Y_UP_Z_SOUTH');
  assert.equal(one.adapters.unreal.centimetersPerMeter,100);
  const checked=await verifyGeoWorld(root,'Geo01',one.specSha256);
  assert.deepEqual(checked,one);
  const again=await buildGeoWorld(spec,root,'Geo01');
  assert.deepEqual(again,one);
  const second=await buildGeoWorld(spec,root,'Geo02');
  assert.deepEqual(second.tiles.map(t=>t.sha256),one.tiles.map(t=>t.sha256));
  assert.equal(second.specSha256,one.specSha256);
  await assert.rejects(buildGeoWorld({...spec,elevationsMeters:spec.elevationsMeters.map(x=>x+1)},root,'Geo01'),/OUTPUT_SPEC_MISMATCH/);
}));
test('fail closed on corrupted GLB, path traversal, symlink and abort',()=>temp(async root=>{
  const spec=sampleSpec();
  const m=await buildGeoWorld(spec,root,'Geo01');
  const path=join(root,'Geo01',m.tiles[0].file);
  const b=await readFile(path);b[b.length-1]^=1;await writeFile(path,b);
  await assert.rejects(verifyGeoWorld(root,'Geo01'),/ARTIFACT_HASH_MISMATCH/);
  await assert.rejects(buildGeoWorld(spec,root,'../escape'),/INVALID_PROJECT_ID/);
  await symlink(join(root,'Geo01'),join(root,'GeoLink'));
  await assert.rejects(verifyGeoWorld(root,'GeoLink'),/UNSAFE_WORLD_DIRECTORY/);
  const ctrl=new AbortController();ctrl.abort();
  await assert.rejects(buildGeoWorld(spec,root,'Geo02',{signal:ctrl.signal}),/CANCELLED/);
}));
test('world stage worker issues verifiable chained receipt, rejects wrong stage and abort',()=>temp(async root=>{
  const worker=new GeoWorldStageWorker({worldSpec:sampleSpec(),outputRoot:root});
  const previous='f'.repeat(64);
  const context={projectId:'Game01',revision:4,status:'running',nextIndex:3,receipts:[{stage:'gdd',inputDigest:'e'.repeat(64),outputDigest:previous,evidence:['real']} ]};
  const receipt=await worker.execute('world',context,new AbortController().signal);
  assert.equal(receipt.stage,'world');
  assert.equal(receipt.inputDigest,previous);
  assert.match(receipt.outputDigest,/^[a-f0-9]{64}$/);
  assert.ok(receipt.evidence.some(x=>x.includes('manifest')));
  assert.equal(receipt.outputDigest,digest(await readFile(join(root,'Game01','manifest.json'))));
  assert.equal((await verifyGeoWorld(root,'Game01')).tiles.length,12);
  await assert.rejects(worker.execute('code',context,new AbortController().signal),/UNSUPPORTED_FACTORY_STAGE/);
  const abort=new AbortController();abort.abort();
  await assert.rejects(worker.execute('world',context,abort.signal),/CANCELLED/);
}));
test('output budget failure removes staging and never publishes partial project',()=>temp(async root=>{
  const spec={...sampleSpec(),maxOutputBytes:1024};
  await assert.rejects(buildGeoWorld(spec,root,'TooLarge'),/OUTPUT_BUDGET_EXCEEDED/);
  const {readdir}=await import('node:fs/promises');
  assert.deepEqual(await readdir(root),[]);
}));
test('corrupt manifest and unexpected file block reusing existing world',()=>temp(async root=>{
  const spec=sampleSpec();
  await buildGeoWorld(spec,root,'Geo01');
  await writeFile(join(root,'Geo01','rogue.glb'),'malicious');
  await assert.rejects(verifyGeoWorld(root,'Geo01'),/WORLD_FILE_SET_MISMATCH/);
  await assert.rejects(buildGeoWorld(spec,root,'Geo01'),/WORLD_FILE_SET_MISMATCH/);
}));
test('pole geodesy and invalid ECEF origin are explicitly handled',()=>{
  assert.deepEqual(ecefToGeodetic(0,0,6356752.314245179),{lat:90,lon:0,altMeters:0});
  assert.throws(()=>ecefToGeodetic(0,0,0),/ECEF_AT_EARTH_CENTER/);
  assert.throws(()=>geodeticToEcef(0,NaN,0),/INVALID_ORIGIN/);
});
test('DEM elevation is referenced to WGS84 ellipsoidal origin altitude, not double-counted',()=>{
  const s=sampleSpec();s.elevationsMeters.fill(s.origin.altMeters);
  const mesh=makeTileMesh(s,0,0,0);
  for(let i=1;i<mesh.positions.length;i+=3)assert.equal(mesh.positions[i],0);
});
test('deterministic geodetic-ECEF property sweep across both hemispheres',()=>{
  let seed=20261114;
  const rand=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
  for(let i=0;i<250;i++){
    const lat=-89.5+179*rand(),lon=-180+360*rand(),alt=-500+10000*rand();
    const back=ecefToGeodetic(...geodeticToEcef(lat,lon,alt));
    assert.ok(Math.abs(back.lat-lat)<1e-8);
    assert.ok(Math.abs(back.lon-lon)<1e-8);
    assert.ok(Math.abs(back.altMeters-alt)<0.002);
  }
});
