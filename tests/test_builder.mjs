import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const B=require('../android/app/src/main/assets/builder.js');

test('sample project is valid and Polish',()=>{
 const p=B.validate(B.sample());assert.equal(p.pages[0].title,'Strona główna');
});
test('web HTML escapes user input',()=>{
 const p=B.sample();p.pages[0].components[0].text='<img src=x onerror=alert(1)>';
 const html=B.html(p);assert.match(html,/&lt;img/);assert.doesNotMatch(html,/<img src=x/);
});
test('malicious actions are rejected',()=>{
 const p=B.sample();p.pages[0].components[3].action='javascript:alert(1)';assert.throws(()=>B.validate(p));
});
test('native Java source uses Android widgets',()=>{
 const java=B.java(B.sample());assert.match(java,/new TextView\(this\)/);assert.match(java,/new EditText\(this\)/);assert.doesNotMatch(java,/WebView/);
});
test('exports deterministic valid ZIP archive with both platforms',()=>{
 const p=B.sample();const a=B.zip(B.files(p)),b=B.zip(B.files(p));assert.deepEqual(a,b);assert.equal(Buffer.from(a).readUInt32LE(0),0x04034b50);assert.ok(a.length>2000);
});
test('web only has no native project',()=>{
 const p=B.sample();p.platform='web';assert.ok(!Object.keys(B.files(p)).some(x=>x.startsWith('android/')));
});
test('native only has no web project',()=>{
 const p=B.sample();p.platform='android';assert.ok(!Object.keys(B.files(p)).some(x=>x.startsWith('web/')));
});
test('duplicate page ids rejected',()=>{
 const p=B.sample();p.pages[1].id=p.pages[0].id;assert.throws(()=>B.validate(p));
});
