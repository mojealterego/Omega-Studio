import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { UnifiedGameFactoryCore } from '../../src/game/UnifiedGameFactoryCore';
const core=new UnifiedGameFactoryCore();
test('registers exactly A00 through A61',()=>{
  assert.equal(core.agents.size,62);
  assert.equal(core.agents.get('A00')?.subsystem,'Research');
  assert.equal(core.agents.get('A61')?.subsystem,'SelfHealingQA');
});
test('game DNA is deterministic',()=>{
  assert.deepEqual(core.generateGameDnaFromPrompt('survival horror'),core.generateGameDnaFromPrompt('survival horror'));
});
test('rejects invalid prompts',()=>{
  assert.throws(()=>core.generateGameDnaFromPrompt(''));
  assert.throws(()=>core.generateGameDnaFromPrompt('x'.repeat(8193)));
});
test('emits valid Unity MCP tool call',()=>{
  const message=JSON.parse(core.buildUnityMcpSceneMutation({instanceId:'cube1',name:'Cube',position:[0,1,2],components:[{type:'Transform',properties:{scale:1}}]}));
  assert.equal(message.method,'tools/call');
  assert.equal(message.params.arguments.name,'Cube');
});
test('rejects nonfinite scene coordinates',()=>{
  assert.throws(()=>core.buildUnityMcpSceneMutation({instanceId:'cube1',name:'Cube',position:[NaN,1,2],components:[]}));
});
test('rejects prototype pollution',()=>{
  assert.throws(()=>core.buildUnityMcpSceneMutation({instanceId:'cube1',name:'Cube',position:[0,1,2],components:[{type:'Transform',properties:JSON.parse('{"__proto__":{"admin":true}}')}]}));
});
test('does not invent signed APK artifacts',()=>{
  const result=core.runQa(core.generateGameDnaFromPrompt('horror'),[]);
  assert.equal(result.passed,true);
  assert.deepEqual(result.signedArtifacts,[]);
});
test('build failures fail closed',()=>{
  const result=core.runQa(core.generateGameDnaFromPrompt('horror'),[],'compiler error');
  assert.equal(result.passed,false);
  assert.ok(result.healingAgents.includes('A50'));
});
test('license failures fail closed',()=>{
  const result=core.runQa(core.generateGameDnaFromPrompt('horror'),[{assetId:'a',commercialUseAllowed:false}]);
  assert.equal(result.passed,false);
  assert.ok(result.failures.includes('QA14_LICENSE_OR_PROVENANCE'));
});
