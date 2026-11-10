import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {parseGgufHeader, hfUrl, analyzeWorkflow, modelSettings, highlightCode}=require('../android/app/src/main/assets/app.js');

function gguf(){
  const enc=new TextEncoder();const name=enc.encode('Tiny');const key=enc.encode('general.name');
  const buf=new ArrayBuffer(4+4+8+8+8+key.length+4+8+name.length);
  const d=new DataView(buf);const u=new Uint8Array(buf);let p=0;
  for(const c of 'GGUF')u[p++]=c.charCodeAt(0);
  d.setUint32(p,3,true);p+=4;d.setBigUint64(p,0n,true);p+=8;d.setBigUint64(p,1n,true);p+=8;
  d.setBigUint64(p,BigInt(key.length),true);p+=8;u.set(key,p);p+=key.length;
  d.setUint32(p,8,true);p+=4;d.setBigUint64(p,BigInt(name.length),true);p+=8;u.set(name,p);
  return buf;
}
test('reads GGUF metadata from browser buffer',()=>{
  const v=parseGgufHeader(gguf());assert.equal(v.version,3);assert.equal(v.metadata['general.name'],'Tiny');
});
test('rejects truncated GGUF',()=>assert.throws(()=>parseGgufHeader(new Uint8Array([71,71,85,70]).buffer)));
test('rejects malicious Hugging Face paths',()=>{
  assert.match(hfUrl('org/model','main','model.gguf'),/^https:\/\/huggingface.co\//);
  assert.throws(()=>hfUrl('org/model','../main','x.gguf'));
  assert.throws(()=>hfUrl('org/model','main','../secret.gguf'));
  assert.throws(()=>hfUrl('https://evil.com/model','main','x.gguf'));
});
test('parses a simple workflow outline without executing it',()=>{
  const p=analyzeWorkflow('name: CI\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n  build:\n    needs: test\n    steps:\n      - run: true');
  assert.deepEqual(p.jobs,['test','build']);assert.equal(p.steps,2);
});
test('validates model parameters and rejects NaN',()=>{
  assert.equal(modelSettings({context:'4096',threads:'4',temperature:'0.7'}).context,4096);
  assert.throws(()=>modelSettings({context:'0'}));assert.throws(()=>modelSettings({temperature:'NaN'}));
});
test('escapes untrusted source in syntax highlighter',()=>{
  const h=highlightCode('<script>alert(1)</script>','python');
  assert.ok(!h.includes('<script>'));assert.ok(h.includes('&lt;'));
});
test('provider catalog exposes only well-formed registered endpoints',()=>{
  const {normalizeProviderCatalog}=require('../android/app/src/main/assets/app.js');
  const payload=JSON.parse(require('node:fs').readFileSync(new URL('../android/app/src/main/assets/providers.json',import.meta.url)));
  const providers=normalizeProviderCatalog(payload);
  assert.ok(providers.length>=20);
  assert.ok(providers.some(x=>x.id==='gemini'));
  assert.throws(()=>normalizeProviderCatalog({version:1,providers:[{id:'evil',title:'evil',endpoint:'http://169.254.169.254/metadata',remote:true,secret_name:'EVIL_API_KEY'}]}));
});
