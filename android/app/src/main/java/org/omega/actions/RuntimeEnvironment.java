package org.omega.actions;

import java.io.File;
import java.io.IOException;
import java.util.Map;

/** Consistent app-private Termux process environment, without inherited injection variables. */
public final class RuntimeEnvironment {
    private RuntimeEnvironment() {}

    public static void configure(Map<String,String> env, File filesDir) throws IOException {
        File prefix = new File(filesDir,"usr");
        File home = new File(filesDir,"home");
        File tmp = new File(prefix,"tmp");
        File cache = new File(home,".cache");
        if ((!home.isDirectory() && !home.mkdirs()) || (!tmp.isDirectory() && !tmp.mkdirs()) ||
            (!cache.isDirectory() && !cache.mkdirs())) throw new IOException("Cannot initialize runtime directories");
        for (String key : new String[]{"LD_PRELOAD","LD_AUDIT","PYTHONHOME","PYTHONPATH","NODE_OPTIONS",
                "BASH_ENV","ENV","GIT_CONFIG_GLOBAL","GIT_CONFIG_SYSTEM"}) env.remove(key);
        env.put("PREFIX",prefix.getAbsolutePath());
        env.put("HOME",home.getAbsolutePath());
        env.put("TMPDIR",tmp.getAbsolutePath());
        env.put("XDG_CACHE_HOME",cache.getAbsolutePath());
        env.put("PATH",new File(prefix,"bin").getAbsolutePath()+":/system/bin");
        env.put("LD_LIBRARY_PATH",new File(prefix,"lib").getAbsolutePath());
        env.put("LANG","en_US.UTF-8");
        env.put("TERM","xterm-256color");
    }
}
