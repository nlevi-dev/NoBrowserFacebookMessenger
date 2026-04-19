#!/usr/bin/env python3
"""
Patches Messenger APK (decompiled with apktool) to open links in the system
browser instead of the in-app BrowserLiteActivity.

Locates the target method by structural signature + stable string fingerprints,
so it works even when obfuscated class/method names change between versions.

Usage:
    python3 patch_messenger_browser.py <decompile_dir>
"""

import re
import sys
import shutil
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Stable string literals present in the target method body.
# These are log strings unlikely to change between app versions.
# ---------------------------------------------------------------------------
METHOD_FINGERPRINTS = [
    "MessengerBrowserLauncher",
    "Start launchIABIntent. requestCode: ",
    "launchActivity_returned_false",
    "iab_cookies_available",
]

# Structural signature: framework types are stable, obfuscated types use \w+/[^;]+
METHOD_SIG_PATTERN = re.compile(
    r"\.method public static \w+"
    r"\(Landroid/app/Activity;"
    r"Landroid/content/Context;"
    r"Landroid/content/Intent;"
    r"L[^;]+;"   # obfuscated self-type (e.g. LX/BTG;)
    r"Lcom/facebook/xapp/messaging/browser/model/MessengerInAppBrowserLaunchParam;"
    r"Ljava/lang/Integer;"
    r"\)V"
)

# ---------------------------------------------------------------------------
# Replacement - {method_name} and {self_type} are filled in at runtime
# ---------------------------------------------------------------------------
REPLACEMENT_TEMPLATE = (
    ".method public static {method_name}"
    "(Landroid/app/Activity;"
    "Landroid/content/Context;"
    "Landroid/content/Intent;"
    "{self_type}"
    "Lcom/facebook/xapp/messaging/browser/model/MessengerInAppBrowserLaunchParam;"
    "Ljava/lang/Integer;)V\n"
    "    .locals 6\n"
    "\n"
    "    # Patched: open links in system browser instead of BrowserLiteActivity\n"
    "    invoke-virtual {{p2}}, Landroid/content/Intent;->getData()Landroid/net/Uri;\n"
    "\n"
    "    move-result-object v2\n"
    "\n"
    "    if-eqz v2, :cond_skip\n"
    "\n"
    "    new-instance v0, Landroid/content/Intent;\n"
    "\n"
    '    const-string v1, "android.intent.action.VIEW"\n'
    "\n"
    "    invoke-direct {{v0, v1, v2}}, Landroid/content/Intent;-><init>(Ljava/lang/String;Landroid/net/Uri;)V\n"
    "\n"
    '    const-string v1, "android.intent.category.BROWSABLE"\n'
    "\n"
    "    invoke-virtual {{v0, v1}}, Landroid/content/Intent;->addCategory(Ljava/lang/String;)Landroid/content/Intent;\n"
    "\n"
    "    move-result-object v0\n"
    "\n"
    "    const v1, 0x10000000\n"
    "\n"
    "    invoke-virtual {{v0, v1}}, Landroid/content/Intent;->addFlags(I)Landroid/content/Intent;\n"
    "\n"
    "    move-result-object v0\n"
    "\n"
    "    invoke-virtual {{p1, v0}}, Landroid/content/Context;->startActivity(Landroid/content/Intent;)V\n"
    "\n"
    "    return-void\n"
    "\n"
    "    :cond_skip\n"
    "\n"
    "    return-void\n"
    "\n"
    ".end method"
)


def find_method_bounds(lines: list, sig: str) -> Optional[tuple]:
    """Return (start, end) line indices (inclusive) for the method matching sig."""
    start = None
    depth = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if start is None:
            if stripped == sig:
                start = i
                depth = 1
        else:
            if stripped.startswith(".method"):
                depth += 1
            elif stripped == ".end method":
                depth -= 1
                if depth == 0:
                    return start, i
    return None


def method_has_fingerprints(lines: list, start: int, end: int) -> bool:
    body = "\n".join(l.strip() for l in lines[start:end + 1])
    return all(fp in body for fp in METHOD_FINGERPRINTS)


def already_patched(lines: list, start: int, end: int) -> bool:
    return any(
        "Patched: open links in system browser" in l
        for l in lines[start:end + 1]
    )


def find_target(smali_files: list) -> Optional[tuple]:
    """
    Scan smali files for the method matching both the structural signature
    pattern and all fingerprint strings.
    Returns (file, start, end, sig_line) or None.
    """
    for smali_file in smali_files:
        try:
            text = smali_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Quick pre-filter before parsing lines
        if not all(fp in text for fp in METHOD_FINGERPRINTS):
            continue

        lines = text.splitlines(keepends=True)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if METHOD_SIG_PATTERN.match(stripped):
                bounds = find_method_bounds(lines, stripped)
                if bounds and method_has_fingerprints(lines, *bounds):
                    return smali_file, bounds[0], bounds[1], stripped

    return None


def patch(decompile_dir: str) -> None:
    root = Path(decompile_dir)
    smali_dirs = sorted(root.glob("smali*"))
    if not smali_dirs:
        sys.exit(f"ERROR: No smali directories found in {decompile_dir}")

    smali_files = [f for d in smali_dirs for f in d.rglob("*.smali")]
    print(f"Scanning {len(smali_files)} smali files...")

    result = find_target(smali_files)
    if result is None:
        sys.exit(
            "ERROR: Could not find the browser launcher method.\n"
            "The app may have changed significantly or fingerprints need updating."
        )

    target, start, end, sig_line = result
    print(f"Found target in : {target}")
    print(f"  Signature     : {sig_line}")
    print(f"  Lines         : {start + 1}-{end + 1}")

    lines = target.read_text(encoding="utf-8").splitlines(keepends=True)

    if already_patched(lines, start, end):
        print("Already patched, nothing to do.")
        return

    # Parse obfuscated method name and self-type out of the actual signature
    m = re.match(
        r"\.method public static (\w+)"
        r"\(Landroid/app/Activity;Landroid/content/Context;Landroid/content/Intent;"
        r"(L[^;]+;)",
        sig_line
    )
    if not m:
        sys.exit(f"ERROR: Could not parse signature: {sig_line}")

    method_name = m.group(1)
    self_type = m.group(2)
    print(f"  Method name   : {method_name}")
    print(f"  Self type     : {self_type}")

    replacement = REPLACEMENT_TEMPLATE.format(
        method_name=method_name,
        self_type=self_type,
    )

    backup = target.with_suffix(".smali.bak")
    shutil.copy2(target, backup)
    print(f"Backup written to: {backup}")

    new_lines = lines[:start] + [replacement + "\n"] + lines[end + 1:]
    target.write_text("".join(new_lines), encoding="utf-8")
    print("Patch applied successfully.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    patch(sys.argv[1])
