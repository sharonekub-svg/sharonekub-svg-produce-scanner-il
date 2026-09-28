// Small persistent flags (first-launch intro seen, "continue without account") in the app's documents.
import { File, Paths } from 'expo-file-system';
import { Platform } from 'react-native';

const WEB_KEY = 'app_prefs';

type Prefs = { onboarded?: boolean; guest?: boolean };
let cache: Prefs | null = null;

function file(): File | null {
  try { return new File(Paths.document, 'prefs.json'); } catch { return null; }
}

function load(): Prefs {
  if (cache) return cache;
  try {
    if (Platform.OS === 'web') { cache = JSON.parse(globalThis.localStorage?.getItem(WEB_KEY) ?? '{}') as Prefs; return cache; }
    const f = file();
    cache = f && f.exists ? (JSON.parse(f.textSync()) as Prefs) : {};
  } catch { cache = {}; }
  return cache;
}

export const getPref = <K extends keyof Prefs>(k: K): Prefs[K] => load()[k];
export function setPref<K extends keyof Prefs>(k: K, v: Prefs[K]) {
  cache = { ...load(), [k]: v };
  try {
    if (Platform.OS === 'web') globalThis.localStorage?.setItem(WEB_KEY, JSON.stringify(cache));
    else file()?.write(JSON.stringify(cache));
  } catch { /* storage unavailable: memory only */ }
}
