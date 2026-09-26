#!/usr/bin/env bash
# Compile ProduceCore.swift (the iOS module's platform-independent core) with the Linux Swift
# toolchain and check it against the Python reference on synthetic + real images.
#   scripts/test_swift_core.sh [image ...]      (needs `swiftc` on PATH; CI installs it)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
python3 "$ROOT/scripts/gen_swift_fixtures.py" --out "$TMP/fx" --images "$@"
swiftc -O "$ROOT/app/modules/produce-model/ios/ProduceCore.swift" "$ROOT/app/modules/produce-model/tests/main.swift" -o "$TMP/core_test"
"$TMP/core_test" "$TMP/fx"
