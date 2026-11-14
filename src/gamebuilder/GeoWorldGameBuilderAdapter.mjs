/** Verified GeoWorld GLBs -> existing reversible GameBuilderProject schema v1. */
import { verifyGeoWorld } from './GeoWorldCore.mjs';

const ENGINES=new Set(['godot','unity','unreal']);
export async function importGeoWorldToGameBuilder(outputRoot,projectId,engine='godot'){
  if(!ENGINES.has(engine))throw Error('UNSUPPORTED_GAME_ENGINE');
  const manifest=await verifyGeoWorld(outputRoot,projectId);
  const nodes=[{id:'GeoWorldScene',type:'scene',parentId:null,name:'OMEGA GeoWorld',properties:{
    coordinateSystem:manifest.coordinateSystem,heightDatum:manifest.heightDatum,
    originLat:manifest.origin.lat,originLon:manifest.origin.lon,originAltMeters:manifest.origin.altMeters,
    metersPerUnit:engine==='unreal'?0.01:1,
  }}];
  for(const tile of manifest.tiles){
    if(tile.lod!==0)continue;
    nodes.push({id:`Tile_r${tile.row}_c${tile.col}`,type:'entity',parentId:'GeoWorldScene',
      name:`Terrain tile ${tile.row}:${tile.col}`,properties:{
        glb:tile.file,sha256:tile.sha256,eastMeters:tile.eastMeters,
        northMeters:tile.northMeters,lod:0,triangles:tile.triangles,
        axisConversionRequired:engine!=='godot',
      }});
  }
  return {schemaVersion:1,projectId,engine,revision:0,nodes};
}
