# app/ — סורק פירות וירקות (Expo SDK 57, TypeScript, RTL Hebrew)

Camera → scan → result. Inference is **our** model: on-device Core ML (`modules/produce-model`,
Swift) or our self-hosted server (`../server`) — never a third-party AI API.

```
src/app/            routes (Expo Router): index = camera, result, credits
src/model/          decision.ts (1:1 port of ml/inference/decision.py), engine.ts (native|remote), math.ts, types.ts
src/ui/             Hebrew strings, chip colours, scan hand-off
modules/produce-model/  local Expo module (Swift): Core ML inference + quality gate
assets/model/       bundle.json + credits.json (from scripts/sync_model_to_app.sh)
__tests__/          decision parity (600 Python-generated cases), math
```

```bash
npm install
npm test            # jest: decision parity with Python + math
npm run typecheck   # tsc --noEmit
../scripts/sync_model_to_app.sh ../exports/<version>   # install a model
npx expo run:ios --device                              # needs macOS + Xcode (native module)
```

Config (`app.json → extra`): `inference.mode` = `native` | `remote`, `inference.serverUrl`,
`feedback.url` / `feedback.anonKey` (Supabase, optional; feedback is off when empty).
`ios.bundleIdentifier` is a placeholder (`com.example.producescanner`) — replace before any build.

Verified in the Linux build environment: typecheck, jest (604 tests), `expo export --platform ios`
(Metro bundle). **Not verified here:** Swift compilation, on-device run, camera (need macOS + iPhone).
