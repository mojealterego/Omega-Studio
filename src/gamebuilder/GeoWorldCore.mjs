/**
 * OMEGA GeoCore / GLS v0.3.0: deterministic, offline WGS84 + DEM tile -> glTF GLB.
 * Engine-neutral source asset generator, NOT an Unreal/Unity/Godot build tool.
 * Node >= 22, no external packages or remote network calls.
 */
import { createHash } from 'node:crypto';
import { constants } from 'node:fs';
import { lstat, mkdir, mkdtemp, open, readdir, rename, rm } from 'node:fs/promises';
import { join, resolve } from 'node:path';

const A=6378137.0;
const F=1/298.257223563;
const E2=F*(2-F);
const B=A*(1-F);
const DEG=Math.PI/180;
const PROJECT=/^[A-Za-z][A-Za-z0-9_-]{0,95}$/;
const FILE=/^tile_r\d{4}_c\d{4}_lod\d{2}\.glb$/;
const DIGEST=/^[a-f0-9]{64}$/;
const FIELD_NAMES=new Set(['schemaVersion','origin','width','height','sampleSpacingMeters','tileCells','lodLevels','maxOutputBytes','elevationsMeters']);
const MAX_SAMPLES=262144;
const MAX_TILES=4096;
const MAX_BYTES=512*1024*1024;

export const GEOCORE_VERSION='0.3.0';
const sha256=value=>createHash('sha256').update(value).digest('hex');
function fail(code){throw new Error(code);}
function finite(value){return typeof value==='number'&&Number.isFinite(value);}
function plain(value){return value!==null&&typeof value==='object'&&!Array.isArray(value)&&
  (Object.getPrototypeOf(value)===Object.prototype||Object.getPrototypeOf(value)===null);}
function checkOrigin(origin){
  if(!plain(origin)||Object.keys(origin).sort().join(',')!=='altMeters,lat,lon'||
    !finite(origin.lat)||Math.abs(origin.lat)>90||!finite(origin.lon)||Math.abs(origin.lon)>180||
    !finite(origin.altMeters)||origin.altMeters < -12000||origin.altMeters > 100000)fail('INVALID_ORIGIN');
}
function checkProject(projectId){if(typeof projectId!=='string'||!PROJECT.test(projectId))fail('INVALID_PROJECT_ID');}
function checkAbort(signal){if(signal?.aborted)fail('CANCELLED');}

/** WGS84 geodetic (degrees, meters) -> Earth-centred Earth-fixed coordinates (meters). */
export function geodeticToEcef(lat,lon,altMeters=0){
  checkOrigin({lat,lon,altMeters});
  const phi=lat*DEG,lambda=lon*DEG;
  const s=Math.sin(phi),c=Math.cos(phi),N=A/Math.sqrt(1-E2*s*s);
  return [(N+altMeters)*c*Math.cos(lambda),(N+altMeters)*c*Math.sin(lambda),(N*(1-E2)+altMeters)*s];
}
/** WGS84 ECEF -> geodetic; iterative inversion with polar-axis handling. */
export function ecefToGeodetic(x,y,z){
  if(![x,y,z].every(finite))fail('INVALID_ECEF');
  const p=Math.hypot(x,y);
  if(p<1e-8){
    if(Math.abs(z)<1e-8)fail('ECEF_AT_EARTH_CENTER');
    return {lat:z>=0?90:-90,lon:0,altMeters:Math.abs(z)-B};
  }
  const lon=Math.atan2(y,x);
  let lat=Math.atan2(z,p*(1-E2)),alt=0;
  for(let i=0;i<12;i++){
    const s=Math.sin(lat),N=A/Math.sqrt(1-E2*s*s);
    alt=p/Math.cos(lat)-N;
    const next=Math.atan2(z,p*(1-E2*N/(N+alt)));
    if(Math.abs(next-lat)<1e-14){lat=next;break;}
    lat=next;
  }
  const s=Math.sin(lat),N=A/Math.sqrt(1-E2*s*s);
  alt=p/Math.cos(lat)-N;
  return {lat:lat/DEG,lon:lon/DEG,altMeters:alt};
}
/** ECEF -> local ENU (east,north,up), metres. */
export function ecefToEnu(x,y,z,origin){
  checkOrigin(origin);
  if(![x,y,z].every(finite))fail('INVALID_ECEF');
  const [x0,y0,z0]=geodeticToEcef(origin.lat,origin.lon,origin.altMeters);
  const dX=x-x0,dY=y-y0,dZ=z-z0;
  const phi=origin.lat*DEG,lambda=origin.lon*DEG;
  const sP=Math.sin(phi),cP=Math.cos(phi),sL=Math.sin(lambda),cL=Math.cos(lambda);
  return [-sL*dX+cL*dY,-sP*cL*dX-sP*sL*dY+cP*dZ,cP*cL*dX+cP*sL*dY+sP*dZ];
}
/** Local ENU -> ECEF (meters). */
export function enuToEcef(east,north,up,origin){
  checkOrigin(origin);
  if(![east,north,up].every(finite))fail('INVALID_ENU');
  const [x0,y0,z0]=geodeticToEcef(origin.lat,origin.lon,origin.altMeters);
  const phi=origin.lat*DEG,lambda=origin.lon*DEG;
  const sP=Math.sin(phi),cP=Math.cos(phi),sL=Math.sin(lambda),cL=Math.cos(lambda);
  return [x0-sL*east-sP*cL*north+cP*cL*up,
          y0+cL*east-sP*sL*north+cP*sL*up,
          z0+cP*north+sP*up];
}

/** Fail-closed world specification validation. Returns a deep-copied, normalized object. */
export function validateWorldSpec(input){
  if(!plain(input))fail('INVALID_WORLD_SPEC');
  for(const key of Object.keys(input))if(!FIELD_NAMES.has(key))fail('UNSUPPORTED_SPEC_FIELD');
  if(input.schemaVersion!==1)fail('INVALID_WORLD_SCHEMA');
  checkOrigin(input.origin);
  const {width,height,tileCells,lodLevels,sampleSpacingMeters,maxOutputBytes,elevationsMeters}=input;
  if(!Number.isSafeInteger(width)||!Number.isSafeInteger(height)||width<5||height<5||
    width*height>MAX_SAMPLES)fail('INVALID_DEM_DIMENSIONS');
  if(!Number.isSafeInteger(tileCells)||tileCells<4||tileCells>128||
    (tileCells&(tileCells-1))!==0||((width-1)%tileCells)!==0||((height-1)%tileCells)!==0)fail('INVALID_TILE_CELLS');
  if(!Number.isSafeInteger(lodLevels)||lodLevels<1||lodLevels>Math.log2(tileCells)+1)fail('INVALID_LOD_LEVELS');
  if(!finite(sampleSpacingMeters)||sampleSpacingMeters<0.1||sampleSpacingMeters>1000)fail('INVALID_SAMPLE_SPACING');
  if(!Number.isSafeInteger(maxOutputBytes)||maxOutputBytes<1024||maxOutputBytes>MAX_BYTES)fail('INVALID_OUTPUT_BUDGET');
  if(!Array.isArray(elevationsMeters)||elevationsMeters.length!==width*height)fail('INVALID_ELEVATION_COUNT');
  if(elevationsMeters.some(x=>!finite(x)||x< -12000||x>100000))fail('INVALID_ELEVATION');
  const tileCount=((width-1)/tileCells)*((height-1)/tileCells)*lodLevels;
  if(tileCount>MAX_TILES)fail('TOO_MANY_TILES');
  return {schemaVersion:1,origin:{lat:input.origin.lat,lon:input.origin.lon,altMeters:input.origin.altMeters},
    width,height,sampleSpacingMeters,tileCells,lodLevels,maxOutputBytes,elevationsMeters:[...elevationsMeters]};
}
function heightAt(spec,row,col){return spec.elevationsMeters[row*spec.width+col];}
function normalAt(spec,row,col){
  const c0=Math.max(0,col-1),c1=Math.min(spec.width-1,col+1);
  const r0=Math.max(0,row-1),r1=Math.min(spec.height-1,row+1);
  const dhde=(heightAt(spec,row,c1)-heightAt(spec,row,c0))/((c1-c0)*spec.sampleSpacingMeters);
  const dhdn=(heightAt(spec,r1,col)-heightAt(spec,r0,col))/((r1-r0)*spec.sampleSpacingMeters);
  const len=Math.hypot(dhde,1,dhdn);
  return [-dhde/len,1/len,dhdn/len]; // glTF Z is south (-north)
}
/** Returns a tile mesh in right-handed glTF X-east/Y-up/Z-south coordinates. */
export function makeTileMesh(spec,tileRow,tileCol,lod){
  return makeTileMeshValidated(validateWorldSpec(spec),tileRow,tileCol,lod);
}
function makeTileMeshValidated(s,tileRow,tileCol,lod){
  const cols=(s.width-1)/s.tileCells,rows=(s.height-1)/s.tileCells;
  if(!Number.isSafeInteger(tileRow)||tileRow<0||tileRow>=rows||
     !Number.isSafeInteger(tileCol)||tileCol<0||tileCol>=cols||
     !Number.isSafeInteger(lod)||lod<0||lod>=s.lodLevels)fail('INVALID_TILE_COORDINATES');
  const step=2**lod,n=s.tileCells/step+1;
  const positions=new Float32Array(n*n*3),normals=new Float32Array(n*n*3),uvs=new Float32Array(n*n*2);
  const indices=new Uint16Array((n-1)*(n-1)*6);
  const startRow=tileRow*s.tileCells,startCol=tileCol*s.tileCells;
  let v=0,u=0;
  let minH=Infinity,maxH=-Infinity;
  for(let i=0;i<n;i++)for(let j=0;j<n;j++){
    const row=startRow+i*step,col=startCol+j*step,h=heightAt(s,row,col);
    positions[v]=j*step*s.sampleSpacingMeters;positions[v+1]=h-s.origin.altMeters;positions[v+2]=-i*step*s.sampleSpacingMeters;
    const norm=normalAt(s,row,col);
    normals.set(norm,v);v+=3;
    uvs[u++]=col/(s.width-1);uvs[u++]=row/(s.height-1);
    minH=Math.min(minH,h);maxH=Math.max(maxH,h);
  }
  let k=0;
  for(let i=0;i<n-1;i++)for(let j=0;j<n-1;j++){
    const a=i*n+j,b=a+1,c=a+n,d=c+1;
    indices[k++]=a;indices[k++]=b;indices[k++]=c;
    indices[k++]=b;indices[k++]=d;indices[k++]=c;
  }
  return {positions,normals,uvs,indices,vertexCount:n*n,triangleCount:indices.length/3,
    minHeight:minH,maxHeight:maxH,tileRow,tileCol,lod,
    east:startCol*s.sampleSpacingMeters,north:startRow*s.sampleSpacingMeters,
    widthMeters:s.tileCells*s.sampleSpacingMeters};
}
function align4(n){return (n+3)&~3;}
function bytesOfFloat32(arr){const b=Buffer.alloc(arr.length*4);for(let i=0;i<arr.length;i++)b.writeFloatLE(arr[i],i*4);return b;}
function bytesOfUint16(arr){const b=Buffer.alloc(arr.length*2);for(let i=0;i<arr.length;i++)b.writeUInt16LE(arr[i],i*2);return b;}
/** Valid glTF 2.0 binary container with one mesh, PBR material and ENU metadata. */
export function encodeGlb(mesh,{east=mesh.east,north=mesh.north}={}){
  if(!mesh||!Number.isSafeInteger(mesh.vertexCount)||mesh.vertexCount<3||mesh.vertexCount>16641||
     ![east,north].every(finite)||mesh.positions.length!==mesh.vertexCount*3||
     mesh.normals.length!==mesh.vertexCount*3||mesh.uvs.length!==mesh.vertexCount*2||
     mesh.indices.length%3!==0||mesh.indices.some(i=>i>=mesh.vertexCount))fail('INVALID_MESH');
  const raw=[bytesOfFloat32(mesh.positions),bytesOfFloat32(mesh.normals),bytesOfFloat32(mesh.uvs),bytesOfUint16(mesh.indices)];
  const views=[];let offset=0;
  for(const b of raw){views.push({buffer:0,byteOffset:offset,byteLength:b.length});offset+=align4(b.length);}
  const binary=Buffer.alloc(offset);
  raw.forEach((b,i)=>b.copy(binary,views[i].byteOffset));
  const maxX=Math.max(...mesh.positions.filter((_,i)=>i%3===0));
  const minX=Math.min(...mesh.positions.filter((_,i)=>i%3===0));
  const minZ=Math.min(...mesh.positions.filter((_,i)=>i%3===2));
  const maxZ=Math.max(...mesh.positions.filter((_,i)=>i%3===2));
  const minY=Math.min(...mesh.positions.filter((_,i)=>i%3===1));
  const maxY=Math.max(...mesh.positions.filter((_,i)=>i%3===1));
  const gltf={asset:{version:'2.0',generator:'OMEGA GeoCore '+GEOCORE_VERSION},scene:0,
    scenes:[{nodes:[0]}],nodes:[{mesh:0,translation:[east,0,-north]}],
    meshes:[{primitives:[{attributes:{POSITION:0,NORMAL:1,TEXCOORD_0:2},indices:3,material:0,mode:4}]}],
    materials:[{name:'Terrain_PBR',pbrMetallicRoughness:{baseColorFactor:[0.48,0.53,0.43,1],metallicFactor:0,roughnessFactor:0.95},doubleSided:false}],
    buffers:[{byteLength:binary.length}],bufferViews:views,
    accessors:[
      {bufferView:0,componentType:5126,count:mesh.vertexCount,type:'VEC3',min:[minX,minY,minZ],max:[maxX,maxY,maxZ]},
      {bufferView:1,componentType:5126,count:mesh.vertexCount,type:'VEC3'},
      {bufferView:2,componentType:5126,count:mesh.vertexCount,type:'VEC2'},
      {bufferView:3,componentType:5123,count:mesh.indices.length,type:'SCALAR'}
    ]};
  const json=Buffer.from(JSON.stringify(gltf),'utf8');
  const jsonPadded=Buffer.alloc(align4(json.length),0x20);json.copy(jsonPadded);
  const out=Buffer.alloc(12+8+jsonPadded.length+8+binary.length);
  out.write('glTF',0,'ascii');out.writeUInt32LE(2,4);out.writeUInt32LE(out.length,8);
  out.writeUInt32LE(jsonPadded.length,12);out.write('JSON',16,'ascii');jsonPadded.copy(out,20);
  const binHeader=20+jsonPadded.length;out.writeUInt32LE(binary.length,binHeader);out.write('BIN\0',binHeader+4,'ascii');
  binary.copy(out,binHeader+8);
  return out;
}
async function writeDurable(file,buffer){
  const handle=await open(file,constants.O_WRONLY|constants.O_CREAT|constants.O_EXCL|constants.O_NOFOLLOW,0o600);
  try{await handle.writeFile(buffer);await handle.sync();}finally{await handle.close();}
}
async function syncDir(dir){const h=await open(dir,constants.O_RDONLY|(constants.O_DIRECTORY??0));try{await h.sync();}finally{await h.close();}}
async function readSafeFile(path,maxBytes){
  const h=await open(path,constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);
  try{const stat=await h.stat();if(!stat.isFile()||stat.size>maxBytes)fail('UNSAFE_WORLD_FILE');return await h.readFile();}finally{await h.close();}
}
async function safeDirectory(path,create=false){
  if(create)await mkdir(path,{recursive:true,mode:0o700});
  const stat=await lstat(path);
  if(!stat.isDirectory()||stat.isSymbolicLink())fail('UNSAFE_WORLD_DIRECTORY');
}
/** Read manifest and verify all on-disk GLBs by SHA-256; fail closed on unexpected files. */
export async function verifyGeoWorld(outputRoot,projectId,expectedSpecSha256){
  checkProject(projectId);
  if(typeof outputRoot!=='string'||!outputRoot.trim())fail('INVALID_OUTPUT_ROOT');
  const target=join(resolve(outputRoot),projectId);
  await safeDirectory(target);
  const raw=await readSafeFile(join(target,'manifest.json'),2*1024*1024);
  let m;try{m=JSON.parse(raw.toString('utf8'));}catch{fail('INVALID_WORLD_MANIFEST');}
  if(!plain(m)||m.schemaVersion!==1||m.generator!=='OMEGA-GeoCore-v0.3.0'||
     m.projectId!==projectId||!DIGEST.test(m.specSha256)||!Array.isArray(m.tiles)||
     m.tiles.length<1||m.tiles.length>MAX_TILES||
     (expectedSpecSha256&&m.specSha256!==expectedSpecSha256))fail('WORLD_MANIFEST_MISMATCH');
  const files=await readdir(target);
  if(files.length!==m.tiles.length+1||!files.includes('manifest.json'))fail('WORLD_FILE_SET_MISMATCH');
  const seen=new Set();
  for(const tile of m.tiles){
    if(!plain(tile)||typeof tile.file!=='string'||!FILE.test(tile.file)||seen.has(tile.file)||
       !DIGEST.test(tile.sha256)||!Number.isSafeInteger(tile.bytes)||tile.bytes<100||tile.bytes>MAX_BYTES)
       fail('INVALID_TILE_MANIFEST');
    seen.add(tile.file);
    const buf=await readSafeFile(join(target,tile.file),tile.bytes);
    if(buf.length!==tile.bytes||sha256(buf)!==tile.sha256)fail('ARTIFACT_HASH_MISMATCH');
    if(buf.toString('ascii',0,4)!=='glTF'||buf.readUInt32LE(4)!==2||buf.readUInt32LE(8)!==buf.length)
       fail('INVALID_GLB_ARTIFACT');
  }
  return m;
}
/** Atomic, deterministic world publication. Repeated identical input is idempotent. */
export async function buildGeoWorld(worldSpec,outputRoot,projectId,{signal}={}){
  checkProject(projectId);checkAbort(signal);
  if(typeof outputRoot!=='string'||!outputRoot.trim())fail('INVALID_OUTPUT_ROOT');
  const spec=validateWorldSpec(worldSpec),specSha256=sha256(JSON.stringify(spec));
  const root=resolve(outputRoot);await safeDirectory(root,true);
  const target=join(root,projectId);
  try{
    await lstat(target);
    const existing=await verifyGeoWorld(root,projectId);
    if(existing.specSha256!==specSha256)fail('OUTPUT_SPEC_MISMATCH');
    return existing;
  }catch(error){if(error?.code!=='ENOENT')throw error;}
  const stage=await mkdtemp(join(root,'.'+projectId+'-'));
  try{
    const tiles=[];let bytes=0;
    const cols=(spec.width-1)/spec.tileCells,rows=(spec.height-1)/spec.tileCells;
    for(let row=0;row<rows;row++)for(let col=0;col<cols;col++)for(let lod=0;lod<spec.lodLevels;lod++){
      checkAbort(signal);
      const mesh=makeTileMeshValidated(spec,row,col,lod);
      const glb=encodeGlb(mesh);
      bytes+=glb.length;
      if(bytes>spec.maxOutputBytes)fail('OUTPUT_BUDGET_EXCEEDED');
      const file=`tile_r${String(row).padStart(4,'0')}_c${String(col).padStart(4,'0')}_lod${String(lod).padStart(2,'0')}.glb`;
      await writeDurable(join(stage,file),glb);
      tiles.push({file,sha256:sha256(glb),bytes:glb.length,row,col,lod,
        vertices:mesh.vertexCount,triangles:mesh.triangleCount,
        eastMeters:mesh.east,northMeters:mesh.north,minHeightMeters:mesh.minHeight,maxHeightMeters:mesh.maxHeight});
    }
    const manifest={schemaVersion:1,generator:'OMEGA-GeoCore-v0.3.0',projectId,specSha256,
      coordinateSystem:'RH_X_EAST_Y_UP_Z_SOUTH',units:'meters',origin:spec.origin,
      originEcefMeters:geodeticToEcef(spec.origin.lat,spec.origin.lon,spec.origin.altMeters),
      heightDatum:'WGS84_ELLIPSOIDAL_METERS',sampleSpacingMeters:spec.sampleSpacingMeters,width:spec.width,height:spec.height,
      tileCells:spec.tileCells,lodLevels:spec.lodLevels,
      adapters:{godot:{coordinateSystem:'X_EAST_Y_UP_Z_SOUTH',metersPerUnit:1},
        unity:{coordinateSystem:'X_EAST_Y_UP_Z_NORTH',metersPerUnit:1,requiresHandednessConversion:true},
        unreal:{coordinateSystem:'X_EAST_Y_NORTH_Z_UP',centimetersPerMeter:100,requiresAxisConversion:true}},
      outputBytes:bytes,tiles};
    const serialized=Buffer.from(JSON.stringify(manifest,null,2)+'\n','utf8');
    if(bytes+serialized.length>spec.maxOutputBytes)fail('OUTPUT_BUDGET_EXCEEDED');
    await writeDurable(join(stage,'manifest.json'),serialized);
    await syncDir(stage);checkAbort(signal);
    try{await rename(stage,target);}catch(error){
      if(error?.code==='EEXIST'||error?.code==='ENOTEMPTY')fail('CONCURRENT_WORLD_PUBLICATION');
      throw error;
    }
    await syncDir(root);
    return manifest;
  }finally{await rm(stage,{recursive:true,force:true});}
}
