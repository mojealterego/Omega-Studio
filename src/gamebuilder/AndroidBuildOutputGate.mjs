import { verifyBuildArtifact } from './VerifiedBuildArtifact.mjs';
import { inspectAndroidPackage } from './AndroidPackageInspector.mjs';

/**
 * Concrete Android build receipt verifier for GAME.PDF Build Center.
 * The compiler must provide an existing file path. This function never
 * invents an APK or declares compilation successful by itself.
 */
export async function verifyAndroidBuildOutput({
  buildRoot,
  artifactPath,
  kind,
  expectedSha256,
  minBytes = 1,
  requireSignature = false,
  signatureVerifier,
}) {
  if (requireSignature && typeof signatureVerifier !== 'function') {
    throw new Error('SIGNATURE_VERIFIER_REQUIRED');
  }
  const verified = await verifyBuildArtifact({
    buildRoot, artifactPath, kind, expectedSha256, minBytes,
  });
  const structure = await inspectAndroidPackage(verified.path, kind);
  let signature = { verified: false, scheme: null };
  if (requireSignature) {
    const result = await signatureVerifier(verified.path, kind);
    if (!result || result.verified !== true ||
      typeof result.scheme !== 'string' || !result.scheme) {
      throw new Error('SIGNATURE_VERIFICATION_FAILED');
    }
    signature = { verified: true, scheme: result.scheme };
  }
  return Object.freeze({
    kind: verified.kind,
    uri: new URL('file://' + encodeURI(verified.path)).href,
    sha256: verified.sha256,
    bytes: verified.bytes,
    structureVerified: true,
    signatureVerified: signature.verified,
    signatureScheme: signature.scheme,
    evidence: Object.freeze([
      'sha256:' + verified.sha256,
      'zip-entries:' + structure.entries,
      'android-markers:' + structure.markers.join(','),
      ...(signature.verified ? ['signature:' + signature.scheme] : []),
    ]),
  });
}
