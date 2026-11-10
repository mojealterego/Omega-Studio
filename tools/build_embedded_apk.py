"""SDK-independent DEX/AXML packaging for a self-contained Android system-shell controller.

This is NOT a Termux distribution: it uses Android's /system/bin/sh. No emulator is
available in the build container. DEX annotation and APK v2 checks are structural.
"""
from __future__ import annotations
import hashlib
import io
import json
import struct
import zlib
import zipfile
from pathlib import Path
from tools.apk_signing import U16,U32,uleb,aligned,make_axml,_sign_v2,verify_apk

ROOT=Path(__file__).resolve().parents[1]
CD='Lorg/omega/actions/MainActivity;'
BD='Lorg/omega/actions/NativeBridge;'
INIT='<init>'
V='V'; S='Ljava/lang/String;'; Z='Z'; I='I'
OBJECT='Ljava/lang/Object;'; ACTIVITY='Landroid/app/Activity;'
WEBVIEW='Landroid/webkit/WebView;'; SETTINGS='Landroid/webkit/WebSettings;'
PROCESSBUILDER='Ljava/lang/ProcessBuilder;'; PROCESS='Ljava/lang/Process;'
SCANNER='Ljava/util/Scanner;'; STREAM='Ljava/io/InputStream;'
ARRAY='[Ljava/lang/String;'; BUNDLE='Landroid/os/Bundle;'
ANNOTATION='Landroid/webkit/JavascriptInterface;'

# method entries: declaring class, name, return type, parameters
SPECS=[
 (OBJECT,INIT,V,()),
 (ACTIVITY,INIT,V,()),
 (ACTIVITY,'onCreate',V,(BUNDLE,)),
 (ACTIVITY,'setContentView',V,('Landroid/view/View;',)),
 (WEBVIEW,INIT,V,('Landroid/content/Context;',)),
 (WEBVIEW,'getSettings',SETTINGS,()),
 (WEBVIEW,'addJavascriptInterface',V,(OBJECT,S)),
 (WEBVIEW,'loadUrl',V,(S,)),
 (SETTINGS,'setJavaScriptEnabled',V,(Z,)),
 (SETTINGS,'setDomStorageEnabled',V,(Z,)),
 (SETTINGS,'setAllowFileAccess',V,(Z,)),
 (SETTINGS,'setAllowFileAccessFromFileURLs',V,(Z,)),
 (SETTINGS,'setAllowUniversalAccessFromFileURLs',V,(Z,)),
 (PROCESSBUILDER,INIT,V,(ARRAY,)),
 (PROCESSBUILDER,'redirectErrorStream',PROCESSBUILDER,(Z,)),
 (PROCESSBUILDER,'start',PROCESS,()),
 (PROCESS,'getInputStream',STREAM,()),
 (PROCESS,'waitFor',I,()),
 (SCANNER,INIT,V,(STREAM,)),
 (SCANNER,'useDelimiter',SCANNER,(S,)),
 (SCANNER,'hasNext',Z,()),
 (SCANNER,'next',S,()),
 (SCANNER,'close',V,()),
 (CD,INIT,V,()),
 (CD,'onCreate',V,(BUNDLE,)),
 (BD,INIT,V,()),
 (BD,'run',S,(S,)),
]
STRINGS=['MainActivity.java','NativeBridge.java','file:///android_asset/index.html',
         'omega','/system/bin/sh','-c',r'\A','']


def dex()->bytes:
    types=sorted(set([CD,BD,ACTIVITY,OBJECT,ANNOTATION]+[x for c,n,r,ps in SPECS for x in (c,r,*ps)]))
    tid={v:i for i,v in enumerate(types)}
    shorty=lambda r,ps:('L' if r.startswith(('L','[')) else r)+''.join('L' if p.startswith(('L','[')) else p for p in ps)
    strings=sorted(set(types+STRINGS+[n for c,n,r,ps in SPECS]+[shorty(r,ps) for c,n,r,ps in SPECS]))
    sid={v:i for i,v in enumerate(strings)}
    protos=sorted(set((r,ps) for c,n,r,ps in SPECS),key=lambda x:(tid[x[0]],tuple(tid[t] for t in x[1])))
    pid={v:i for i,v in enumerate(protos)}
    methods=sorted(SPECS,key=lambda x:(tid[x[0]],sid[x[1]],pid[(x[2],x[3])]))
    mid={v:i for i,v in enumerate(methods)}
    offsets={};offset=0x70
    for name,count,width in [('string',len(strings),4),('type',len(types),4),('proto',len(protos),12),('method',len(methods),8),('class',2,32)]:
        offsets[name]=offset;offset+=count*width
    data_off=(offset+3)&~3
    buf=bytearray(b'\0'*data_off)
    string_offsets=[]
    for s in strings:
        string_offsets.append(len(buf));raw=s.encode('utf-8')
        buf.extend(uleb(len(s.encode('utf-16-le'))//2)+raw+b'\0')
    typelist={}
    for _,ps in protos:
        if not ps or ps in typelist:continue
        aligned(buf);typelist[ps]=len(buf)
        buf.extend(U32(len(ps))+b''.join(U16(tid[p]) for p in ps));aligned(buf)
    aligned(buf)
    def op35(op,regs,key):
        if key not in mid:raise KeyError(key)
        regs=list(regs)
        if len(regs)>5 or max(regs,default=0)>15:raise ValueError('dex 35c overflow')
        v=regs+[0]*(5-len(regs))
        return [op|(len(regs)<<12)|(v[4]<<8),mid[key],v[0]|(v[1]<<4)|(v[2]<<8)|(v[3]<<12)]
    def cs(reg,s):return [0x1a|(reg<<8),sid[s]]
    def ci(reg,v):return [0x12|(reg<<8)|((v&15)<<12)]
    def new(reg,cls):return [0x22|(reg<<8),tid[cls]]
    def arr(reg,size,cls):return [0x23|(reg<<8)|(size<<12),tid[cls]]
    def put(value,index,array):return [0x4d|(value<<8),index|(array<<8)]
    def moveobject(reg):return [0x0c|(reg<<8)]
    def moveresult(reg):return [0x0a|(reg<<8)]
    def call(op,regs,c,n,r,params=()):return op35(op,regs,(c,n,r,params))
    codes={}
    codes[(CD,INIT)]=(1,1,1,[*call(0x70,[0],ACTIVITY,INIT,V),0x0e])
    main=[
      *call(0x6f,[4,5],ACTIVITY,'onCreate',V,(BUNDLE,)),
      *new(0,WEBVIEW),*call(0x70,[0,4],WEBVIEW,INIT,V,('Landroid/content/Context;',)),
      *call(0x6e,[4,0],ACTIVITY,'setContentView',V,('Landroid/view/View;',)),
      *call(0x6e,[0],WEBVIEW,'getSettings',SETTINGS),*moveobject(1),
      *ci(2,1),*call(0x6e,[1,2],SETTINGS,'setJavaScriptEnabled',V,(Z,)),
      *ci(2,1),*call(0x6e,[1,2],SETTINGS,'setDomStorageEnabled',V,(Z,)),
      *ci(2,1),*call(0x6e,[1,2],SETTINGS,'setAllowFileAccess',V,(Z,)),
      *ci(2,0),*call(0x6e,[1,2],SETTINGS,'setAllowFileAccessFromFileURLs',V,(Z,)),
      *call(0x6e,[1,2],SETTINGS,'setAllowUniversalAccessFromFileURLs',V,(Z,)),
      *new(1,BD),*call(0x70,[1],BD,INIT,V),*cs(2,'omega'),
      *call(0x6e,[0,1,2],WEBVIEW,'addJavascriptInterface',V,(OBJECT,S)),
      *cs(1,'file:///android_asset/index.html'),*call(0x6e,[0,1],WEBVIEW,'loadUrl',V,(S,)),
      0x0e]
    codes[(CD,'onCreate')]=(6,2,3,main)
    codes[(BD,INIT)]=(1,1,1,[*call(0x70,[0],OBJECT,INIT,V),0x0e])
    # v7 = incoming command; v6 = this.
    bridge=[
        *ci(0,3),*arr(0,0,ARRAY),
        *ci(1,0),*cs(2,'/system/bin/sh'),*put(2,1,0),
        *ci(1,1),*cs(2,'-c'),*put(2,1,0),
        *ci(1,2),*put(7,1,0),
        *new(1,PROCESSBUILDER),*call(0x70,[1,0],PROCESSBUILDER,INIT,V,(ARRAY,)),
        *ci(0,1),*call(0x6e,[1,0],PROCESSBUILDER,'redirectErrorStream',PROCESSBUILDER,(Z,)),
        *call(0x6e,[1],PROCESSBUILDER,'start',PROCESS),*moveobject(1),
        *call(0x6e,[1],PROCESS,'getInputStream',STREAM),*moveobject(0),
        *new(2,SCANNER),*call(0x70,[2,0],SCANNER,INIT,V,(STREAM,)),
        *cs(0,r'\A'),*call(0x6e,[2,0],SCANNER,'useDelimiter',SCANNER,(S,)),
        *call(0x6e,[2],SCANNER,'hasNext',Z),*moveresult(0),
    ]
    # if-eqz v0 -> empty. patched after allocating dynamic offsets.
    branch_pos=len(bridge);bridge.extend([0x38,0])
    bridge.extend([*call(0x6e,[2],SCANNER,'next',S),*moveobject(3)])
    goto_pos=len(bridge);bridge.extend([0x28])
    empty_pos=len(bridge);bridge.extend(cs(3,''))
    after_pos=len(bridge)
    bridge[branch_pos+1]=(empty_pos-branch_pos)&0xffff
    if not -128<=after_pos-goto_pos<=127:raise ValueError('goto out of range')
    bridge[goto_pos]=0x28|(((after_pos-goto_pos)&0xff)<<8)
    bridge.extend([*call(0x6e,[2],SCANNER,'close',V),*call(0x6e,[1],PROCESS,'waitFor',I),*moveresult(0),0x11|(3<<8)])
    codes[(BD,'run')]=(8,2,2,bridge)
    code_offsets={}
    for cls,name in [(CD,INIT),(CD,'onCreate'),(BD,INIT),(BD,'run')]:
        aligned(buf);code_offsets[(cls,name)]=len(buf)
        regs,ins,outs,instructions=codes[(cls,name)]
        buf.extend(struct.pack('<HHHHII',regs,ins,outs,0,0,len(instructions)))
        buf.extend(struct.pack('<'+'H'*len(instructions),*instructions))
    class_data_offsets={}
    for cls in (CD,BD):
        aligned(buf);class_data_offsets[cls]=len(buf)
        ctor=mid[(cls,INIT,V,())]; method_name='onCreate' if cls==CD else 'run'
        ret,params=(V,(BUNDLE,)) if cls==CD else (S,(S,))
        method=mid[(cls,method_name,ret,params)]
        flag=0x0004 if cls==CD else 0x0001
        buf.extend(uleb(0)+uleb(0)+uleb(1)+uleb(1))
        buf.extend(uleb(ctor)+uleb(0x10001)+uleb(code_offsets[(cls,INIT)]))
        buf.extend(uleb(method)+uleb(flag)+uleb(code_offsets[(cls,method_name)]))
    annotation_item_off=len(buf)
    buf.extend(bytes([1])+uleb(tid[ANNOTATION])+uleb(0))
    aligned(buf)
    annotation_set_off=len(buf);buf.extend(U32(1)+U32(annotation_item_off))
    aligned(buf)
    annotation_directory_off=len(buf)
    buf.extend(U32(0)+U32(0)+U32(1)+U32(0)+U32(mid[(BD,'run',S,(S,))])+U32(annotation_set_off))
    aligned(buf);map_off=len(buf)
    map_entries=[(0x0000,1,0),(0x0001,len(strings),offsets['string']),
                 (0x0002,len(types),offsets['type']),(0x0003,len(protos),offsets['proto']),
                 (0x0005,len(methods),offsets['method']),(0x0006,2,offsets['class']),
                 (0x2002,len(strings),string_offsets[0])]
    if typelist:map_entries.append((0x1001,len(typelist),min(typelist.values())))
    map_entries.extend([(0x2001,4,min(code_offsets.values())),(0x2000,2,min(class_data_offsets.values())),
                        (0x2004,1,annotation_item_off),(0x1003,1,annotation_set_off),
                        (0x2006,1,annotation_directory_off),(0x1000,1,map_off)])
    map_entries.sort(key=lambda x:x[2]);buf.extend(U32(len(map_entries)))
    for typ,count,off in map_entries:buf.extend(struct.pack('<HHII',typ,0,count,off))
    for i,off in enumerate(string_offsets):struct.pack_into('<I',buf,offsets['string']+i*4,off)
    for i,t in enumerate(types):struct.pack_into('<I',buf,offsets['type']+i*4,sid[t])
    for i,(r,ps) in enumerate(protos):struct.pack_into('<III',buf,offsets['proto']+i*12,sid[shorty(r,ps)],tid[r],typelist.get(ps,0))
    for i,(c,n,r,ps) in enumerate(methods):struct.pack_into('<HHI',buf,offsets['method']+i*8,tid[c],pid[(r,ps)],sid[n])
    for i,cls in enumerate(sorted((CD,BD),key=lambda x:tid[x])):
        source=sid['MainActivity.java' if cls==CD else 'NativeBridge.java']
        superclass=ACTIVITY if cls==CD else OBJECT
        annotations=annotation_directory_off if cls==BD else 0
        struct.pack_into('<8I',buf,offsets['class']+i*32,tid[cls],1,tid[superclass],0,source,annotations,class_data_offsets[cls],0)
    buf[:8]=b'dex\n035\0'
    struct.pack_into('<20I',buf,32,len(buf),0x70,0x12345678,0,0,map_off,
                     len(strings),offsets['string'],len(types),offsets['type'],len(protos),offsets['proto'],
                     0,0,len(methods),offsets['method'],2,offsets['class'],len(buf)-data_off,data_off)
    buf[12:32]=hashlib.sha1(buf[32:]).digest()
    struct.pack_into('<I',buf,8,zlib.adler32(buf[12:])&0xffffffff)
    return bytes(buf)


def build(output:Path)->dict:
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    data=io.BytesIO()
    asset_root=ROOT/'android/app/src/main/assets'
    with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as apk:
        apk.writestr('AndroidManifest.xml',make_axml())
        apk.writestr('classes.dex',dex())
        native=ROOT/'android/app/src/main/jniLibs/arm64-v8a/libomega_runtime.so'
        if not native.is_file():
            raise RuntimeError('Native ARM64 ELF must be built before APK packaging')
        if native.read_bytes()[:4]!=b'\x7fELF' or int.from_bytes(native.read_bytes()[18:20], 'little')!=183:
            raise RuntimeError('Native library is not AArch64 ELF')
        apk.write(native,'lib/arm64-v8a/libomega_runtime.so',compress_type=zipfile.ZIP_STORED)
        for name in ('index.html','app.css','app.js','builder.js','builder-ui.js'):
            apk.write(asset_root/name,'assets/'+name)
    output.write_bytes(_sign_v2(data.getvalue()))
    verify_apk(output)
    return {'path':str(output),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'size_bytes':output.stat().st_size,'signed_v2':True,'classes':2,
            'native_elf_arm64':True,'runtime_complete':False,
            'runtime':'Offline editor + NoCode AppBuilder + Android system shell; no Termux/Python/Git bootstrap'}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('output',type=Path)
    print(json.dumps(build(p.parse_args().output),indent=2))
