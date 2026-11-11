/**
 * OMEGA GeoWorld: deterministic local tangent-plane projection and sector index.
 * WGS84 approximation for neighborhood-scale scenes, not survey-grade GIS.
 * No network, no external dependencies, no geographic data collection.
 */
const EARTH_RADIUS_M=6378137;
const DEG=Math.PI/180;
function coordinate(lat,lon){
 if(!Number.isFinite(lat)||!Number.isFinite(lon)||lat < -85||lat > 85||lon < -180||lon > 180)
  throw Error('INVALID_COORDINATE');
}
export function createGeoWorld({originLat,originLon,sectorSize=256}){
 coordinate(originLat,originLon);
 if(!Number.isFinite(sectorSize)||sectorSize<16||sectorSize>4096)throw Error('INVALID_SECTOR_SIZE');
 const cos=Math.cos(originLat*DEG);
 const toLocal=({lat,lon,alt=0})=>{
  coordinate(lat,lon);
  if(!Number.isFinite(alt)||Math.abs(alt)>20000)throw Error('INVALID_ALTITUDE');
  let delta=lon-originLon;
  if(delta>180)delta-=360;
  if(delta< -180)delta+=360;
  if(Math.abs(lat-originLat)>0.5||Math.abs(delta)>0.5)throw Error('OUTSIDE_LOCAL_PROJECTION');
  return {x:EARTH_RADIUS_M*delta*DEG*cos,y:alt,z:EARTH_RADIUS_M*(lat-originLat)*DEG};
 };
 const toGeo=({x,y=0,z})=>{
  if(![x,y,z].every(Number.isFinite))throw Error('INVALID_LOCAL_POSITION');
  const lat=originLat+z/EARTH_RADIUS_M/DEG;
  let lon=originLon+x/(EARTH_RADIUS_M*cos)/DEG;
  lon=((lon+180)%360+360)%360-180;
  coordinate(lat,lon);
  return {lat,lon,alt:y};
 };
 const sector=({x,z})=>{
  if(!Number.isFinite(x)||!Number.isFinite(z))throw Error('INVALID_LOCAL_POSITION');
  const col=Math.floor(x/sectorSize),row=Math.floor(z/sectorSize);
  if(!Number.isSafeInteger(col)||!Number.isSafeInteger(row))throw Error('SECTOR_OVERFLOW');
  return {col,row,id:`${col}:${row}`};
 };
 const sectorsForBounds=({minX,minZ,maxX,maxZ},maxSectors=4096)=>{
  if(![minX,minZ,maxX,maxZ].every(Number.isFinite)||minX>maxX||minZ>maxZ)throw Error('INVALID_BOUNDS');
  if(!Number.isSafeInteger(maxSectors)||maxSectors<1||maxSectors>100000)throw Error('INVALID_SECTOR_LIMIT');
  const start=sector({x:minX,z:minZ}),end=sector({x:maxX,z:maxZ});
  const count=(end.col-start.col+1)*(end.row-start.row+1);
  if(!Number.isSafeInteger(count)||count>maxSectors)throw Error('SECTOR_LIMIT_EXCEEDED');
  const result=[];
  for(let row=start.row;row<=end.row;row++)for(let col=start.col;col<=end.col;col++)result.push({col,row,id:`${col}:${row}`});
  return result;
 };
 return Object.freeze({originLat,originLon,sectorSize,toLocal,toGeo,sector,sectorsForBounds});
}
