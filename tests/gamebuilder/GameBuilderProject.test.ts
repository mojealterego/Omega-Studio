import {strict as assert} from 'node:assert';
import {test} from 'node:test';
import {GameBuilderProject,validateProject,type Project} from '../../src/gamebuilder/GameBuilderProject';
function fixture():GameBuilderProject {
 return new GameBuilderProject({schemaVersion:1,projectId:'Demo',engine:'godot',revision:0,
 nodes:[{id:'Root',type:'scene',parentId:null,name:'Main',properties:{}},
 {id:'Hero',type:'entity',parentId:'Root',name:'Hero',properties:{hp:100}}]});
}
test('exports and imports identical declarative code',()=>{
 const original=fixture();const converted=original.exportCode();
 assert.deepEqual(GameBuilderProject.importCode(converted.source).snapshot(),original.snapshot());
 assert.deepEqual(converted.losses,[]);
});
test('updates properties and increments revision',()=>{
 const p=fixture();const s=p.apply({kind:'update',id:'Hero',properties:{hp:80},expectedRevision:0});
 assert.equal(s.nodes[1].properties.hp,80);assert.equal(s.revision,1);
});
test('rejects stale concurrent revision',()=>{
 const p=fixture();p.apply({kind:'rename',id:'Hero',name:'Knight',expectedRevision:0});
 assert.throws(()=>p.apply({kind:'rename',id:'Hero',name:'Mage',expectedRevision:0}),/REVISION_CONFLICT/);
});
test('invalid mutation rolls back atomically',()=>{
 const p=fixture();assert.throws(()=>p.apply({kind:'move',id:'Root',parentId:'Hero',expectedRevision:0}));
 assert.equal(p.snapshot().revision,0);assert.equal(p.snapshot().nodes[0].parentId,null);
});
test('detects parent cycles',()=>{
 const p=fixture();p.apply({kind:'add',node:{id:'Child',type:'entity',parentId:'Hero',name:'Child',properties:{}},expectedRevision:0});
 assert.throws(()=>p.apply({kind:'move',id:'Hero',parentId:'Child',expectedRevision:1}),/PARENT_CYCLE/);
});
test('removing a node also removes descendants',()=>{
 const p=fixture();const s=p.apply({kind:'remove',id:'Root',expectedRevision:0});
 assert.equal(s.nodes.length,0);
});
test('undo restores content with monotonically increasing revision',()=>{
 const p=fixture();p.apply({kind:'rename',id:'Hero',name:'Knight',expectedRevision:0});
 const s=p.undo(1);assert.equal(s.nodes[1].name,'Hero');assert.equal(s.revision,2);
});
test('refuses arbitrary TypeScript execution on import',()=>{
 assert.throws(()=>GameBuilderProject.importCode('process.exit(1)'),/UNSUPPORTED_CODE_FORMAT/);
});
test('rejects malicious property keys',()=>{
 const p=fixture();assert.throws(()=>p.apply({kind:'update',id:'Hero',properties:JSON.parse('{"__proto__":true}'),expectedRevision:0}),/INVALID_PROPERTY/);
});
test('rejects orphan nodes',()=>{
 const p=fixture();assert.throws(()=>p.apply({kind:'add',node:{id:'Orphan',type:'entity',parentId:'Missing',name:'Orphan',properties:{}},expectedRevision:0}),/MISSING_PARENT/);
});
test('snapshots are isolated from mutation',()=>{
 const p=fixture();const s=p.snapshot();s.nodes[0].name='Mutated';assert.equal(p.snapshot().nodes[0].name,'Main');
});
test('validates supported engines',()=>{
 const p=fixture().snapshot();(p as any).engine='unknown';assert.throws(()=>validateProject(p),/INVALID_PROJECT/);
});
