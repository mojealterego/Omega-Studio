import { createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { lstat, realpath } from 'node:fs/promises';
import { relative, resolve, sep } from 'node:path';

/** Verifies actual bytes of an APK/AAB within an approved build root. */
export async function verifyBuildArtifact({ buildRoot, artifactPath, kind, expectedSha256, minBytes = 1 }) {
  if (!['apk', 'aab'].includes(kind)) throw new Error('UNSUPPORTED_ARTIFACT_KIND');
  if (typeof artifactPath !== 'string' || !artifactPath.endsWith(`.${kind}`)) throw new Error('INVALID_ARTIFACT_PATH');
  if (!Number.isSafeInteger(minBytes) || minBytes < 1) throw new Error('INVALID_MIN_BYTES');
  if (expectedSha256 !== undefined && !/^[a-fA-F0-9]{64}$/.test(expectedSha256)) throw new Error('INVALID_EXPECTED_DIGEST');
  const root = await realpath(resolve(buildRoot));
  const candidate = resolve(root, artifactPath);
  const rel = relative(root, candidate);
  if (rel === '' || rel === '..' || rel.startsWith(`..${sep}`) || rel.startsWith(sep)) throw new Error('PATH_OUTSIDE_BUILD_ROOT');
  const canonical = await realpath(candidate);
  const canonicalRel = relative(root, canonical);
  if (canonicalRel === '' || canonicalRel === '..' || canonicalRel.startsWith(`..${sep}`) || canonicalRel.startsWith(sep)) throw new Error('SYMLINK_OUTSIDE_BUILD_ROOT');
  const before = await lstat(canonical);
  if (!before.isFile() || before.size < minBytes) throw new Error('INVALID_ARTIFACT_FILE');
  const sha = createHash('sha256');
  let bytes = 0;
  for await (const chunk of createReadStream(canonical, { flags: 'r' })) {
    sha.update(chunk); bytes += chunk.length;
  }
  const after = await lstat(canonical);
  if (before.dev !== after.dev || before.ino !== after.ino || before.size !== after.size || before.mtimeMs !== after.mtimeMs || bytes !== after.size) throw new Error('ARTIFACT_CHANGED_DURING_VERIFICATION');
  const sha256 = sha.digest('hex');
  if (expectedSha256 && sha256 !== expectedSha256.toLowerCase()) throw new Error('ARTIFACT_DIGEST_MISMATCH');
  return Object.freeze({ kind, path: canonical, bytes, sha256, verified: true });
}
