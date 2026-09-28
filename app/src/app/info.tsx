// "How it works" (same content as the web info sheet): steps, which fruits get a score, what a photo
// can't know, privacy, account, replay intro, data credits.
import { Link, router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { type Session, getSession, googleEnabled, loadSession, onAuthChange } from '../auth';
import { getBundle } from '../model/engine';
import { setPref } from '../prefs';
import { Account } from '../ui/Account';
import { he } from '../ui/strings';

export default function InfoScreen() {
  const [session, setSession] = useState<Session | null>(getSession());
  const [googleOn, setGoogleOn] = useState(false);
  useFocusEffect(useCallback(() => {
    loadSession().then(setSession);
    googleEnabled().then(setGoogleOn);
    return onAuthChange(() => setSession(getSession()));
  }, []));
  const b = getBundle() as any;
  const rated = Object.keys(b.supported_heads ?? {}).map((p) => b.produce_meta?.[p]).filter(Boolean);
  const n = Object.values(b.produce_meta ?? {}).filter((m: any) => !m.is_negative_class && m.he !== 'אחר').length;
  const replay = () => { setPref('onboarded', false); router.replace('/welcome'); };

  return (
    <SafeAreaView style={styles.fill}>
      <View style={styles.bar}>
        <Pressable onPress={() => router.back()} accessibilityRole="button" accessibilityLabel={he.back} style={styles.round}><Text style={styles.roundText}>›</Text></Pressable>
        <Text style={styles.title} accessibilityRole="header">{he.howItWorks}</Text>
        <View style={styles.round} />
      </View>
      <ScrollView contentContainerStyle={styles.pad}>
        <View style={styles.card}>
          <Text style={styles.body}><Text style={styles.b}>1. {he.step1a}</Text> {he.step1b}</Text>
          <Text style={styles.body}><Text style={styles.b}>2. {he.step2a}</Text> {he.step2b}</Text>
          <Text style={styles.body}><Text style={styles.b}>3. {he.step3a}</Text> {he.step3b}</Text>
        </View>
        <View style={styles.card}>
          <Text style={styles.b}>{he.ratedFor}</Text>
          <View style={styles.chips}>{rated.map((m: any) => <Text key={m.he} style={styles.chip}>{m.emoji} {m.he}</Text>)}</View>
          <Text style={styles.small}>{he.ratedNote(n)}</Text>
        </View>
        <View style={styles.card}>
          <Text style={styles.b}>{he.photoLimitsTitle}</Text>
          {he.photoLimits.map((t) => <Text key={t} style={styles.body}>• {t}</Text>)}
        </View>
        <Account session={session} googleOn={googleOn} />
        <View style={styles.card}>
          <Text style={styles.b}>{he.privacyTitle}</Text>
          <Text style={styles.body}>{session ? he.privacySignedIn : he.privacyDevice}</Text>
        </View>
        <Text style={styles.small}>{he.modelVersion}: {b.model_id}</Text>
        <Link href="/credits" style={styles.link}>{he.credits}</Link>
        <Pressable onPress={replay} accessibilityRole="button" style={styles.secondary}><Text style={styles.secondaryText}>{he.replayIntro}</Text></Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, backgroundColor: '#F6F1E6' },
  bar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 8 },
  round: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#FFFDF8', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#E6DFD0' },
  roundText: { fontSize: 26, color: '#1E2721', lineHeight: 28 },
  title: { fontSize: 18, fontWeight: '800', color: '#1E2721' },
  pad: { padding: 16, gap: 12 },
  card: { backgroundColor: '#FFFDF8', borderRadius: 18, padding: 14, gap: 8, borderWidth: 1, borderColor: '#E6DFD0' },
  b: { fontWeight: '800', fontSize: 15, color: '#1E2721' },
  body: { fontSize: 15, color: '#3C463F', lineHeight: 22 },
  small: { fontSize: 12, color: '#7A7F76', lineHeight: 18 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { backgroundColor: '#E3F3E8', color: '#1f5c38', borderRadius: 12, paddingHorizontal: 10, paddingVertical: 4, fontSize: 14, fontWeight: '700', overflow: 'hidden' },
  link: { color: '#2f7d4f', fontSize: 15, fontWeight: '700', textAlign: 'center', paddingVertical: 6 },
  secondary: { borderWidth: 1.5, borderColor: '#2f7d4f', minHeight: 50, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  secondaryText: { color: '#2f7d4f', fontSize: 16, fontWeight: '700' },
});
