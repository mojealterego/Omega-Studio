package org.omega.actions.core;

import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

public final class GgufMetadataReader {
    private GgufMetadataReader() {}
    private static final long LIMIT=8L*1024*1024;
    private static final long MAX_STRING=1024L*1024;
    private static final long MAX_ARRAY=100000;

    public static Map<String,Object> inspect(File file) throws IOException {
        try(RandomAccessFile f=new RandomAccessFile(file,"r")){
            if(f.length()<24||f.read()!=71||f.read()!=71||f.read()!=85||f.read()!=70)throw new IOException("Not a GGUF file");
            long version=u32(f),tensors=u64(f),count=u64(f);
            if(version!=2&&version!=3)throw new IOException("Unsupported GGUF version");
            if(count>100000)throw new IOException("Too many GGUF keys");
            Map<String,Object> meta=new LinkedHashMap<>();
            for(long i=0;i<count;i++){
                String key=string(f);
                if(meta.containsKey(key))throw new IOException("Duplicate GGUF key");
                meta.put(key,value(f,u32(f),0));
            }
            Map<String,Object> result=new LinkedHashMap<>();
            result.put("version",version);result.put("tensor_count",tensors);result.put("metadata_count",count);
            result.put("metadata",meta);result.put("bytes",f.length());return result;
        }
    }
    private static void require(RandomAccessFile f,long n)throws IOException{
        if(n<0||n>f.length()-f.getFilePointer()||n>LIMIT-f.getFilePointer())throw new IOException("GGUF metadata bounds exceeded");
    }
    private static long u32(RandomAccessFile f)throws IOException{
        require(f,4);long a=f.readUnsignedByte(),b=f.readUnsignedByte(),c=f.readUnsignedByte(),d=f.readUnsignedByte();return a|(b<<8)|(c<<16)|(d<<24);
    }
    private static long u64(RandomAccessFile f)throws IOException{
        long a=u32(f),b=u32(f);if(b>0x1fffff)throw new IOException("GGUF integer exceeds safe range");return a|(b<<32);
    }
    private static String string(RandomAccessFile f)throws IOException{
        long n=u64(f);if(n>MAX_STRING)throw new IOException("GGUF string too long");require(f,n);
        byte[] b=new byte[(int)n];f.readFully(b);return new String(b,StandardCharsets.UTF_8);
    }
    private static Object value(RandomAccessFile f,long type,int depth)throws IOException{
        if(depth>2)throw new IOException("GGUF array nesting exceeded");
        if(type==8)return string(f);
        if(type==9){long element=u32(f),count=u64(f);if(count>MAX_ARRAY)throw new IOException("GGUF array too large");
            if(count>16){for(long i=0;i<count;i++)value(f,element,depth+1);return "["+count+" values]";}
            java.util.List<Object> out=new java.util.ArrayList<>();for(long i=0;i<count;i++)out.add(value(f,element,depth+1));return out;}
        int size=switch((int)type){case 0,1,7->1;case 2,3->2;case 4,5,6->4;case 10,11,12->8;default->throw new IOException("Unknown GGUF type");};
        require(f,size);long bits=0;for(int i=0;i<size;i++)bits|=((long)f.readUnsignedByte())<<(8*i);
        return switch((int)type){case 7->bits!=0;case 6->Float.intBitsToFloat((int)bits);case 12->Double.longBitsToDouble(bits);
            case 1->(int)(byte)bits;case 3->(int)(short)bits;case 5->(int)bits;case 11->bits;
            default->bits;};
    }
}
