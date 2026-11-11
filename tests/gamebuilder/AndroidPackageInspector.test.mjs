import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { inspectAndroidPackage } from '../../src/gamebuilder/AndroidPackageInspector.mjs';
function zip(names) {
  const local = []; const central = []; let offset = 0;
  for (const name of names) {
    const bytes = Buffer.from(name);
    const l = Buffer.alloc(30 + bytes.length); l.writeUInt32LE(0x04034b50, 0); l.writeUInt16LE(bytes.length, 26); bytes.copy(l, 30);
    const c = Buffer.alloc(46 + bytes.length); c.writeUInt32LE(0x02014b50, 0); c.writeUInt16LE(bytes.length, 28); c.writeUInt32LE(offset, 42); bytes.copy(c, 46);
    local.push(l); central.push(c); offset += l.length;
  }
  const size = central.reduce((sum, b) => sum + b.length, 0);
  const e = Buffer.alloc(22); e.writeUInt32LE(0x06054b50, 0); e.writeUInt16LE(names.length, 8); e.writeUInt16LE(names.length, 10); e.writeUInt32LE(size, 12); e.writeUInt32LE(offset, 16);
  return Buffer.concat([...local, ...central, e]);
}
async function withZip(names, fn) { const dir = await mkdtemp(join(tmpdir(), 'omega-zip-')); const file = join(dir, 'game.zip'); try { await writeFile(file, zip(names)); return await fn(file); } finally { await rm(dir, { recursive: true, force: true }); } }
test('accepts APK central directory and markers', () => withZip(['AndroidManifest.xml', 'classes.dex'], async f => { const r = await inspectAndroidPackage(f, 'apk'); assert.equal(r.entries, 2); assert.equal(r.signatureVerified, false); }));
test('accepts AAB central directory and markers', () => withZip(['BundleConfig.pb', 'base/manifest/AndroidManifest.xml'], async f => assert.equal((await inspectAndroidPackage(f, 'aab')).kind, 'aab')));
test('rejects missing manifest', () => withZip(['classes.dex'], async f => assert.rejects(inspectAndroidPackage(f, 'apk'), /MISSING_ANDROID_PACKAGE_MARKER/)));
test('rejects traversal entry', () => withZip(['AndroidManifest.xml', 'classes.dex', '../secret'], async f => assert.rejects(inspectAndroidPackage(f, 'apk'), /UNSAFE_ENTRY_NAME/)));
test('rejects duplicate entries', () => withZip(['AndroidManifest.xml', 'classes.dex', 'classes.dex'], async f => assert.rejects(inspectAndroidPackage(f, 'apk'), /DUPLICATE_ENTRY/)));
test('rejects entry count limit', () => withZip(['AndroidManifest.xml', 'classes.dex'], async f => assert.rejects(inspectAndroidPackage(f, 'apk', { maxEntries: 1 }), /PACKAGE_LIMIT_EXCEEDED/)));
test('rejects truncated archive', () => withZip([], async f => { await writeFile(f, Buffer.from('invalid')); await assert.rejects(inspectAndroidPackage(f, 'apk'), /INVALID_ZIP/); }));
test('rejects invalid package kind', () => withZip([], async f => assert.rejects(inspectAndroidPackage(f, 'zip'), /INVALID_PACKAGE_KIND/)));
