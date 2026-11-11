/** GeoWorld -> narrative bridge: deterministic proximity triggers for Android scenes.
 * All positions are local meters; no location permissions or GPS required.
 */
const ID=/^[A-Za-z][A-Za-z0-9_-]{0,95}$/;
const finite=n=>typeof n==='number'&&Number.isFinite(n);
function validate(zones){
 if(!Array.isArray(zones)||zones.length>10000)throw Error('INVALID_ZONES');
 const seen=new Set();
 return zones.map(z=>{
  if(!z||!ID.test(z.id)||seen.has(z.id)||!ID.test(z.sceneId)||
    !finite(z.x)||!finite(z.z)||!finite(z.radius)||z.radius<=0||z.radius>10000||
    !Number.isSafeInteger(z.priority??0)||Math.abs(z.priority??0)>100000||
    (z.requires!==undefined&&(!Array.isArray(z.requires)||z.requires.some(r=>!r||!ID.test(r.flag)||typeof r.equals!=='boolean'))))
    throw Error('INVALID_ZONE');
  seen.add(z.id);
  return {id:z.id,sceneId:z.sceneId,x:z.x,z:z.z,radius:z.radius,priority:z.priority??0,
    requires:(z.requires??[]).map(r=>({flag:r.flag,equals:r.equals}))};
 });
}
export class GeoNarrativeTriggerIndex{
 #zones;#activated=new Set();
 constructor(zones,{activated=[]}={}){
  this.#zones=validate(zones);
  if(!Array.isArray(activated)||activated.length>zones.length)throw Error('INVALID_CHECKPOINT');
  const ids=new Set(this.#zones.map(z=>z.id));
  for(const id of activated){if(!ids.has(id)||this.#activated.has(id))throw Error('INVALID_CHECKPOINT');this.#activated.add(id);}
 }
 evaluate({x,z,flags={}}){
  if(!finite(x)||!finite(z)||!flags||typeof flags!=='object'||Array.isArray(flags))throw Error('INVALID_POSITION');
  return this.#zones.filter(zone=>!this.#activated.has(zone.id)&&
   (x-zone.x)**2+(z-zone.z)**2<=zone.radius**2&&
   zone.requires.every(r=>flags[r.flag]===r.equals))
   .sort((a,b)=>b.priority-a.priority||a.id.localeCompare(b.id,'en'))
   .map(z=>({id:z.id,sceneId:z.sceneId}));
 }
 activate(zoneId){
  if(!this.#zones.some(z=>z.id===zoneId))throw Error('ZONE_NOT_FOUND');
  if(this.#activated.has(zoneId))return false;
  this.#activated.add(zoneId);return true;
 }
 checkpoint(){return {activated:[...this.#activated].sort()};}
}
