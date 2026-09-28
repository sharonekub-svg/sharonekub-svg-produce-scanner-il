#!/usr/bin/env bash
# Build an installable Android APK (arm64, signed with the debug key — for sideloading/testing, not Play Store).
# Needs ANDROID_HOME with platforms;android-36, build-tools;36.0.0, ndk;27.1.12297006 (see app/android after prebuild).
#   scripts/build_android_apk.sh            -> app/android/app/build/outputs/apk/release/app-release.apk
# In the cloud container, Maven Central answers 429 through the proxy: copy scripts/gradle-central-mirror.init.gradle to
# ~/.gradle/init.d/ (Google mirror of Central; disables the release lint that crashes there — a check, not part of the APK).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/app"
: "${ANDROID_HOME:=/opt/android-sdk}"; export ANDROID_HOME
CI=1 npx expo prebuild --platform android --no-install > /dev/null
git checkout package.json 2>/dev/null || true   # prebuild rewrites the run scripts
printf 'sdk.dir=%s\n' "$ANDROID_HOME" > android/local.properties
cd android
./gradlew assembleRelease -PreactNativeArchitectures=arm64-v8a --no-daemon --console=plain --max-workers=3
ls -la app/build/outputs/apk/release/app-release.apk
