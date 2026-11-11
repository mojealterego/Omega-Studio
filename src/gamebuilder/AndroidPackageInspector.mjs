import { open } from 'node:fs/promises';

/** Validates ZIP central directory and Android package markers without executing archive contents. */
export async function inspectAndroidPackage(filePath, kind, { maxEntries = 100000, maxCentralDirectoryBytes = 64 * 1024 * 1024 } = {}) {
  if (!['apk', 'aab'].includes(kind)) throw new Error('INVALID_PACKAGE_KIND');
  const fh = await open(filePath, 'r');
  try {
    const stat = await fh.stat();
    if (!stat.isFile() || stat.size < 22) throw new Error('INVALID_ZIP');
    const tailLength = Math.min(stat.size, 65557);
    const tail = Buffer.alloc(tailLength);
    await readExact(fh, tail, stat.size - tailLength);
    let eocd = -1;
    for (let i = tail.length - 22; i >= 0; i--) {
      if (tail.readUInt32LE(i) === 0x06054b50 && i + 22 + tail.readUInt16LE(i + 20) === tail.length) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error('MISSING_END_OF_CENTRAL_DIRECTORY');
    const disk = tail.readUInt16LE(eocd + 4);
    const diskWithDirectory = tail.readUInt16LE(eocd + 6);
    const entriesOnDisk = tail.readUInt16LE(eocd + 8);
    const count = tail.readUInt16LE(eocd + 10);
    const directorySize = tail.readUInt32LE(eocd + 12);
    const directoryOffset = tail.readUInt32LE(eocd + 16);
    if (disk !== 0 || diskWithDirectory !== 0 || entriesOnDisk !== count) throw new Error('MULTI_DISK_UNSUPPORTED');
    if (count === 65535 || directorySize === 0xffffffff || directoryOffset === 0xffffffff) throw new Error('ZIP64_UNSUPPORTED');
    if (count > maxEntries || directorySize > maxCentralDirectoryBytes) throw new Error('PACKAGE_LIMIT_EXCEEDED');
    if (directoryOffset + directorySize > stat.size - tailLength + eocd) throw new Error('INVALID_DIRECTORY_BOUNDS');
    const directory = Buffer.alloc(directorySize);
    await readExact(fh, directory, directoryOffset);
    const names = new Set();
    let position = 0;
    for (let index = 0; index < count; index++) {
      if (position + 46 > directory.length || directory.readUInt32LE(position) !== 0x02014b50) throw new Error('INVALID_CENTRAL_DIRECTORY');
      const flags = directory.readUInt16LE(position + 8);
      const method = directory.readUInt16LE(position + 10);
      const compressed = directory.readUInt32LE(position + 20);
      const uncompressed = directory.readUInt32LE(position + 24);
      const nameLength = directory.readUInt16LE(position + 28);
      const extraLength = directory.readUInt16LE(position + 30);
      const commentLength = directory.readUInt16LE(position + 32);
      const localOffset = directory.readUInt32LE(position + 42);
      const end = position + 46 + nameLength + extraLength + commentLength;
      if (end > directory.length || nameLength === 0) throw new Error('INVALID_ENTRY');
      if (flags & 1) throw new Error('ENCRYPTED_ENTRY');
      if (![0, 8].includes(method)) throw new Error('UNSUPPORTED_COMPRESSION');
      if (compressed === 0xffffffff || uncompressed === 0xffffffff || localOffset === 0xffffffff) throw new Error('ZIP64_UNSUPPORTED');
      if (localOffset >= directoryOffset) throw new Error('INVALID_LOCAL_HEADER_OFFSET');
      const name = directory.subarray(position + 46, position + 46 + nameLength).toString('utf8');
      if (name.includes('\0') || name.startsWith('/') || name.includes('\\') || name.split('/').some(part => part === '..' || part === '.')) throw new Error('UNSAFE_ENTRY_NAME');
      if (names.has(name)) throw new Error('DUPLICATE_ENTRY');
      names.add(name);
      position = end;
    }
    if (position !== directory.length) throw new Error('CENTRAL_DIRECTORY_TRAILING_DATA');
    const required = kind === 'apk' ? ['AndroidManifest.xml', 'classes.dex'] : ['BundleConfig.pb', 'base/manifest/AndroidManifest.xml'];
    for (const name of required) if (!names.has(name)) throw new Error('MISSING_ANDROID_PACKAGE_MARKER:' + name);
    return Object.freeze({ kind, entries: count, markers: required, structuralCheck: true, signatureVerified: false });
  } finally { await fh.close(); }
}
async function readExact(fh, buffer, offset) {
  let total = 0;
  while (total < buffer.length) {
    const { bytesRead } = await fh.read(buffer, total, buffer.length - total, offset + total);
    if (bytesRead === 0) throw new Error('UNEXPECTED_EOF');
    total += bytesRead;
  }
}
