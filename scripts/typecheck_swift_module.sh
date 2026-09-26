#!/usr/bin/env bash
# Type-check the iOS Expo module (ProduceModelModule.swift + ProduceCore.swift) on Linux against
# signature stubs of ExpoModulesCore / CoreML / UIKit (app/modules/produce-model/tests/typecheck-stubs).
# Catches our own type/logic errors; it cannot prove the stubs match Apple's SDK exactly —
# the first `npx expo run:ios` on a Mac remains the final check.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STUBS="$ROOT/app/modules/produce-model/tests/typecheck-stubs"
TMP="$(mktemp -d)"
for m in ExpoModulesCore CoreML UIKit; do
  swiftc -parse-as-library -emit-module -module-name "$m" -emit-module-path "$TMP/$m.swiftmodule" "$STUBS/$m.swift"
done
swiftc -typecheck -I "$TMP" -module-name ProduceModel \
  "$ROOT/app/modules/produce-model/ios/ProduceCore.swift" "$ROOT/app/modules/produce-model/ios/ProduceModelModule.swift"
echo "ProduceModelModule.swift: type-check OK"
