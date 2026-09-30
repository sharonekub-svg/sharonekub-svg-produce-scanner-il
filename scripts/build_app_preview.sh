#!/usr/bin/env bash
# Build the app's web preview (same code as the phone app) into server/web/preview.
# The server serves it at "/" so the app can be checked on a computer; scans go to this server's /v1/analyze.
#   scripts/build_app_preview.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/app"
rm -rf dist
npx expo export --platform web > /dev/null
OUT="$ROOT/server/web/preview"
rm -rf "$OUT" && cp -R dist "$OUT" && rm -rf dist
# Vercel drops any folder named node_modules from the deployment: move the dependency icons and fix the references.
if [ -d "$OUT/assets/node_modules" ]; then
  mv "$OUT/assets/node_modules" "$OUT/assets/_deps"
  grep -rl '/assets/node_modules/' "$OUT/_expo" | xargs -r sed -i 's#/assets/node_modules/#/assets/_deps/#g'
fi
python3 - "$OUT/index.html" <<'PY'
import sys
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
# Hebrew RTL (react-native-web follows the document direction) and a phone-sized frame on wide screens.
s = s.replace('<html lang="en">', '<html lang="he" dir="rtl">')
s = s.replace("</style>", """  @media (min-width: 600px) {
        body { background: #1f2a22; display: flex; align-items: center; justify-content: center; }
        #root { flex: none; width: 390px; height: min(844px, 96vh); border-radius: 36px; overflow: hidden;
                box-shadow: 0 0 0 10px #0d130f, 0 30px 80px rgba(0,0,0,.5); }
      }
    </style>""", 1)
# Vercel Web Analytics (cookieless page views; counts only once enabled in the Vercel project's Analytics tab).
s = s.replace("</head>", """<script>window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };</script>
    <script defer src="/_vercel/insights/script.js"></script>
  </head>""", 1)
open(p, "w", encoding="utf-8").write(s)
PY
echo "preview built: $(du -sh "$OUT" | cut -f1)"
