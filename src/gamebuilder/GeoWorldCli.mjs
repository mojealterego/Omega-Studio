#!/usr/bin/env node
/** Offline CLI: validates an explicit local JSON DEM and publishes a verified world. */
import { constants } from 'node:fs';
import { open } from 'node:fs/promises';
import { buildGeoWorld, verifyGeoWorld } from './GeoWorldCore.mjs';

function parseArgs(argv){
  if(argv.length!==6||argv[0]!=='--spec'||argv[2]!=='--root'||argv[4]!=='--project')
    throw Error('USAGE: node GeoWorldCli.mjs --spec input.json --root output-directory --project Project01');
  return {specPath:argv[1],root:argv[3],project:argv[5]};
}
async function main(){
  const {specPath,root,project}=parseArgs(process.argv.slice(2));
  const h=await open(specPath,constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);
  let data;
  try{const stat=await h.stat();if(!stat.isFile()||stat.size>16*1024*1024)throw Error('SPEC_FILE_TOO_LARGE');data=await h.readFile();}
  finally{await h.close();}
  let spec;try{spec=JSON.parse(data.toString('utf8'));}catch{throw Error('INVALID_SPEC_JSON');}
  const manifest=await buildGeoWorld(spec,root,project);
  await verifyGeoWorld(root,project,manifest.specSha256);
  process.stdout.write(JSON.stringify({status:'HOST_VERIFIED',projectId:project,tiles:manifest.tiles.length,
    bytes:manifest.outputBytes,specSha256:manifest.specSha256})+'\n');
}
main().catch(error=>{process.stderr.write((error?.message??'UNKNOWN_ERROR')+'\n');process.exitCode=1;});
