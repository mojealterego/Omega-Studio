import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { mkdtemp, readFile, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { FileFactoryStore } from '../../src/gamebuilder/FileFactoryStore.mjs';

async function workspace(fn) {
  const root = await mkdtemp(join(tmpdir(), 'omega-factory-state-'));
  try { await fn(root); } finally { await rm(root, { recursive: true, force: true }); }
}
function state(revision = 0, status = 'pending') {
  return { projectId: 'Game01', revision, status, nextIndex: 0, receipts: [] };
}

test('persists a checkpoint across new store instances', async () => workspace(async root => {
  const writer = new FileFactoryStore(root);
  await writer.save(state(), -1);
  await writer.save({ ...state(1), status: 'paused' }, 0);
  const reader = new FileFactoryStore(root);
  assert.deepEqual(await reader.load('Game01'), { ...state(1), status: 'paused' });
}));

test('rejects stale compare-and-swap updates', async () => workspace(async root => {
  const first = new FileFactoryStore(root), second = new FileFactoryStore(root);
  await first.save(state(), -1);
  await first.save(state(1), 0);
  await assert.rejects(second.save(state(1, 'failed'), 0), /OPTIMISTIC_LOCK_CONFLICT/);
  assert.deepEqual(await second.load('Game01'), state(1));
}));

test('serializes simultaneous writers with exactly one winner', async () => workspace(async root => {
  const first = new FileFactoryStore(root), second = new FileFactoryStore(root);
  await first.save(state(), -1);
  const settled = await Promise.allSettled([
    first.save(state(1, 'paused'), 0),
    second.save(state(1, 'failed'), 0),
  ]);
  assert.equal(settled.filter(x => x.status === 'fulfilled').length, 1);
  assert.equal(settled.filter(x => x.status === 'rejected').length, 1);
  assert.equal((await first.load('Game01')).revision, 1);
}));

test('rejects tampered state and does not overwrite it', async () => workspace(async root => {
  const store = new FileFactoryStore(root);
  await store.save(state(), -1);
  const file = join(root, 'Game01.json');
  const envelope = JSON.parse(await readFile(file, 'utf8'));
  envelope.state.status = 'succeeded';
  await writeFile(file, JSON.stringify(envelope));
  await assert.rejects(store.load('Game01'), /STATE_INTEGRITY_MISMATCH/);
  await assert.rejects(store.save(state(1), 0), /STATE_INTEGRITY_MISMATCH/);
}));

test('rejects invalid project IDs and source symlink redirects', async () => workspace(async root => {
  const store = new FileFactoryStore(root);
  await assert.rejects(store.load('../secret'), /INVALID_PROJECT_ID/);
  await assert.rejects(store.save({ ...state(), projectId: '../../etc/passwd' }, -1), /INVALID_PROJECT_ID/);
  const target = join(root, 'other.json');
  await writeFile(target, JSON.stringify({ secret: 'not a state' }));
  await symlink(target, join(root, 'Game01.json'));
  await assert.rejects(store.load('Game01'), /ELOOP|STATE_NOT_REGULAR_FILE/);
  await assert.rejects(store.save(state(), -1), /ELOOP|STATE_NOT_REGULAR_FILE/);
}));

test('refuses unconfirmed recovery and resumes interrupted checkpoint only after explicit acknowledgement', async () => workspace(async root => {
  const store = new FileFactoryStore(root);
  await store.save(state(0, 'running'), -1);
  await assert.rejects(store.recoverInterrupted('Game01', 0), /RECOVERY_REQUIRES_OPERATOR_CONFIRMATION/);
  const resumed = await store.recoverInterrupted('Game01', 0, { operatorConfirmedNoActiveWorker: true });
  assert.equal(resumed.status, 'paused');
  assert.equal(resumed.revision, 1);
  assert.equal((await new FileFactoryStore(root).load('Game01')).status, 'paused');
  await assert.rejects(store.recoverInterrupted('Game01', 0, { operatorConfirmedNoActiveWorker: true }), /OPTIMISTIC_LOCK_CONFLICT/);
}));

test('rejects revisions skipped by writers and mismatched state project', async () => workspace(async root => {
  const store = new FileFactoryStore(root);
  await assert.rejects(store.save(state(2), -1), /INVALID_REVISION_TRANSITION/);
  await assert.rejects(store.save({ ...state(), projectId: '__bad' }, -1), /INVALID_PROJECT_ID/);
}));
