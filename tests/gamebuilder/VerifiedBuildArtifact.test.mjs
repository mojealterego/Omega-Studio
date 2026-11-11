import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { mkdtemp, writeFile, symlink, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { verifyBuildArtifact } from '../../src/gamebuilder/VerifiedBuildArtifact.mjs';
async function sandbox(fn) { const root = await mkdtemp(join(tmpdir(),'omega-build-')); try { return await fn(root); } finally { await rm(root,{recursive:true,force:true}); } }
test('verifies real APK bytes',()=>sandbox(async root=>{const data=Buffer.from('PK\x03\x04fixture');await writeFile(join(root,'game.apk'),data);const r=await verifyBuildArtifact({buildRoot:root,artifactPath:'game.apk',kind:'apk'});assert.equal(r.sha256,createHash('sha256').update(data).digest('hex'));assert.equal(r.bytes,data.length);assert.equal(r.verified,true);}));
test('verifies AAB',()=>sandbox(async root=>{await writeFile(join(root,'game.aab'),'test');assert.equal((await verifyBuildArtifact({buildRoot:root,artifactPath:'game.aab',kind:'aab'})).kind,'aab');}));
test('rejects digest mismatch',()=>sandbox(async root=>{await writeFile(join(root,'game.apk'),'test');await assert.rejects(verifyBuildArtifact({buildRoot:root,artifactPath:'game.apk',kind:'apk',expectedSha256:'0'.repeat(64)}),/ARTIFACT_DIGEST_MISMATCH/);}));
test('rejects traversal',()=>sandbox(async root=>{await assert.rejects(verifyBuildArtifact({buildRoot:root,artifactPath:'../outside.apk',kind:'apk'}),/PATH_OUTSIDE_BUILD_ROOT/);}));
test('rejects external symlink',()=>sandbox(async root=>{const outside=await mkdtemp(join(tmpdir(),'omega-out-'));try{await writeFile(join(outside,'x.apk'),'test');await symlink(join(outside,'x.apk'),join(root,'link.apk'));await assert.rejects(verifyBuildArtifact({buildRoot:root,artifactPath:'link.apk',kind:'apk'}),/SYMLINK_OUTSIDE_BUILD_ROOT/);}finally{await rm(outside,{recursive:true,force:true});}}));
test('rejects empty artifact',()=>sandbox(async root=>{await writeFile(join(root,'empty.apk'),'');await assert.rejects(verifyBuildArtifact({buildRoot:root,artifactPath:'empty.apk',kind:'apk'}),/INVALID_ARTIFACT_FILE/);}));
test('rejects wrong extension',()=>sandbox(async root=>{await assert.rejects(verifyBuildArtifact({buildRoot:root,artifactPath:'game.zip',kind:'apk'}),/INVALID_ARTIFACT_PATH/);}));
test('rejects missing file',()=>sandbox(async root=>{await assert.rejects(verifyBuildArtifact({buildRoot:root,artifactPath:'missing.apk',kind:'apk'}));}));
