#!/usr/bin/env python3
"""Rewrite HushGram's API 28/29 calls so the build runs on Android 8.x (API 26).

Usage: python3 scripts/api26/apply.py [repo_root]

Safe to run repeatedly: already-rewritten code no longer matches the rules.
Lint (lintDebug) is the real safety net; anything this script misses shows up there.
"""
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
    # Signing: assumes the local variable is called `info`, as in upstream today.
    ("PackageInfo.signingInfo", "InstagramSignature.java",
     r"\b(\w+)\.signingInfo\b(?!\()", r"Api26Compat.signingInfo(\1)"),
    ("SigningInfo.getApkContentsSigners", "InstagramSignature.java",
     r"\b(\w+)\.getApkContentsSigners\(\)", r"Api26Compat.apkContentsSigners(info, \1)"),
    ("GET_SIGNING_CERTIFICATES flag", None,
     r"\bPackageManager\.GET_SIGNING_CERTIFICATES\b", "Api26Compat.SIGNING_FLAGS"),
]

# Files whose rewrite is best-effort and deserves a human look.
REVIEW = {
    "InstagramSignature.java":
        "signature trust check: on API <28 only current signers are available (no key-rotation history). "
        "If the code returns early when signingInfo is null, make sure that doesn't skip the fallback.",
    "ChatExport.java":
        "chat export: below API 29 this inserts into the generic Files collection; "
        "needs WRITE_EXTERNAL_STORAGE and may fail on 8.x.",
    "Fonts.java":
        "fonts: numeric weights collapse to normal/bold below API 28.",
}


def warn(msg):
    print(f"::warning::{msg}")


def main():
    if not (ROOT / "extensions").is_dir():
        sys.exit(f"No extensions/ directory under {ROOT}")

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

    print("== API 26 compat: rewrites ==")
    for name, n in counts.items():
        print(f"{n:4d}  {name}")
        if n == 0:
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
