package org.omega.actions.core;

/** JNI access to the freestanding AArch64 native integrity probe. */
public final class OmegaNative {
    private static final boolean LOADED;
    static {
        boolean loaded;
        try { System.loadLibrary("omega_runtime"); loaded = true; }
        catch (UnsatisfiedLinkError e) { loaded = false; }
        LOADED = loaded;
    }
    private OmegaNative() { }
    public static boolean available() { return LOADED; }
    public static int version() { return LOADED ? abiVersion() : 0; }
    private static native int abiVersion();
}
