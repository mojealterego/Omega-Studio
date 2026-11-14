# OMEGA Studio Ultimate × GAME — GeoWorld / GLS v0.3.0

Status: **implemented and host-tested** (Node.js 22.16.0 / Linux x86_64), **not** Android-device-tested, **not** a full AAA engine, **not** a quantum computer, **not** a native Unity/Unreal/Godot build. Existing GameBuilder remains the parent product.

## Delivered

- `src/gamebuilder/GeoWorldCore.mjs`: WGS84 geodetic↔ECEF and ECEF↔ENU transforms; finite, bounded DEM; deterministic tile meshes with configurable LODs; globally sampled seam-consistent normals; right-handed glTF 2.0 GLB with PBR material; manifest with SHA-256 for each tile; atomic project-directory publication and verified idempotent replay.
- `src/gamebuilder/GeoWorldStageWorker.mjs`: real `world` stage worker compatible with the existing 16-stage `FactoryRunner` interface; input digest chaining; manifest digest receipt.
- `src/gamebuilder/GeoWorldGameBuilderAdapter.mjs`: verified world → schema-v1 `GameBuilderProject` with scene root and LOD0 tile nodes; supports Code↔NoCode serialization for Godot, Unity, Unreal metadata.
- `src/gamebuilder/GeoWorldCli.mjs`: offline CLI for DEM JSON → GLB tiles and verified manifest.
- `tests/gamebuilder/*.test.mjs`: WGS84 roundtrips, ENU, 250-point deterministic property sweep, mesh seams, triangle winding, GLB header/accessors, reproducibility, corruption, symlinks, traversal, budgets, abort, factory stage receipts, Code↔NoCode, 16-stage factory integration with *only world stage real*.
- `examples/demo_world.json`, `demo-output/DemoWorld01/`: synthetic terrain and generated GLB assets, not a real map/DEM.

## Execute locally

Node.js >=22 (no npm install):

```sh
node src/gamebuilder/GeoWorldCli.mjs --spec examples/demo_world.json --root ./out --project DemoWorld01
node --test tests/gamebuilder/GeoWorldCore.test.mjs
node --experimental-transform-types --test tests/gamebuilder/GeoWorldPipeline.test.mjs tests/gamebuilder/GeoWorldGameBuilder.test.mjs
```

To integrate into existing `FactoryRunner` workers map:

```js
import { GeoWorldStageWorker } from './src/gamebuilder/GeoWorldStageWorker.mjs';
const workers = {
  world: new GeoWorldStageWorker({worldSpec: validatedWorldSpec, outputRoot: '/private/omega-worlds'}),
  // All other stages require their own real workers; no production build is implied.
};
```

`FactoryPipeline.ts` and `GameBuilderProject.ts` in the ZIP are exact behavioral snapshots of the inspected upstream files with only provenance comments added, for offline integration tests; they are **not** intended to replace those existing repository files.

## DEM schema

```json
{
  "schemaVersion": 1,
  "origin": {"lat": 49.748, "lon": 18.634, "altMeters": 285},
  "width": 5,
  "height": 5,
  "sampleSpacingMeters": 2,
  "tileCells": 4,
  "lodLevels": 3,
  "maxOutputBytes": 1000000,
  "elevationsMeters": [
    285,285,285,285,285,
    285,285,285,285,285,
    285,285,285,285,285,
    285,285,285,285,285,
    285,285,285,285,285
  ]
}
```

Coordinates: latitude/longitude degrees on WGS84; altitude and DEM samples are **WGS84 ellipsoidal metres**. DEM samples are absolute heights; glTF local Y = DEM height − origin.altMeters. glTF X = east, Y = up, Z = south (right-handed), and node translation is `(tileEast, 0, -tileNorth)`. `originEcefMeters` and conversion metadata are preserved in `manifest.json`. For source DEM with orthometric heights (e.g., EGM96/EGM2008), **convert to ellipsoidal heights with an appropriate geoid model first**; this package does not silently conflate datums.

Width−1 and height−1 must be multiples of `tileCells` (power of 2, 4..128). `lodLevels` <= log2(tileCells)+1. Total samples <=262144; total GLBs <=4096; output budget 1 KiB..512 MiB. No network calls, no Google Maps or Street View access. The synthetic example has no geographic fidelity to Cieszyn beyond its chosen origin coordinate.

## Security and crash consistency

- Output root and project directories reject symlinks at validation time; IDs use an allowlist. File reads use `O_NOFOLLOW`, size limits, and regular-file checks. No remote fetch or execution of DEM content.
- Each GLB is written via exclusive creation and fsync to a staging directory. The staging directory is synced before atomic rename into the final project directory; parent directory is synced afterwards. Failed/cancelled builds clean up staging files.
- Existing worlds are never overwritten: same spec is reused only after manifest and every artifact are re-verified; different spec is rejected. SHA-256 checks integrity but is not an authenticated signature against privileged tampering.
- This implementation assumes a trusted local filesystem and single trusted owner; cross-host coordination, malicious same-user races, distributed transactions, and power-failure guarantees on every filesystem are not demonstrated.
- `FactoryRunner` controls stage state separately; the world worker is idempotent, but its receipt does not prove that a game, Android APK, or other pipeline stage was built.

## Adapter limitations

The `GameBuilderProject` adapter is an engine-neutral scene manifest, not an engine-native scene or compiled project. Unity and Unreal require their real asset importers, coordinate-conversion validation and runtime/device tests. Godot must import GLB files in a real project; no Godot editor/runtime was executed here. Geometry has no skirt stitching for transitions between adjacent *different* LODs, collision mesh, texture atlas, streaming scheduler, photogrammetry, vegetation, water, cinematic renderer, or quantum/topological accelerator. These remain separate development requirements.

## Evidence

- Node tests: `node --test` and `node --experimental-transform-types --test` executed locally; logs included.
- GLB parsed by `trimesh` and all triangle face normals point upward on the synthetic terrain; `pyproj` WGS84 ECEF cross-check matched to machine precision for the reference origin.
- The other 15 FactoryRunner workers in the integration test are explicitly simulated; only the `world` worker emits real GLB assets.
- No GitHub Actions, physical Android, Unity, Unreal or Godot tests were executed.

## Next production gates

1. Verified real DEM ingest with datum/geoid conversion and provenance; deterministic reprojection and tiling from external sources with license enforcement.
2. LOD transition stitching and runtime streaming with CPU/GPU memory limits and telemetry.
3. Native Godot/Unity/Unreal import adapters with headless editor build and rendering comparisons.
4. Connect real factory workers and verify signed Android ARM64 builds on an actual S24 Ultra; retain separate release gates.
