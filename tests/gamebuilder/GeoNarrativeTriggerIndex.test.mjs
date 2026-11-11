import {test} from 'node:test';
import {strict as assert} from 'node:assert';
import {GeoNarrativeTriggerIndex} from '../../src/gamebuilder/GeoNarrativeTriggerIndex.mjs';
const zones=[
 {id:'station',sceneId:'Interview',x:0,z:0,radius:10,priority:1},
 {id:'evidence',sceneId:'Evidence',x:0,z:0,radius:4,priority:2,requires:[{flag:'hasPhone',equals:true}]}
];
test('distance and flag gate',()=>{const t=new GeoNarrativeTriggerIndex(zones);assert.deepEqual(t.evaluate({x:0,z:0}).map(x=>x.id),['station']);assert.deepEqual(t.evaluate({x:0,z:0,flags:{hasPhone:true}}).map(x=>x.id),['evidence','station']);});
test('boundary included',()=>{const t=new GeoNarrativeTriggerIndex(zones);assert.deepEqual(t.evaluate({x:10,z:0}).map(x=>x.id),['station']);});
test('activation is idempotent',()=>{const t=new GeoNarrativeTriggerIndex(zones);assert.equal(t.activate('station'),true);assert.equal(t.activate('station'),false);assert.deepEqual(t.evaluate({x:0,z:0}).map(x=>x.id),[]);});
test('checkpoint roundtrip',()=>{const t=new GeoNarrativeTriggerIndex(zones);t.activate('station');const copy=new GeoNarrativeTriggerIndex(zones,t.checkpoint());assert.deepEqual(copy.evaluate({x:0,z:0,flags:{hasPhone:true}}).map(x=>x.id),['evidence']);});
test('rejects duplicate zone IDs',()=>assert.throws(()=>new GeoNarrativeTriggerIndex([zones[0],zones[0]]),/INVALID_ZONE/));
test('rejects nonfinite positions',()=>assert.throws(()=>new GeoNarrativeTriggerIndex(zones).evaluate({x:Infinity,z:0}),/INVALID_POSITION/));
test('rejects unknown checkpoint zones',()=>assert.throws(()=>new GeoNarrativeTriggerIndex(zones,{activated:['unknown']}),/INVALID_CHECKPOINT/));
test('rejects unknown activation',()=>assert.throws(()=>new GeoNarrativeTriggerIndex(zones).activate('unknown'),/ZONE_NOT_FOUND/));
