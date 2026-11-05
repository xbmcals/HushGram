#!/usr/bin/env python3
"""Rewrite HushGram's API 28/29 calls so the build runs on Android 8.x (API 26).

Usage: python3 scripts/api26/apply.py [repo_root]

Safe to run repeatedly: already-rewritten code no longer matches the rules.
Lint (lintDebug) is the real safety net; anything this script misses shows up there.
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
HERE = Path(__file__).resolve().parent
HELPER_SRC = HERE / "Api26Compat.java"
HELPER_DST = ROOT / "extensions/shared/library/src/main/java/app/hushgram/extension/shared/Api26Compat.java"
IMPORT_LINE = "import app.hushgram.extension.shared.Api26Compat;"

# (name, only_in_filename or None, regex, replacement)
RULES = [
    ("getLongVersionCode", None,
     r"\b(\w+)\.getLongVersionCode\(\)", r"Api26Compat.longVersionCode(\1)"),
    ("Application.getProcessName", None,
     r"\bApplication\.getProcessName\(\)", "Api26Compat.processName()"),
    ("Process.isIsolated", None,
     r"\bProcess\.isIsolated\(\)", "Api26Compat.isIsolated()"),
    ("Drawable.isProjected", None,
     r"\b(\w+)\.isProjected\(\)", r"Api26Compat.isProjected(\1)"),
    ("View.resetPivot", None,
     r"\b(\w+)\.resetPivot\(\)", r"Api26Compat.resetPivot(\1)"),
    ("Typeface.create(base, weight, italic)", None,
     r"\bTypeface\.create\(([^,()]+),\s*([^,()]+),\s*([^,()]+)\)",
     r"Api26Compat.createTypeface(\1, \2, \3)"),
    ("Typeface.getWeight", "Fonts.java",
     r"\b(\w+)\.getWeight\(\)", r"Api26Compat.typefaceWeight(\1)"),
    ("setAccessibilityHeading", None,
     r"\b(\w+)\.setAccessibilityHeading\(", r"Api26Compat.setHeading(\1, "),
    ("setAccessibilityPaneTitle", None,
     r"\b(\w+)\.setAccessibilityPaneTitle\(", r"Api26Compat.setPaneTitle(\1, "),
    ("WindowInsets.getDisplayCutout", None,
     r"\b(\w+)\.getDisplayCutout\(\)", r"Api26Compat.displayCutout(\1)"),
    ("DisplayCutout.getSafeInset*", None,
     r"\b(\w+)\.getSafeInset(Left|Top|Right|Bottom)\(\)", r"Api26Compat.safeInset\2(\1)"),
    ("MediaStore.Downloads.EXTERNAL_CONTENT_URI", None,
     r"\bMediaStore\.Downloads\.EXTERNAL_CONTENT_URI", "Api26Compat.downloadsUri()"),
    # THE CRASH FIX. Instagram's own check (X.01gY.A02) throws SecurityException(X.0ezk,
    # message = package name) when SDK_INT < 28 and the signer list has MORE than one entry.
    # Upstream answers with both Meta certificates [original, rotated], which is right for
    # Android 13+ but fatal on 8.x. A Play build on Android 7-12 reports only the original
    # certificate, and its hash is in Instagram's trust table. Only the own-app answer changes;
    # instagram() itself keeps both, because the family checks need both to spot Meta-signed builds.
    ("own-app signers: one cert below API 28", "InstagramSignature.java",
     r"\breturn instagram\(\);",
     "return Api26Compat.belowApi28() ? single(ORIGINAL_CERTIFICATE) : instagram();"),
    # Signing: below API 28 there is no SigningInfo and no key rotation, so the old
    # `signatures` array IS the current signer set. Without this, currentSigners()
    # returns null on 8.x and the Threads/Facebook/Messenger handoff fix never works.
    ("currentSigners legacy fallback", "InstagramSignature.java",
     r"(\n[ \t]*)SigningInfo signing = info\.signingInfo;",
     r"\1if (Api26Compat.belowApi28()) return Api26Compat.legacySigners(info);"
     r"\1SigningInfo signing = Api26Compat.signingInfo(info);"),
    # Assumes the local variable is called `info`, as in upstream today.
    ("PackageInfo.signingInfo", "InstagramSignature.java",
     r"\b(\w+)\.signingInfo\b(?!\()", r"Api26Compat.signingInfo(\1)"),
    ("SigningInfo.getApkContentsSigners", "InstagramSignature.java",
     r"\b(\w+)\.getApkContentsSigners\(\)", r"Api26Compat.apkContentsSigners(info, \1)"),
    ("GET_SIGNING_CERTIFICATES flag", None,
     r"\bPackageManager\.GET_SIGNING_CERTIFICATES\b", "Api26Compat.SIGNING_FLAGS"),
]

# Rules that are only a fallback for another rule; no warning if they match nothing.
OPTIONAL = {"PackageInfo.signingInfo"}

# Files whose rewrite is best-effort and deserves a human look.
REVIEW = {
    "InstagramSignature.java":
        "signature trust check: below API 28 only the current signer is readable (no rotation history), "
        "which is how Android 8.x works anyway. The own-app answer is unchanged.",
    "ChatExport.java":
        "chat export: below API 29 this inserts into the generic Files collection; "
        "needs WRITE_EXTERNAL_STORAGE and may fail on 8.x.",
    "Fonts.java":
        "fonts: numeric weights collapse to normal/bold below API 28.",
}


def warn(msg):
    print(f"::warning::{msg}")


# ---------------------------------------------------------------------------
# Launcher bypass: make the icon open InstagramMainActivity instead of LauncherActivity.
# The manifest of the Instagram APK is edited when Morphe Manager runs the patches, so the edit
# is injected into an EXISTING resource patch. No new patch exists, so the bundle's patch list
# and the committed metadata stay exactly as they are.
# ---------------------------------------------------------------------------
SKIP_BUILD_DIRS = {".git", ".gradle", "build", "node_modules"}
LAUNCHER_MARKER = "hushgram-skip-launcher"

# Fully qualified names throughout, so no imports are needed in the host file.
LAUNCHER_HELPERS = """

// hushgram-skip-launcher: added by scripts/api26/apply.py
private fun org.w3c.dom.Element.hgAttr(name: String): String = getAttribute("android:$name")

private fun org.w3c.dom.Element.hgChildren(tag: String): List<org.w3c.dom.Element> {
    val found = mutableListOf<org.w3c.dom.Element>()
    for (i in 0 until childNodes.length) {
        val node = childNodes.item(i)
        if (node is org.w3c.dom.Element && node.tagName == tag) found += node
    }
    return found
}

/** An intent-filter with action MAIN and category LAUNCHER: what the icon starts. */
private fun org.w3c.dom.Element.hgIsLauncherFilter(): Boolean =
    hgChildren("action").any { it.hgAttr("name") == "android.intent.action.MAIN" } &&
        hgChildren("category").any { it.hgAttr("name") == "android.intent.category.LAUNCHER" }

/** Points the icon (and icon aliases) at InstagramMainActivity. Does nothing if the manifest differs. */
private fun hushgramSkipLauncherActivity(doc: org.w3c.dom.Document) {
    val from = "com.instagram.mainactivity.LauncherActivity"
    val to = "com.instagram.mainactivity.InstagramMainActivity"
    val application = doc.getElementsByTagName("application").item(0) as? org.w3c.dom.Element ?: return
    val activities = application.hgChildren("activity")
    val launcher = activities.firstOrNull { it.hgAttr("name") == from } ?: return
    val main = activities.firstOrNull { it.hgAttr("name") == to } ?: return

    // Icon aliases keep their icon and label; only the target moves.
    application.hgChildren("activity-alias")
        .filter { it.hgAttr("targetActivity") == from }
        .forEach { it.setAttribute("android:targetActivity", to) }

    // Move the MAIN/LAUNCHER entry from LauncherActivity to InstagramMainActivity.
    launcher.hgChildren("intent-filter")
        .filter { it.hgIsLauncherFilter() }
        .forEach { filter ->
            launcher.removeChild(filter)
            main.appendChild(filter)
        }
    main.setAttribute("android:exported", "true")
}
"""

CALL_LINE = '\n        document("AndroidManifest.xml").use { hushgramSkipLauncherActivity(it) } // hushgram-skip-launcher'
EXECUTE_RE = re.compile(r"\bexecute\s*\{")


def inject_launcher_skip():
    """Add the manifest edit to an existing resourcePatch's execute block."""
    candidates = []
    for kt in sorted((ROOT / "patches").glob("**/src/main/kotlin/**/*.kt")):
        text = kt.read_text(encoding="utf-8")
        if LAUNCHER_MARKER in text:
            print(f"launcher bypass already in {kt.relative_to(ROOT)}")
            return kt
        head = text.find("resourcePatch(")
        if head < 0:
            continue
        m = EXECUTE_RE.search(text, head)
        if not m:
            continue
        # `execute { context ->` has a lambda parameter; inserting before it would break the syntax.
        if re.match(r"\s*\w+\s*->", text[m.end():m.end() + 40]):
            continue
        low = (str(kt) + text).lower()
        rank = (0 if "icon" in str(kt).lower() or "icon" in text.lower()[:600] else 1,
                0 if "AndroidManifest.xml" in text else 1)
        candidates.append((rank, kt, text, m))
    if not candidates:
        warn("launcher bypass NOT added: found no resource patch with a plain `execute {` block to host it")
        return None
    candidates.sort(key=lambda c: c[0])
    _, kt, text, m = candidates[0]
    out = text[:m.end()] + CALL_LINE + text[m.end():] + LAUNCHER_HELPERS
    kt.write_text(out, encoding="utf-8")
    print(f"launcher bypass injected into {kt.relative_to(ROOT)}")
    return kt



MIN_SDK = 26
MINSDK_RE = re.compile(r'(?i)(\bmin_?sdk(?:_?version)?\b\s*[=(\s]\s*"?)(\d+)')


def force_min_sdk():
    """Pin minSdk to 26 in the build files. A fork sync can put upstream's 28 back, and with 28
    lint rejects version checks and annotations that are only there for Android 8."""
    patterns = ["**/*.gradle", "**/*.gradle.kts", "**/*.toml", "**/gradle.properties",
                "**/buildSrc/**/*.kt", "**/buildSrc/**/*.kts", "**/build-logic/**/*.kt",
                "**/build-logic/**/*.kts"]
    seen = set()
    for pattern in patterns:
        for path in sorted(ROOT.glob(pattern)):
            if path in seen or any(part in SKIP_BUILD_DIRS for part in path.relative_to(ROOT).parts):
                continue
            seen.add(path)
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            def lower(m):
                return m.group(1) + str(MIN_SDK) if int(m.group(2)) > MIN_SDK else m.group(0)

            new = MINSDK_RE.sub(lower, text)
            if new != text:
                path.write_text(new, encoding="utf-8")
                print(f"minSdk set to {MIN_SDK} in {path.relative_to(ROOT)}")


def main():
    if not (ROOT / "extensions").is_dir():
        sys.exit(f"No extensions/ directory under {ROOT}")

    force_min_sdk()

    counts = {name: 0 for name, *_ in RULES}
    changed_files = []

    for path in sorted(ROOT.glob("extensions/**/src/main/java/**/*.java")):
        if path.name == "Api26Compat.java":
            continue
        original = path.read_text(encoding="utf-8")
        src = original
        for name, only_in, pattern, repl in RULES:
            if only_in and path.name != only_in:
                continue
            src, n = re.subn(pattern, repl, src)
            counts[name] += n
        if src != original:
            if IMPORT_LINE not in src:
                src = re.sub(r"^(package [^;]+;)", r"\1\n\n" + IMPORT_LINE, src, count=1, flags=re.M)
            path.write_text(src, encoding="utf-8")
            changed_files.append(path)

    # Install the helper class.
    HELPER_DST.parent.mkdir(parents=True, exist_ok=True)
    HELPER_DST.write_text(HELPER_SRC.read_text(encoding="utf-8"), encoding="utf-8")

    if os.environ.get("LAUNCHER_PATCH", "on").lower() == "on":
        inject_launcher_skip()
    else:
        print("launcher patch: off (workflow input launcher_patch = off)")

    print("== API 26 compat: rewrites ==")
    for name, n in counts.items():
        print(f"{n:4d}  {name}")
        if n == 0 and name not in OPTIONAL:
            warn(f"rule matched nothing (already fixed upstream, or code moved): {name}")
    print(f"{len(changed_files)} file(s) changed; helper written to {HELPER_DST.relative_to(ROOT)}")

    for path in changed_files:
        if path.name in REVIEW:
            warn(f"review {path.relative_to(ROOT)}: {REVIEW[path.name]}")

    # The instagram module has to be able to see the helper in the shared module.
    for gradle in (ROOT / "extensions/instagram").glob("build.gradle*"):
        if "shared" not in gradle.read_text(encoding="utf-8"):
            warn(f"{gradle.relative_to(ROOT)} doesn't mention the shared module; "
                 "Api26Compat may not be on its classpath.")

    # minSdk sanity check.
    for gradle in ROOT.rglob("*.gradle*"):
        if "build" in gradle.parts:
            continue
        for m in re.finditer(r"minSdk(?:Version)?\s*(?:=|\s)\s*(\d+)", gradle.read_text(encoding="utf-8")):
            if int(m.group(1)) > 26:
                warn(f"{gradle.relative_to(ROOT)} has minSdk {m.group(1)} (> 26)")


if __name__ == "__main__":
    main()
