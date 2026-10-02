// Profile (corner button on the camera screen): name + photo from Google (or "guest"), scan stats,
// the last few scans (tap to reopen) and the account card (sign in / out / delete).
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { type Session, getSession, googleEnabled, loadSession, onAuthChange } from '../auth';
import { type HistoryEntry, loadHistory, onHistoryChange, summarize, syncHistory } from '../history';
import { Account } from '../ui/Account';
import { he } from '../ui/strings';
import { Item, TONE } from './history';

const RECENT = 3;

// Most scanned type (Hebrew name + emoji), ignoring unidentified scans.
function favourite(items: HistoryEntry[]): string | null {
  const n = new Map<string, number>();
  for (const e of items) {
    const r = e.output.result;
    if (r.produce_he) n.set(`${r.emoji} ${r.produce_he}`, (n.get(`${r.emoji} ${r.produce_he}`) ?? 0) + 1);
  }
  let best: string | null = null;
  n.forEach((c, k) => { if (best == null || c > n.get(best)!) best = k; });
  return best;
}

export default function ProfileScreen() {
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
  const fav = favourite(items);
  const name = session?.name || he.guest;

  return (
    <SafeAreaView style={styles.fill}>
      <View style={styles.bar}>
        <Pressable onPress={() => router.back()} accessibilityRole="button" accessibilityLabel={he.back} style={styles.round}><Text style={styles.roundText}>›</Text></Pressable>
        <Text style={styles.title} accessibilityRole="header">{he.profile}</Text>
        <View style={styles.round} />
      </View>
      <ScrollView contentContainerStyle={styles.pad}>
        <View style={styles.head}>
          {session?.avatar
            ? <Image source={{ uri: session.avatar }} style={styles.avatar} accessibilityIgnoresInvertColors />
            : <View style={[styles.avatar, styles.initial]}><Text style={styles.initialText}>{session ? name.trim().charAt(0) : '👤'}</Text></View>}
          <Text style={styles.name}>{name}</Text>
          <Text style={styles.sub}>{session ? he.signedInGoogle : he.guestSub}</Text>
        </View>

        <View style={styles.stats}>
          <View style={styles.stat}><Text style={styles.statNum}>{s.total}</Text><Text style={styles.statLabel}>{he.scansCount}</Text></View>
          <View style={styles.stat}><Text style={[styles.statNum, { color: TONE.good }]}>{s.good}</Text><Text style={styles.statLabel}>{he.inGoodShape}</Text></View>
          <View style={styles.stat}><Text style={[styles.statNum, { color: TONE.bad }]}>{s.bad}</Text><Text style={styles.statLabel}>{he.notRecommended}</Text></View>
        </View>
        {fav ? <Text style={styles.fav}>{he.favType}: <Text style={styles.favName}>{fav}</Text></Text> : null}

        <Text style={styles.section}>{he.recentScans}</Text>
        {items.length === 0 ? (
          <Text style={styles.sub}>{he.noScansYet}</Text>
        ) : (
          <View style={styles.list}>
            {items.slice(0, RECENT).map((e) => <Item key={e.id} e={e} />)}
            {items.length > RECENT ? (
              <Pressable onPress={() => router.push('/history')} accessibilityRole="button" style={styles.more}>
                <Text style={styles.moreText}>{he.allScans} ({items.length}) ‹</Text>
              </Pressable>
            ) : null}
          </View>
        )}

        <View style={styles.accountWrap}><Account session={session} googleOn={googleOn} /></View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, backgroundColor: '#F6F1E6' },
  bar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 8 },
  round: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#FFFDF8', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#E6DFD0' },
  roundText: { fontSize: 26, color: '#2A1C1E', lineHeight: 28 },
  title: { fontSize: 18, fontWeight: '800', color: '#2A1C1E' },
  pad: { padding: 16, gap: 12 },
  head: { alignItems: 'center', gap: 4, marginBottom: 4 },
  avatar: { width: 88, height: 88, borderRadius: 44, borderWidth: 3, borderColor: '#8A0C1B' },
  initial: { backgroundColor: '#8A0C1B', alignItems: 'center', justifyContent: 'center' },
  initialText: { color: '#fff', fontSize: 38, fontWeight: '900' },
  name: { fontSize: 24, fontWeight: '900', color: '#2A1C1E', marginTop: 6 },
  sub: { fontSize: 14, color: '#7A7F76', textAlign: 'center' },
  stats: { flexDirection: 'row', gap: 10 },
  stat: { flex: 1, backgroundColor: '#FFFDF8', borderRadius: 18, paddingVertical: 12, alignItems: 'center', borderWidth: 1, borderColor: '#E6DFD0' },
  statNum: { fontSize: 26, fontWeight: '900', color: '#2A1C1E' },
  statLabel: { fontSize: 12, fontWeight: '700', color: '#4A3C3E', textAlign: 'center' },
  fav: { fontSize: 15, color: '#4A3C3E', textAlign: 'center' },
  favName: { fontWeight: '800', color: '#8A0C1B' },
  section: { fontSize: 18, fontWeight: '800', color: '#2A1C1E', marginTop: 8, textAlign: 'right' },
  list: { gap: 12 },
  more: { minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  moreText: { color: '#8A0C1B', fontSize: 16, fontWeight: '800' },
  accountWrap: { marginTop: 8 },
});
