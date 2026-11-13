import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { FactoryRunner, FACTORY_STAGES } from '../../src/gamebuilder/FactoryPipeline.ts';
import { FileFactoryStore } from '../../src/gamebuilder/FileFactoryStore.mjs';

const hex = (n) => String(n % 10).repeat(64);
const workers = () => Object.fromEntries(FACTORY_STAGES.map((stage, index) => [stage, {
  async execute() {
    return {
      stage,
      inputDigest: index === 0 ? 'a'.repeat(64) : hex(index - 1),
      outputDigest: hex(index),
      evidence: ['test-receipt'],
      ...(['build', 'release'].includes(stage)
        ? { artifact: { kind: 'apk', uri: 'file:///example.apk', bytes: 100, sha256: 'f'.repeat(64) } }
        : {})
    };
  }
}]));

async function workspace(fn) {
  const root = await mkdtemp(join(tmpdir(), 'omega-factory-integration-'));
  try { await fn(root); } finally { await rm(root, { recursive: true, force: true }); }
}

test('real FactoryRunner resumes checkpoint from new store instance without rerunning successful stages', async () => workspace(async root => {
  const w = workers();
  delete w['game-dna'];
  const first = new FactoryRunner(new FileFactoryStore(root), w);
  await first.create('Integration');
  const failed = await first.run('Integration', new AbortController().signal);
  assert.equal(failed.status, 'failed');
  assert.equal(failed.receipts.length, 1);
  let researchCalls = 0;
  const resumedWorkers = workers();
  resumedWorkers.research = { async execute() { researchCalls++; throw new Error('MUST_NOT_RERUN'); } };
  const second = new FactoryRunner(new FileFactoryStore(root), resumedWorkers);
  const done = await second.run('Integration', new AbortController().signal);
  assert.equal(done.status, 'succeeded');
  assert.equal(done.receipts.length, FACTORY_STAGES.length);
  assert.equal(researchCalls, 0);
}));

test('interrupted running stage cannot be replayed without explicit no-active-worker confirmation', async () => workspace(async root => {
  const store = new FileFactoryStore(root);
  const initial = new FactoryRunner(store, workers());
  await initial.create('Integration');
  await store.save({ projectId: 'Integration', revision: 1, status: 'running', nextIndex: 0, receipts: [] }, 0);
  const resumed = new FactoryRunner(new FileFactoryStore(root), workers());
  await assert.rejects(resumed.run('Integration', new AbortController().signal), /ALREADY_RUNNING/);
  await store.recoverInterrupted('Integration', 1, { operatorConfirmedNoActiveWorker: true });
  assert.equal((await resumed.run('Integration', new AbortController().signal)).status, 'succeeded');
}));
