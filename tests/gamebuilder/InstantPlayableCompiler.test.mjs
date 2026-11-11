import {test} from 'node:test';
import {strict as assert} from 'node:assert';
import {compileInstantPlayable} from '../../src/gamebuilder/InstantPlayableCompiler.mjs';
function project(){
 return {schemaVersion:1,projectId:'Demo',engine:'godot',revision:2,nodes:[
 {id:'Main',type:'scene',parentId:null,name:'Level One',properties:{}},
 {id:'Hero',type:'entity',parentId:'Main',name:'Hero',properties:{role:'player',x:80,y:80,speed:200}},
 {id:'Coin',type:'entity',parentId:'Main',name:'Coin',properties:{role:'collectible',x:180,y:80}},
 {id:'Wall',type:'entity',parentId:'Main',name:'Wall',properties:{role:'obstacle',x:250,y:80}}
 ]};
}
test('creates self-contained playable HTML',()=>{
 const result=compileInstantPlayable(project());
 assert.equal(result.format,'html');assert.equal(result.entityCount,3);
 assert.match(result.html,/<canvas/);assert.match(result.html,/requestAnimationFrame/);
 assert.match(result.sha256,/^[a-f0-9]{64}$/);
});
test('same project produces deterministic HTML',()=>{
 assert.equal(compileInstantPlayable(project()).sha256,compileInstantPlayable(project()).sha256);
});
test('requires exactly one player',()=>{
 const p=project();p.nodes=p.nodes.filter(n=>n.id!=='Hero');
 assert.throws(()=>compileInstantPlayable(p),/PLAYER_REQUIRED/);
});
test('rejects multiple players',()=>{
 const p=project();p.nodes.find(n=>n.id==='Coin').properties.role='player';
 assert.throws(()=>compileInstantPlayable(p),/EXACTLY_ONE_PLAYER_REQUIRED/);
});
test('rejects missing scene',()=>{
 assert.throws(()=>compileInstantPlayable(project(),{sceneId:'Missing'}),/SCENE_NOT_FOUND/);
});
test('rejects unsafe property keys',()=>{
 const p=project();p.nodes[1].properties=JSON.parse('{"__proto__":"attack"}');
 assert.throws(()=>compileInstantPlayable(p),/INVALID_PROPERTY/);
});
test('escapes untrusted scene text by base64 encoding',()=>{
 const p=project();p.nodes[0].name='</script><script>alert(1)</script>';
 const result=compileInstantPlayable(p);
 assert.equal(result.html.includes('</script><script>alert(1)</script>'),false);
});
test('rejects orphan nodes',()=>{
 const p=project();p.nodes[1].parentId='Unknown';
 assert.throws(()=>compileInstantPlayable(p),/MISSING_PARENT/);
});
