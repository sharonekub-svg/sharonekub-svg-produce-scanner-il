// "My scans" (same layout as the web history page): cards with a glow in the result's colour,
// thumbnail, name, stage, date, score and delete. Tap a card to reopen its result. Device only.
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, FlatList, Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { type Session, deleteAccount, getSession, googleEnabled, loadSession, onAuthChange, signIn, signOut } from '../auth';
import { type HistoryEntry, clearHistory, loadHistory, onHistoryChange, removeFromHistory, summarize, syncHistory } from '../history';
import type { ScanResult } from '../model/types';
import { setLastScan } from '../ui/state';
import { he } from '../ui/strings';

const TONE = { good: '#2E8B57', mid: '#C98A12', bad: '#C0392B', none: '#8A8F87' };
const toneOf = (r: ScanResult) => (r.score == null ? TONE.none : r.score >= 7 ? TONE.good : r.score >= 4 ? TONE.mid : TONE.bad);

function stageText(r: ScanResult): string {
  if (r.score == null) return he.identifyOnlyShort;
  for (const h of [r.ripeness, r.freshness, r.visual_spoilage]) if (h?.available && h.label_he) return h.label_he;
  return '';
}

const when = (t: number) => new Date(t).toLocaleString('he-IL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

function Item({ e }: { e: HistoryEntry }) {
  const r = e.output.result;
  const tone = toneOf(r);
  const open = () => {
    setLastScan({ output: e.output, photoUri: e.thumb ?? '', fromHistory: true });
    router.push('/result');
  };
  return (
    <View style={[styles.item, { borderColor: tone, shadowColor: tone }]}>
      <Pressable onPress={open} accessibilityRole="button" accessibilityLabel={`${r.produce_he}, ${stageText(r)}${r.score != null ? `, ${r.score} ${he.outOf10}` : ''}`}
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
      {r.score != null ? <Text style={[styles.score, { color: tone }]}>{r.score}</Text> : null}
      </Pressable>
      <Pressable onPress={() => removeFromHistory(e.id)} hitSlop={8} accessibilityRole="button" accessibilityLabel={he.deleteScan} style={styles.del}>
        <Text style={styles.delText}>🗑</Text>
      </Pressable>
    </View>
  );
}

// Account card: sign in (only when Google sign-in is enabled), or who is signed in + sign out / delete.
function Account({ session, googleOn }: { session: Session | null; googleOn: boolean }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  if (!session && !googleOn) return null;
  const onSignIn = async () => {
    setBusy(true); setMsg(null);
    const ok = await signIn();
    setBusy(false);
    if (ok) syncHistory(); else setMsg(he.signInFailed);
  };
  const onDelete = () => Alert.alert(he.deleteAccountTitle, he.deleteAccountBody, [
    { text: he.donateCancel, style: 'cancel' },
    { text: he.deleteAccount, style: 'destructive', onPress: async () => { if (!(await deleteAccount())) setMsg(he.deleteFailed); } },
  ]);
  return session ? (
    <View style={styles.account}>
      <View style={styles.accountRow}>
        {session.avatar ? <Image source={{ uri: session.avatar }} style={styles.avatar} /> : null}
        <View style={styles.flex1}>
          <Text style={styles.accountTitle}>{he.signedInAs}</Text>
          <Text style={styles.date}>{session.name}</Text>
        </View>
        <Pressable onPress={signOut} accessibilityRole="button" style={styles.linkBtn}><Text style={styles.link}>{he.signOut}</Text></Pressable>
      </View>
      <Pressable onPress={onDelete} accessibilityRole="button" style={styles.linkBtn}><Text style={[styles.link, styles.danger]}>{he.deleteAccount}</Text></Pressable>
      {msg ? <Text style={styles.date}>{msg}</Text> : null}
    </View>
  ) : (
    <View style={styles.account}>
      <Text style={styles.emptyBody}>{he.signInCta}</Text>
      <Pressable onPress={onSignIn} disabled={busy} accessibilityRole="button" style={[styles.google, busy && { opacity: 0.6 }]}>
        <Text style={styles.googleG}>G</Text><Text style={styles.googleText}>{he.signInGoogle}</Text>
      </Pressable>
      {msg ? <Text style={styles.date}>{msg}</Text> : null}
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
  roundText: { fontSize: 26, color: '#1E2721', lineHeight: 28 },
  title: { fontSize: 18, fontWeight: '800', color: '#1E2721' },
  list: { padding: 16, gap: 12 },
  pills: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 4 },
  pill: { backgroundColor: '#FFFDF8', borderRadius: 14, paddingHorizontal: 12, paddingVertical: 6, fontSize: 13, fontWeight: '700', color: '#3C463F', overflow: 'hidden' },
  item: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#FFFDF8', borderRadius: 20, padding: 10, borderWidth: 1.5,
    shadowOpacity: 0.25, shadowRadius: 10, shadowOffset: { width: 0, height: 0 }, elevation: 3 },
  itemMain: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12 },
  thumb: { width: 64, height: 64, borderRadius: 14, backgroundColor: '#ddd' },
  noThumb: { alignItems: 'center', justifyContent: 'center', backgroundColor: '#EFE8DA' },
  noThumbEmoji: { fontSize: 30 },
  flex1: { flex: 1 },
  name: { fontSize: 17, fontWeight: '800', color: '#1E2721' },
  stageRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 2 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  stage: { fontSize: 13, fontWeight: '700' },
  date: { fontSize: 12, color: '#7A7F76', marginTop: 2 },
  score: { fontSize: 24, fontWeight: '900', width: 34, textAlign: 'center' },
  del: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center' },
  delText: { fontSize: 18 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 10 },
  emptyEmoji: { fontSize: 54 },
  emptyTitle: { fontSize: 24, fontWeight: '800', color: '#1E2721' },
  emptyBody: { fontSize: 15, color: '#3C463F', textAlign: 'center', lineHeight: 22 },
  primary: { backgroundColor: '#2f7d4f', paddingHorizontal: 32, minHeight: 52, borderRadius: 14, alignItems: 'center', justifyContent: 'center', marginTop: 12 },
  primaryText: { color: '#fff', fontSize: 18, fontWeight: '700' },
  account: { alignSelf: 'stretch', backgroundColor: '#FFFDF8', borderRadius: 18, padding: 14, gap: 10, marginBottom: 12, borderWidth: 1, borderColor: '#E6DFD0' },
  accountRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  avatar: { width: 36, height: 36, borderRadius: 18 },
  accountTitle: { fontSize: 15, fontWeight: '800', color: '#1E2721' },
  linkBtn: { minHeight: 36, justifyContent: 'center' },
  link: { color: '#2f7d4f', fontSize: 15, fontWeight: '700' },
  danger: { color: '#C0392B' },
  google: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: '#fff', borderWidth: 1, borderColor: '#dadce0', borderRadius: 14, minHeight: 52 },
  googleG: { fontSize: 20, fontWeight: '900', color: '#4285F4' },
  googleText: { fontSize: 17, fontWeight: '700', color: '#1f1f1f' },
  footer: { fontSize: 12, color: '#7A7F76', textAlign: 'center', marginTop: 8 },
});
