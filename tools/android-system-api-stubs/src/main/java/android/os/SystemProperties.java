package android.os;

/** Compile-only declaration; the implementation is supplied by Android. */
public final class SystemProperties {
    private SystemProperties() {}

    public static String get(String key, String defaultValue) {
        throw new UnsupportedOperationException("Android system API stub");
    }
}
