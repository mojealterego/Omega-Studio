import {strict as assert} from 'node:assert';
import {test} from 'node:test';
import {GAME_INTEGRATIONS,integrationById,validateIntegrationRegistry} from '../../src/integrations/GameDevIntegrationRegistry';
test('registers all 16 supplied repositories exactly once',()=>{
 assert.equal(GAME_INTEGRATIONS.length,16);
 assert.equal(new Set(GAME_INTEGRATIONS.map(x=>x.id)).size,16);
 assert.doesNotThrow(validateIntegrationRegistry);
});
test('all integrations fail closed until approved',()=>{
 for(const integration of GAME_INTEGRATIONS){
  assert.equal(integration.enabled,false);
  assert.equal(integration.transport,'unconfigured');
  assert.equal(integration.trust,'unverified');
 }
});
test('distinguishes MCP servers from packages and SDKs',()=>{
 assert.equal(integrationById('Unity-MCP2')?.kind,'mcp-server');
 assert.equal(integrationById('GameDev-MCP-Server')?.kind,'mcp-server');
 assert.equal(integrationById('Unity-AI-Terrain')?.kind,'unity-extension');
 assert.equal(integrationById('AI-Game-Dev-CLI-Core')?.kind,'cli-core');
 assert.equal(integrationById('mobile-ai-agents')?.kind,'agent-library');
 assert.equal(integrationById('unity')?.kind,'sdk');
});
test('does not fabricate endpoints',()=>{
 for(const integration of GAME_INTEGRATIONS){
  assert.match(integration.repository,/^https:\/\/github\.com\/mojealterego\//);
  assert.equal('endpoint' in integration,false);
 }
});
test('unknown integration returns undefined',()=>{
 assert.equal(integrationById('nonexistent'),undefined);
});
