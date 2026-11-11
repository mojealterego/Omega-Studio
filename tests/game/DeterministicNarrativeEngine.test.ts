import {strict as assert} from 'node:assert';
import {test} from 'node:test';
import {DeterministicNarrativeEngine} from '../../src/game/DeterministicNarrativeEngine';
function make(){
 const e=new DeterministicNarrativeEngine();
 for(const id of ['hero','backup'])e.addCharacter({id,alive:true,playable:true,relationships:{}});
 e.addScene({id:'start',primary:'hero',fallback:'backup',requires:{},ending:false,choices:[{id:'go',target:'end',flags:{gate:true},deferred:[{id:'d',trigger:'end',flags:{resolved:true},relations:[{from:'hero',to:'backup',delta:150}]}]}]});
 e.addScene({id:'end',primary:'hero',fallback:'backup',requires:{gate:true},ending:true,choices:[]});
 return e;
}
test('decision commits deferred effects and clamps relationships',()=>{const e=make();assert.equal(e.decide('start','go'),'end');assert.equal(e.flags.resolved,true);assert.equal(e.characters.get('hero')?.relationships.backup,100);assert.equal(e.pending.length,0);});
test('dead primary falls back to living playable character',()=>{const e=make();e.characters.get('hero')!.alive=false;assert.equal(e.enter('start'),'backup');});
test('invalid choice does not change state',()=>{const e=make();assert.throws(()=>e.decide('start','absent'));assert.equal(e.timeline.length,0);assert.equal(e.flags.gate,undefined);});
test('missing target does not commit',()=>{const e=make();e.scenes.delete('end');assert.throws(()=>e.decide('start','go'));assert.equal(e.flags.gate,undefined);});
test('continuity audit detects missing target',()=>{const e=make();e.scenes.delete('end');assert.equal(e.audit('start').consistent,false);});
test('continuity audit counts reachable ending',()=>{const e=make();assert.equal(e.audit('start').endings,1);});
test('unsafe world flag rejected',()=>{const e=make();e.scenes.get('start')!.choices[0].flags=JSON.parse('{"__proto__":true}');assert.throws(()=>e.decide('start','go'),/INVALID_FLAG/);});
test('duplicate scene rejected',()=>{const e=make();assert.throws(()=>e.addScene(e.scenes.get('start')!));});
