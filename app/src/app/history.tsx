// "My scans" (same layout as the web history page): cards with a glow in the result's colour,
// thumbnail, name, stage, date, score and delete. Tap a card to reopen its result. Device only.
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, FlatList, Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { type Session, getSession, googleEnabled, loadSession, onAuthChange } from '../auth';
import { type HistoryEntry, clearHistory, loadHistory, onHistoryChange, removeFromHistory, summarize, syncHistory } from '../history';
import type { ScanResult } from '../model/types';
import { Account } from '../ui/Account';
import { score100 } from '../ui/chips';
import { setLastScan } from '../ui/state';
import { he } from '../ui/strings';

export const TONE = { good: '#2E8B57', mid: '#C98A12', bad: '#C0392B', none: '#8A8F87' };
const toneOf = (r: ScanResult) => (r.score == null ? TONE.none : r.score >= 7 ? TONE.good : r.score >= 4 ? TONE.mid : TONE.bad);

function stageText(r: ScanResult): string {
  if (r.score == null) return he.identifyOnlyShort;
  // A low score is explained by spoilage/freshness ("מקולקל"), not by ripeness ("בשל" in red reads as a contradiction).
  const order = r.score < 4 ? [r.condition, r.visual_spoilage, r.freshness, r.ripeness] : [r.ripeness, r.condition, r.freshness, r.visual_spoilage];
  for (const h of order) if (h?.available && h.label_he) return h.label_he;
  return '';
}

// 0-100 for every entry: older scans stored only the 1-10 score.
const shown = (r: ScanResult) => score100(r);

const when = (t: number) => new Date(t).toLocaleString('he-IL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

export function Item({ e }: { e: HistoryEntry }) {
  const r = e.output.result;
  const tone = toneOf(r);
  const open = () => {
    setLastScan({ output: e.output, photoUri: e.thumb ?? '', fromHistory: true });
    router.push('/result');
  };
  return (
    <View style={[styles.item, { borderColor: tone, shadowColor: tone }]}>
      <Pressable onPress={open} accessibilityRole="button" accessibilityLabel={`${r.produce_he}, ${stageText(r)}${r.score != null ? `, ${shown(r)} ${he.outOf100}` : ''}`}
                 style={styles.itemMain}>
      {e.thumb ? <Image source={{ uri: e.thumb }} style={styles.thumb} accessibilityIgnoresInvertColors /> : <View style={[styles.thumb, styles.noThumb]}><Text style={styles.noThumbEmoji}>{r.emoji}</Text></View>}
      <View style={styles.flex1}>
        <Text style={styles.name}>{r.emoji} {r.produce_he}</Text>
        <View style={styles.stageRow}>
          <View style={[styles.dot, { backgroundColor: tone }]} />
          <Text style={[styles.stage, { color: tone }]}>{stageText(r)}</Text>
        </View>
        <Text style={styles.date}>{when(e.t)}</Text>
      </View>
      {r.score != null ? <Text style={[styles.score, { color: tone }]}>{shown(r)}</Text> : null}
      </Pressable>
      <Pressable onPress={() => removeFromHistory(e.id)} hitSlop={8} accessibilityRole="button" accessibilityLabel={he.deleteScan} style={styles.del}>
        <Text style={styles.delText}>🗑</Text>
      </Pressable>
    </View>
  );
}

export default function HistoryScreen() {
  const [items, setItems] = useState<HistoryEntry[]>(loadHistory());
  const [session, setSession] = useState<Session | null>(getSession());
  const [googleOn, setGoogleOn] = useState(false);
  useFocusEffect(useCallback(() => {
    setItems([...loadHistory()]);
    loadSession().then((s) => { setSession(s); if (s) syncHistory(); });
    googleEnabled().then(setGoogleOn);
    const offH = onHistoryChange(() => setItems([...loadHistory()]));
    const offA = onAuthChange(() => setSession(getSession()));
    return () => { offH(); offA(); };
  }, []));
  const s = summarize(items);
  const confirmClear = () => Alert.alert(he.clearAllTitle, undefined, [
    { text: he.donateCancel, style: 'cancel' },
    { text: he.clearAll, style: 'destructive', onPress: clearHistory },
  ]);

  return (
    <SafeAreaView style={styles.fill}>
      <View style={styles.bar}>
        <Pressable onPress={() => router.back()} accessibilityRole="button" accessibilityLabel={he.back} style={styles.round}><Text style={styles.roundText}>›</Text></Pressable>
        <Text style={styles.title} accessibilityRole="header">{he.myScans}</Text>
        {items.length ? (
          <Pressable onPress={confirmClear} accessibilityRole="button" accessibilityLabel={he.clearAll} style={styles.round}><Text style={styles.delText}>🗑</Text></Pressable>
        ) : <View style={styles.round} />}
      </View>
      {items.length === 0 ? (
        <View style={styles.empty}>
          <Account session={session} googleOn={googleOn} />
          <Text style={styles.emptyEmoji}>🧺</Text>
          <Text style={styles.emptyTitle}>{he.noScansYet}</Text>
          <Text style={styles.emptyBody}>{he.noScansBody}</Text>
          <Pressable onPress={() => router.back()} accessibilityRole="button" style={styles.primary}><Text style={styles.primaryText}>{he.firstScan}</Text></Pressable>
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(e) => String(e.id)}
          contentContainerStyle={styles.list}
          ListHeaderComponent={
            <>
            <Account session={session} googleOn={googleOn} />
            <View style={styles.pills}>
              <Text style={styles.pill}>{s.total} {he.scansCount}</Text>
              {s.scored ? <Text style={[styles.pill, { color: TONE.good }]}>● {s.good} {he.inGoodShape}</Text> : null}
              {s.scored ? <Text style={[styles.pill, { color: TONE.bad }]}>● {s.bad} {he.notRecommended}</Text> : null}
            </View>
            </>
          }
          renderItem={({ item }) => <Item e={item} />}
          ListFooterComponent={<Text style={styles.footer}>{session ? he.savedInAccount : he.savedOnDevice}</Text>}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, backgroundColor: '#F6F1E6' },
  bar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 8 },
  round: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#FFFDF8', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#E6DFD0' },
  roundText: { fontSize: 26, color: '#2A1C1E', lineHeight: 28 },
  title: { fontSize: 18, fontWeight: '800', color: '#2A1C1E' },
  list: { padding: 16, gap: 12 },
  pills: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 4 },
  pill: { backgroundColor: '#FFFDF8', borderRadius: 14, paddingHorizontal: 12, paddingVertical: 6, fontSize: 13, fontWeight: '700', color: '#4A3C3E', overflow: 'hidden' },
  item: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#FFFDF8', borderRadius: 20, padding: 10, borderWidth: 1.5,
    shadowOpacity: 0.25, shadowRadius: 10, shadowOffset: { width: 0, height: 0 }, elevation: 3 },
  itemMain: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12 },
  thumb: { width: 64, height: 64, borderRadius: 14, backgroundColor: '#ddd' },
  noThumb: { alignItems: 'center', justifyContent: 'center', backgroundColor: '#EFE8DA' },
  noThumbEmoji: { fontSize: 30 },
  flex1: { flex: 1 },
  name: { fontSize: 17, fontWeight: '800', color: '#2A1C1E' },
  stageRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 2 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  stage: { fontSize: 13, fontWeight: '700' },
  date: { fontSize: 12, color: '#7A7F76', marginTop: 2 },
  score: { fontSize: 22, fontWeight: '900', width: 44, textAlign: 'center' },
  del: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center' },
  delText: { fontSize: 18 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 10 },
  emptyEmoji: { fontSize: 54 },
  emptyTitle: { fontSize: 24, fontWeight: '800', color: '#2A1C1E' },
  emptyBody: { fontSize: 15, color: '#4A3C3E', textAlign: 'center', lineHeight: 22 },
  primary: { backgroundColor: '#8A0C1B', paddingHorizontal: 32, minHeight: 52, borderRadius: 14, alignItems: 'center', justifyContent: 'center', marginTop: 12 },
  primaryText: { color: '#fff', fontSize: 18, fontWeight: '700' },
  footer: { fontSize: 12, color: '#7A7F76', textAlign: 'center', marginTop: 8 },
});
