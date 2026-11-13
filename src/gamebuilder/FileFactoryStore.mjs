import { createHash, randomUUID } from 'node:crypto';
import { constants } from 'node:fs';
import { lstat, mkdir, open, rename, unlink } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { setTimeout as sleep } from 'node:timers/promises';

const PROJECT_ID = /^[A-Za-z][A-Za-z0-9_-]{0,95}$/;
const VALID_STATUS = new Set(['pending', 'running', 'succeeded', 'failed', 'paused']);
const SHA256 = /^[a-f0-9]{64}$/;
const MAX_STATE_BYTES = 8 * 1024 * 1024;
const MAX_STAGES = 128;

function requireProjectId(value) {
  if (typeof value !== 'string' || !PROJECT_ID.test(value)) throw new Error('INVALID_PROJECT_ID');
}
function validateState(state) {
  if (!state || typeof state !== 'object' || Array.isArray(state)) throw new Error('INVALID_FACTORY_STATE');
  requireProjectId(state.projectId);
  if (!Number.isSafeInteger(state.revision) || state.revision < 0 ||
      !VALID_STATUS.has(state.status) || !Number.isSafeInteger(state.nextIndex) ||
      state.nextIndex < 0 || state.nextIndex > MAX_STAGES ||
      !Array.isArray(state.receipts) || state.receipts.length !== state.nextIndex ||
      (state.lastError !== undefined && (typeof state.lastError !== 'string' || state.lastError.length > 4096))) {
    throw new Error('INVALID_FACTORY_STATE');
  }
  for (const receipt of state.receipts) {
    if (!receipt || typeof receipt !== 'object' || typeof receipt.stage !== 'string' ||
        typeof receipt.inputDigest !== 'string' || !SHA256.test(receipt.inputDigest.toLowerCase()) ||
        typeof receipt.outputDigest !== 'string' || !SHA256.test(receipt.outputDigest.toLowerCase()) ||
        !Array.isArray(receipt.evidence) || receipt.evidence.length < 1 ||
        receipt.evidence.some(e => typeof e !== 'string' || !e || e.length > 4096)) {
      throw new Error('INVALID_FACTORY_RECEIPT');
    }
  }
}
function checksum(state) {
  return createHash('sha256').update(JSON.stringify(state), 'utf8').digest('hex');
}

/**
 * Crash-consistent local StateStore for FactoryRunner (one trusted host/filesystem).
 * Atomic rename and per-project exclusive lock serialize compare-and-swap writes.
 * The SHA-256 envelope detects accidental corruption, not malicious rewrites by the OS user.
 * A crashed process can leave a .lock file; it is deliberately NOT reclaimed automatically.
 */
export class FileFactoryStore {
  constructor(rootDirectory, { lockAttempts = 100, lockWaitMs = 20 } = {}) {
    if (typeof rootDirectory !== 'string' || !rootDirectory.trim()) throw new Error('INVALID_STATE_ROOT');
    if (!Number.isSafeInteger(lockAttempts) || lockAttempts < 1 || lockAttempts > 1000 ||
        !Number.isSafeInteger(lockWaitMs) || lockWaitMs < 1 || lockWaitMs > 1000) {
      throw new Error('INVALID_LOCK_POLICY');
    }
    this.root = resolve(rootDirectory);
    this.lockAttempts = lockAttempts;
    this.lockWaitMs = lockWaitMs;
  }

  async #ensureRoot() {
    await mkdir(this.root, { recursive: true, mode: 0o700 });
    const stat = await lstat(this.root);
    if (!stat.isDirectory() || stat.isSymbolicLink()) throw new Error('UNSAFE_STATE_ROOT');
  }
  #path(projectId) {
    requireProjectId(projectId);
    return join(this.root, projectId + '.json');
  }
  async load(projectId) {
    const file = this.#path(projectId);
    await this.#ensureRoot();
    let descriptor;
    try {
      descriptor = await open(file, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
    } catch (error) {
      if (error?.code === 'ENOENT') return null;
      if (error?.code === 'ELOOP') throw new Error('STATE_NOT_REGULAR_FILE');
      throw error;
    }
    try {
      const stat = await descriptor.stat();
      if (!stat.isFile() || stat.size > MAX_STATE_BYTES) throw new Error('STATE_NOT_REGULAR_FILE');
      const text = await descriptor.readFile('utf8');
      if (Buffer.byteLength(text, 'utf8') > MAX_STATE_BYTES) throw new Error('STATE_TOO_LARGE');
      let envelope;
      try { envelope = JSON.parse(text); } catch { throw new Error('STATE_INVALID_JSON'); }
      if (envelope?.schema !== 1 || typeof envelope.digest !== 'string' || !SHA256.test(envelope.digest)) {
        throw new Error('STATE_INVALID_ENVELOPE');
      }
      if (checksum(envelope.state) !== envelope.digest) throw new Error('STATE_INTEGRITY_MISMATCH');
      validateState(envelope.state);
      if (envelope.state.projectId !== projectId) throw new Error('STATE_PROJECT_MISMATCH');
      return structuredClone(envelope.state);
    } finally {
      await descriptor.close();
    }
  }

  async #withLock(projectId, action) {
    await this.#ensureRoot();
    const lockPath = join(this.root, projectId + '.lock');
    let handle;
    for (let attempt = 0; attempt < this.lockAttempts; attempt++) {
      try {
        handle = await open(lockPath, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600);
        break;
      } catch (error) {
        if (error?.code !== 'EEXIST') throw error;
        if (attempt + 1 === this.lockAttempts) throw new Error('STATE_LOCK_BUSY');
        await sleep(this.lockWaitMs);
      }
    }
    try {
      await handle.writeFile(String(process.pid) + '\n', 'utf8');
      await handle.sync();
      return await action();
    } finally {
      await handle.close();
      await unlink(lockPath);
    }
  }

  async #saveLocked(state, expectedRevision) {
    const current = await this.load(state.projectId);
    if ((current?.revision ?? -1) !== expectedRevision) throw new Error('OPTIMISTIC_LOCK_CONFLICT');
    const envelope = JSON.stringify({ schema: 1, digest: checksum(state), state });
    if (Buffer.byteLength(envelope, 'utf8') > MAX_STATE_BYTES) throw new Error('STATE_TOO_LARGE');
    const target = this.#path(state.projectId);
    const temp = join(this.root, state.projectId + '.' + randomUUID() + '.tmp');
    let descriptor;
    try {
      descriptor = await open(temp, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600);
      await descriptor.writeFile(envelope, 'utf8');
      await descriptor.sync();
    } finally {
      if (descriptor) await descriptor.close();
    }
    try {
      await rename(temp, target);
      const directory = await open(this.root, constants.O_RDONLY | (constants.O_DIRECTORY ?? 0));
      try { await directory.sync(); } finally { await directory.close(); }
    } finally {
      await unlink(temp).catch(error => { if (error.code !== 'ENOENT') throw error; });
    }
  }

  async save(state, expectedRevision) {
    validateState(state);
    if (!Number.isSafeInteger(expectedRevision) || expectedRevision < -1 ||
        state.revision !== expectedRevision + 1) throw new Error('INVALID_REVISION_TRANSITION');
    return this.#withLock(state.projectId, () => this.#saveLocked(state, expectedRevision));
  }

  /** Only after the operator establishes that the previous worker is no longer alive. */
  async recoverInterrupted(projectId, expectedRevision, { operatorConfirmedNoActiveWorker = false } = {}) {
    requireProjectId(projectId);
    if (!operatorConfirmedNoActiveWorker) throw new Error('RECOVERY_REQUIRES_OPERATOR_CONFIRMATION');
    return this.#withLock(projectId, async () => {
      const previous = await this.load(projectId);
      if ((previous?.revision ?? -1) !== expectedRevision) throw new Error('OPTIMISTIC_LOCK_CONFLICT');
      if (previous.status !== 'running') throw new Error('STATE_NOT_INTERRUPTED');
      const next = { ...previous, revision: previous.revision + 1, status: 'paused',
        lastError: 'INTERRUPTED_RUN_REQUIRES_RECONCILIATION' };
      await this.#saveLocked(next, expectedRevision);
      return structuredClone(next);
    });
  }
}
