#!/usr/bin/env bash
# Build the Google Play bundle (.aab), signed with the UPLOAD key (Play App Signing re-signs it for users).
#   UPLOAD_KEYSTORE=/path/scanfruit-upload.keystore UPLOAD_KEY_ALIAS=scanfruit-upload UPLOAD_PASSWORD=... \
#     scripts/build_android_aab.sh      -> app/android/app/build/outputs/bundle/release/app-release-upload.aab
#     (+ native-debug-symbols.zip and mapping.txt next to it, for Play's crash reports)
# The keystore and its password are secrets: never commit them (keep them in the environment's secret settings).
# Same container notes as build_android_apk.sh (Maven Central mirror init script, ANDROID_HOME).
set -euo pipefail
: "${UPLOAD_KEYSTORE:?set UPLOAD_KEYSTORE}" "${UPLOAD_PASSWORD:?set UPLOAD_PASSWORD}"
: "${UPLOAD_KEY_ALIAS:=scanfruit-upload}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/app"
: "${ANDROID_HOME:=/opt/android-sdk}"; export ANDROID_HOME
CI=1 npx expo prebuild --platform android --no-install > /dev/null
git checkout package.json 2>/dev/null || true   # prebuild rewrites the run scripts
printf 'sdk.dir=%s\n' "$ANDROID_HOME" > android/local.properties
# Release signing from the environment (prebuild's template signs release builds with the debug key).
python3 - android/app/build.gradle <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
if "signingConfigs.upload" not in s:
    s = s.replace("    signingConfigs {\n", """    signingConfigs {
        upload {
            storeFile file(System.getenv("UPLOAD_KEYSTORE"))
            storePassword System.getenv("UPLOAD_PASSWORD")
            keyAlias System.getenv("UPLOAD_KEY_ALIAS")
            keyPassword System.getenv("UPLOAD_PASSWORD")
        }
""", 1)
    head, rel = s.split("        release {", 1)
    rel = rel.replace("signingConfig signingConfigs.debug", "signingConfig signingConfigs.upload", 1)
    s = head + "        release {" + rel
    open(p, "w").write(s)
PY
export UPLOAD_KEYSTORE UPLOAD_PASSWORD UPLOAD_KEY_ALIAS
cd android
./gradlew bundleRelease -PreactNativeArchitectures=arm64-v8a,armeabi-v7a --no-daemon --console=plain --max-workers=3
OUT=app/build/outputs/bundle/release
# Upload copy without BUNDLE-METADATA (debug symbols + R8 map, ~19MB): small enough to send/upload anywhere.
# Re-signed with the same upload key. The symbols go to Play separately (App bundle explorer -> Downloads):
#   native-debug-symbols.zip (Native debug symbols) and mapping.txt (ReTrace mapping file).
rm -rf "$OUT/meta" "$OUT/native-debug-symbols.zip" "$OUT/mapping.txt"
unzip -q "$OUT/app-release.aab" 'BUNDLE-METADATA/*' -d "$OUT/meta"
cp "$OUT/meta/BUNDLE-METADATA/com.android.tools.build.obfuscation/proguard.map" "$OUT/mapping.txt"
(cd "$OUT/meta/BUNDLE-METADATA/com.android.tools.build.debugsymbols" && zip -qr ../../../native-debug-symbols.zip .)
rm -rf "$OUT/meta"
cp "$OUT/app-release.aab" "$OUT/app-release-upload.aab"
zip -q -d "$OUT/app-release-upload.aab" 'BUNDLE-METADATA/com.android.tools.build.debugsymbols/*' \
  'BUNDLE-METADATA/com.android.tools.build.obfuscation/*' 'META-INF/*.SF' 'META-INF/*.RSA' 'META-INF/MANIFEST.MF'
jarsigner -sigalg SHA256withRSA -digestalg SHA-256 -keystore "$UPLOAD_KEYSTORE" -storepass:env UPLOAD_PASSWORD \
  "$OUT/app-release-upload.aab" "$UPLOAD_KEY_ALIAS" > /dev/null
jarsigner -verify "$OUT/app-release-upload.aab" | grep -q "jar verified"
ls -la "$OUT/app-release-upload.aab" "$OUT/native-debug-symbols.zip" "$OUT/mapping.txt"
