import {test} from 'node:test';
import {strict as assert} from 'node:assert';
import {CinematicNarrativeRuntime} from '../../src/gamebuilder/CinematicNarrativeRuntime.mjs';
const story={id:'OriginalThriller',start:'Station',scenes:[
 {id:'Station',text:'Na peronie leży tajemniczy telefon.',choices:[
  {id:'take',label:'Zabierz telefon',to:'Interview',effects:[{flag:'hasPhone',value:true}]},
  {id:'leave',label:'Odejdź',to:'Interview'}]},
 {id:'Interview',text:'Detektyw zadaje pytanie.',choices:[
  {id:'show',label:'Pokaż telefon',to:'Trust',requires:[{flag:'hasPhone',equals:true}]},
  {id:'hide',label:'Zachowaj milczenie',to:'Doubt'}]},
 {id:'Trust',text:'Detektyw ci ufa.',choices:[]},
 {id:'Doubt',text:'Detektyw ci nie ufa.',choices:[]}
]};
test('choices change story branch and flags',()=>{
 const runtime=new CinematicNarrativeRuntime(story);
 runtime.choose('take',0);
 assert.equal(runtime.snapshot().flags.hasPhone,true);
 assert.equal(runtime.view().choices.length,2);
 assert.equal(runtime.choose('show',1).id,'Trust');
 assert.equal(runtime.view().ending,true);
});
test('locked choice unavailable without evidence',()=>{
 const runtime=new CinematicNarrativeRuntime(story);
 runtime.choose('leave',0);
 assert.equal(runtime.view().choices.length,1);
 assert.throws(()=>runtime.choose('show',1),/CHOICE_NOT_AVAILABLE/);
});
test('save/load retains deterministic state',()=>{
 const runtime=new CinematicNarrativeRuntime(story);
 runtime.choose('take',0);
 const restored=new CinematicNarrativeRuntime(story,JSON.parse(JSON.stringify(runtime.snapshot())));
 assert.deepEqual(restored.view(),runtime.view());
});
test('rejects stale choice',()=>{
 const runtime=new CinematicNarrativeRuntime(story);
 assert.throws(()=>runtime.choose('take',1),/REVISION_CONFLICT/);
});
test('rejects missing scene targets',()=>{
 const invalid=structuredClone(story);invalid.scenes[0].choices[0].to='Missing';
 assert.throws(()=>new CinematicNarrativeRuntime(invalid),/MISSING_TARGET/);
});
test('rejects malformed save flags',()=>{
 const runtime=new CinematicNarrativeRuntime(story);
 const save=runtime.snapshot();save.flags.invalid='yes';
 assert.throws(()=>new CinematicNarrativeRuntime(story,save),/INVALID_SAVE_FLAG/);
});
