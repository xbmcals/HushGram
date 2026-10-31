package app.hushgram.extension.shared;

import android.annotation.SuppressLint;
import android.annotation.TargetApi;
import android.app.Application;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.content.pm.SigningInfo;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.net.Uri;
import android.os.Build;
import android.os.Process;
import android.provider.MediaStore;
import android.view.DisplayCutout;
import android.view.View;
import android.view.WindowInsets;

import java.io.FileInputStream;
import java.nio.charset.StandardCharsets;

/**
 * Guarded wrappers so the code runs on Android 8.0/8.1 (API 26/27).
 * Generated into the build by scripts/api26/apply.py; not part of upstream.
 *
 * The real API 28/29 calls live in nested @TargetApi classes so that older
 * runtimes never have to verify them unless the SDK_INT check passes.
 */
public final class Api26Compat {
    private Api26Compat() {}

    private static final int SDK = Build.VERSION.SDK_INT;

    /** Flags for getPackageInfo() that return signatures on every version. */
    @SuppressLint("InlinedApi")
    public static final int SIGNING_FLAGS = SDK >= 28
            ? PackageManager.GET_SIGNING_CERTIFICATES
            : PackageManager.GET_SIGNATURES;

    // ---- PackageInfo -------------------------------------------------------

    @SuppressWarnings("deprecation")
    public static long longVersionCode(PackageInfo info) {
        return SDK >= 28 ? Api28.longVersionCode(info) : info.versionCode;
    }

    public static SigningInfo signingInfo(PackageInfo info) {
        return SDK >= 28 ? Api28.signingInfo(info) : null;
    }

    @SuppressWarnings("deprecation")
    public static Signature[] apkContentsSigners(PackageInfo info, SigningInfo signing) {
        if (SDK >= 28 && signing != null) return Api28.signers(signing);
        return info.signatures;
    }

    // ---- Process -----------------------------------------------------------

    public static String processName() {
        if (SDK >= 28) return Api28.processName();
        try {
            Class<?> at = Class.forName("android.app.ActivityThread");
            Object name = at.getDeclaredMethod("currentProcessName").invoke(null);
            if (name instanceof String) return (String) name;
        } catch (Throwable ignored) {
            // fall through
        }
        return cmdlineProcessName();
    }

    public static boolean isIsolated() {
        if (SDK >= 28) return Api28.isIsolated();
        int appId = Process.myUid() % 100000;
        return appId >= 99000 && appId <= 99999;
    }

    private static String cmdlineProcessName() {
        try (FileInputStream in = new FileInputStream("/proc/self/cmdline")) {
            byte[] buf = new byte[256];
            int n = in.read(buf);
            if (n <= 0) return null;
            int end = 0;
            while (end < n && buf[end] != 0) end++;
            return new String(buf, 0, end, StandardCharsets.UTF_8);
        } catch (Throwable t) {
            return null;
        }
    }

    // ---- Views -------------------------------------------------------------

    public static void resetPivot(View v) {
        if (SDK >= 28) {
            Api28.resetPivot(v);
        } else {
            v.setPivotX(v.getWidth() / 2f);
            v.setPivotY(v.getHeight() / 2f);
        }
    }

    public static void setHeading(View v, boolean heading) {
        if (SDK >= 28) Api28.heading(v, heading);
    }

    public static void setPaneTitle(View v, CharSequence title) {
        if (SDK >= 28) Api28.paneTitle(v, title);
    }

    // ---- Display cutout (none exists below 28) -----------------------------

    public static DisplayCutout displayCutout(WindowInsets insets) {
        return SDK >= 28 ? Api28.cutout(insets) : null;
    }

    public static int safeInsetLeft(DisplayCutout c) {
        return SDK >= 28 && c != null ? Api28.left(c) : 0;
    }

    public static int safeInsetTop(DisplayCutout c) {
        return SDK >= 28 && c != null ? Api28.top(c) : 0;
    }

    public static int safeInsetRight(DisplayCutout c) {
        return SDK >= 28 && c != null ? Api28.right(c) : 0;
    }

    public static int safeInsetBottom(DisplayCutout c) {
        return SDK >= 28 && c != null ? Api28.bottom(c) : 0;
    }

    // ---- Fonts -------------------------------------------------------------

    /** Below API 28 there are no numeric weights: 600+ maps to bold, rest to normal. */
    public static Typeface createTypeface(Typeface base, int weight, boolean italic) {
        if (SDK >= 28) return Api28.create(base, weight, italic);
        int style = weight >= 600
                ? (italic ? Typeface.BOLD_ITALIC : Typeface.BOLD)
                : (italic ? Typeface.ITALIC : Typeface.NORMAL);
        return Typeface.create(base, style);
    }

    public static int typefaceWeight(Typeface t) {
        if (SDK >= 28) return Api28.weight(t);
        return t != null && t.isBold() ? 700 : 400;
    }

    // ---- Drawables / MediaStore -------------------------------------------

    public static boolean isProjected(Drawable d) {
        return SDK >= 29 && Api29.isProjected(d);
    }

    /**
     * MediaStore.Downloads is API 29+. Below that we hand back the generic
     * external Files collection; inserting there needs WRITE_EXTERNAL_STORAGE
     * and ignores RELATIVE_PATH, so exports may not work on 8.x.
     */
    public static Uri downloadsUri() {
        return SDK >= 29 ? Api29.downloads() : MediaStore.Files.getContentUri("external");
    }

    // ---- Real API calls, isolated --------------------------------------------

    @TargetApi(28)
    private static final class Api28 {
        static long longVersionCode(PackageInfo i) { return i.getLongVersionCode(); }
        static SigningInfo signingInfo(PackageInfo i) { return i.signingInfo; }
        static Signature[] signers(SigningInfo s) { return s.getApkContentsSigners(); }
        static String processName() { return Application.getProcessName(); }
        static boolean isIsolated() { return Process.isIsolated(); }
        static void resetPivot(View v) { v.resetPivot(); }
        static void heading(View v, boolean h) { v.setAccessibilityHeading(h); }
        static void paneTitle(View v, CharSequence t) { v.setAccessibilityPaneTitle(t); }
        static DisplayCutout cutout(WindowInsets i) { return i.getDisplayCutout(); }
        static int left(DisplayCutout c) { return c.getSafeInsetLeft(); }
        static int top(DisplayCutout c) { return c.getSafeInsetTop(); }
        static int right(DisplayCutout c) { return c.getSafeInsetRight(); }
        static int bottom(DisplayCutout c) { return c.getSafeInsetBottom(); }
        static Typeface create(Typeface b, int w, boolean i) { return Typeface.create(b, w, i); }
        static int weight(Typeface t) { return t.getWeight(); }
    }

    @TargetApi(29)
    private static final class Api29 {
        static boolean isProjected(Drawable d) { return d.isProjected(); }
        static Uri downloads() { return MediaStore.Downloads.EXTERNAL_CONTENT_URI; }
    }
}
