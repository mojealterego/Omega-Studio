import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { verifyAndroidBuildOutput } from '../../src/gamebuilder/AndroidBuildOutputGate.mjs';
function zip(names) {
 const local=[];const central=[];let offset=0;
 for(const name of names){
  const b=Buffer.from(name);
  const l=Buffer.alloc(30+b.length);l.writeUInt32LE(0x04034b50,0);l.writeUInt16LE(b.length,26);b.copy(l,30);
  const c=Buffer.alloc(46+b.length);c.writeUInt32LE(0x02014b50,0);c.writeUInt16LE(b.length,28);c.writeUInt32LE(offset,42);b.copy(c,46);
  local.push(l);central.push(c);offset+=l.length;
 }
 const size=central.reduce((n,b)=>n+b.length,0);
 const e=Buffer.alloc(22);e.writeUInt32LE(0x06054b50,0);e.writeUInt16LE(names.length,8);e.writeUInt16LE(names.length,10);e.writeUInt32LE(size,12);e.writeUInt32LE(offset,16);
 return Buffer.concat([...local,...central,e]);
}
async function fixture(names,fn){
 const dir=await mkdtemp(join(tmpdir(),'omega-gate-'));try{
  await writeFile(join(dir,'game.apk'),zip(names));
  return await fn({buildRoot:dir,artifactPath:'game.apk',kind:'apk'});
 }finally{await rm(dir,{recursive:true,force:true});}
}
const markers=['AndroidManifest.xml','classes.dex'];
test('verifies bytes and structural markers together',()=>fixture(markers,async opts=>{
 const result=await verifyAndroidBuildOutput(opts);
 assert.equal(result.structureVerified,true);assert.equal(result.signatureVerified,false);
 assert.match(result.sha256,/^[a-f0-9]{64}$/);assert.equal(result.evidence.length,3);
}));
test('refuses unsupported content despite valid SHA256',()=>fixture(['classes.dex'],async opts=>{
 await assert.rejects(verifyAndroidBuildOutput(opts),/MISSING_ANDROID_PACKAGE_MARKER/);
}));
test('signature requirement fails closed without verifier',()=>fixture(markers,async opts=>{
 await assert.rejects(verifyAndroidBuildOutput({...opts,requireSignature:true}),/SIGNATURE_VERIFIER_REQUIRED/);
}));
test('signature verifier must confirm valid result',()=>fixture(markers,async opts=>{
 await assert.rejects(verifyAndroidBuildOutput({...opts,requireSignature:true,signatureVerifier:async()=>({verified:false})}),/SIGNATURE_VERIFICATION_FAILED/);
}));
test('successful injected signature verifier emits evidence',()=>fixture(markers,async opts=>{
 const result=await verifyAndroidBuildOutput({...opts,requireSignature:true,signatureVerifier:async()=>({verified:true,scheme:'test-only'})});
 assert.equal(result.signatureVerified,true);assert.equal(result.signatureScheme,'test-only');
}));
test('digest mismatch is rejected before ZIP inspection',()=>fixture(markers,async opts=>{
 await assert.rejects(verifyAndroidBuildOutput({...opts,expectedSha256:'0'.repeat(64)}),/ARTIFACT_DIGEST_MISMATCH/);
}));
