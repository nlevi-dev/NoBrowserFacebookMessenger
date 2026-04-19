#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Usage: ./patch_and_build.sh <apk_file>
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APK="${1:-}"

if [[ -z "$APK" ]]; then
    echo "Usage: $0 <apk_file>"
    exit 1
fi

if [[ ! -f "$APK" ]]; then
    echo "ERROR: File not found: $APK"
    exit 1
fi

APK_BASENAME="$(basename "$APK")"
APK_DIR="$(cd "$(dirname "$APK")" && pwd)"
APK_FULL="$APK_DIR/$APK_BASENAME"
DECOMPILE_DIR="$SCRIPT_DIR/decompiled"
BUILT_APK="$SCRIPT_DIR/built.apk"
PATCHED_OUT="$APK_DIR/patched_$APK_BASENAME"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

get_latest_github_release_url() {
    local repo="$1" pattern="$2"
    curl -fsSL "https://api.github.com/repos/$repo/releases/latest" \
        | grep "browser_download_url" \
        | grep "$pattern" \
        | head -1 \
        | sed 's/.*"browser_download_url": "\(.*\)"/\1/'
}

ensure_jar() {
    local jar_glob="$1" repo="$2" pattern="$3"
    local found
    found="$(ls "$SCRIPT_DIR"/$jar_glob 2>/dev/null | head -1 || true)"
    if [[ -n "$found" ]]; then
        echo "$found"
        return
    fi
    echo "Downloading latest $jar_glob from $repo ..." >&2
    local url
    url="$(get_latest_github_release_url "$repo" "$pattern")"
    if [[ -z "$url" ]]; then
        echo "ERROR: Could not determine download URL for $repo" >&2
        exit 1
    fi
    local dest="$SCRIPT_DIR/$(basename "$url")"
    curl -fsSL -o "$dest" "$url"
    echo "$dest"
}

# ---------------------------------------------------------------------------
# Ensure tools
# ---------------------------------------------------------------------------

APKTOOL_JAR="$(ensure_jar "apktool_*.jar" "iBotPeaches/Apktool" "apktool_")"
SIGNER_JAR="$(ensure_jar "uber-apk-signer-*.jar" "patrickfav/uber-apk-signer" "uber-apk-signer-")"

echo "apktool : $APKTOOL_JAR"
echo "signer  : $SIGNER_JAR"

# ---------------------------------------------------------------------------
# Decompile
# ---------------------------------------------------------------------------

if [[ -d "$DECOMPILE_DIR" ]]; then
    echo "Removing existing decompile dir..."
    rm -rf "$DECOMPILE_DIR"
fi

echo "Decompiling $APK_BASENAME ..."
java -jar "$APKTOOL_JAR" d "$APK_FULL" -r -o "$DECOMPILE_DIR"

# ---------------------------------------------------------------------------
# Patch
# ---------------------------------------------------------------------------

echo "Patching..."
python3 "$SCRIPT_DIR/patch_messenger_browser.py" "$DECOMPILE_DIR"

# ---------------------------------------------------------------------------
# Recompile
# ---------------------------------------------------------------------------

echo "Recompiling..."
java -jar "$APKTOOL_JAR" b "$DECOMPILE_DIR" -o "$BUILT_APK"

# ---------------------------------------------------------------------------
# Sign
# ---------------------------------------------------------------------------

echo "Signing..."
java -jar "$SIGNER_JAR" --apks "$BUILT_APK"

# uber-apk-signer outputs <name>-aligned-debugSigned.apk next to the input
SIGNED_APK="${BUILT_APK%.apk}-aligned-debugSigned.apk"
if [[ ! -f "$SIGNED_APK" ]]; then
    # fallback: find whatever it produced
    SIGNED_APK="$(ls "${BUILT_APK%.apk}"*Signed*.apk 2>/dev/null | head -1 || true)"
fi

if [[ -z "$SIGNED_APK" || ! -f "$SIGNED_APK" ]]; then
    echo "ERROR: Could not find signed APK output"
    exit 1
fi

# ---------------------------------------------------------------------------
# Rename to final output
# ---------------------------------------------------------------------------

mv "$SIGNED_APK" "$PATCHED_OUT"

# ---------------------------------------------------------------------------
# Cleanup intermediate APKs
# ---------------------------------------------------------------------------

rm -f "$BUILT_APK" "$SIGNED_APK" "$SIGNED_APK".idsig

echo ""
echo "Done: $PATCHED_OUT"
