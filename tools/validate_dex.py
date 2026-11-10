"""Check Dex 035 header, class definitions, code ranges, annotations and control-flow targets."""
from __future__ import annotations
import hashlib
import struct
import zlib
from pathlib import Path
from tools.build_embedded_apk import CD,BD,ANNOTATION


def read_uleb(data:bytes,offset:int)->tuple[int,int]:
    val=0
    for shift in range(0,35,7):
        b=data[offset];offset+=1;val+=(b&127)<<shift
        if b<128:return val,offset
    raise ValueError('ULEB128 too long')


def verify_dex(raw:bytes)->dict:
    if raw[:8]!=b'dex\n035\0':raise ValueError('Invalid magic')
    if struct.unpack_from('<I',raw,8)[0]!=(zlib.adler32(raw[12:])&0xffffffff):raise ValueError('Bad DEX adler32')
    if raw[12:32]!=hashlib.sha1(raw[32:]).digest():raise ValueError('Bad DEX SHA-1')
    (size,header,endian,link_size,link_off,map_off,
     sc,so,tc,to,pc,po,fc,fo,mc,mo,cc,co,ds,do)=struct.unpack_from('<20I',raw,32)
    if size!=len(raw) or header!=0x70 or endian!=0x12345678 or cc!=2 or mc<4:
        raise ValueError('DEX header invalid')
    strings=[]
    for i in range(sc):
        off=struct.unpack_from('<I',raw,so+i*4)[0]
        count,off=read_uleb(raw,off)
        end=raw.index(0,off)
        value=raw[off:end].decode('utf-8')
        if len(value.encode('utf-16-le'))//2!=count:raise ValueError('String length mismatch')
        strings.append(value)
    types=[strings[struct.unpack_from('<I',raw,to+i*4)[0]] for i in range(tc)]
    method_names=[]
    for i in range(mc):
        cls,proto,name=struct.unpack_from('<HHI',raw,mo+i*8)
        method_names.append((types[cls],strings[name]))
    cls_info={};total_methods=0;annotated=[]
    for i in range(cc):
        typ,access,superclass,ifaces,source,ann,cldata,statics=struct.unpack_from('<8I',raw,co+i*32)
        name=types[typ]
        if name in cls_info:raise ValueError('Repeated DEX class')
        cls_info[name]={"source":strings[source],"annotations":ann,"methods":[]}
        pos=cldata
        static_count,pos=read_uleb(raw,pos);instance_count,pos=read_uleb(raw,pos)
        direct_count,pos=read_uleb(raw,pos);virtual_count,pos=read_uleb(raw,pos)
        if static_count or instance_count or direct_count!=1 or virtual_count!=1:raise ValueError('Unexpected class data')
        for j in range(2):
            diff,pos=read_uleb(raw,pos);flags,pos=read_uleb(raw,pos);offset,pos=read_uleb(raw,pos)
            idx=diff
            if method_names[idx][0]!=name:raise ValueError('Method owner mismatch')
            cls_info[name]['methods'].append(method_names[idx][1]);total_methods+=1
            if offset%4:raise ValueError('Unaligned code')
            regs,ins,outs,tries,dbg,units=struct.unpack_from('<HHHHII',raw,offset)
            if tries or units==0 or offset+16+2*units>len(raw):raise ValueError('Invalid code item')
            instructions=struct.unpack_from('<'+'H'*units,raw,offset+16)
            pc2=0;boundaries=set();branches=[]
            widths={0x6e:3,0x6f:3,0x70:3,0x1a:2,0x22:2,0x23:2,0x38:2,0x4d:2,
                    0x0e:1,0x0c:1,0x0a:1,0x12:1,0x11:1,0x28:1}
            while pc2<units:
                boundaries.add(pc2);op=instructions[pc2]&255
                if op not in widths:raise ValueError('Unexpected opcode '+hex(op))
                width=widths[op]
                if pc2+width>units:raise ValueError('Truncated instruction')
                if op==0x38:
                    delta=struct.unpack('<h',struct.pack('<H',instructions[pc2+1]))[0]
                    branches.append(pc2+delta)
                if op==0x28:
                    d=(instructions[pc2]>>8)&255
                    if d>=128:d-=256
                    branches.append(pc2+d)
                pc2+=width
            if pc2!=units or any(b not in boundaries for b in branches):raise ValueError('Invalid branch target')
        if ann:
            class_a,fields,methods_count,params=struct.unpack_from('<4I',raw,ann)
            if class_a or fields or params or methods_count!=1:raise ValueError('Unexpected annotations')
            method_idx,set_off=struct.unpack_from('<2I',raw,ann+16)
            if method_names[method_idx]!=(BD,'run'):raise ValueError('Wrong annotated method')
            count=struct.unpack_from('<I',raw,set_off)[0]
            annot_off=struct.unpack_from('<I',raw,set_off+4)[0]
            visibility=raw[annot_off]
            tidx,pos=read_uleb(raw,annot_off+1)
            pair_count,pos=read_uleb(raw,pos)
            if count!=1 or visibility!=1 or pair_count!=0 or types[tidx]!=ANNOTATION:
                raise ValueError('JavascriptInterface annotation invalid')
            annotated.append('NativeBridge.run')
    if set(cls_info)!={CD,BD} or total_methods!=4 or annotated!=['NativeBridge.run']:
        raise ValueError('Required classes/method annotations missing')
    if '127.0.0.1:8765' in strings or 'file:///android_asset/index.html' not in strings:
        raise ValueError('APK still references old backend')
    return {'dex_bytes':len(raw),'strings':len(strings),'classes':len(cls_info),
            'defined_methods':total_methods,'runtime_annotations':annotated,
            'branch_targets_valid':True,'dex_adler32_valid':True,'dex_sha1_valid':True}

if __name__=='__main__':
    import json,sys,zipfile
    with zipfile.ZipFile(sys.argv[1]) as z:print(json.dumps(verify_dex(z.read('classes.dex')),indent=2))
