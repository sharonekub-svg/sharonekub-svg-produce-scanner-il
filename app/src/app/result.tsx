// Result (ux-principles.md #3–7): answer first, confidence in words, one useful action,
// disclaimer always visible, details collapsed. Low confidence → optional second angle.
import { Link, router } from 'expo-router';
import { useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { STORAGE_TIP_HE, confidenceWord } from '../model/advice';
import { getBundle } from '../model/engine';
import type { HeadResult } from '../model/types';
import { sendFeedback } from '../feedback';
import { CHIP, pct } from '../ui/chips';
import { getLastScan, setPendingPrevious } from '../ui/state';
import { he } from '../ui/strings';

function Chip({ title, head }: { title: string; head: HeadResult | null }) {
  const available = head?.available && head.label;
  const c = CHIP[available ? head!.label! : 'unknown'];
  return (
    <View style={styles.chipCol} accessible accessibilityLabel={`${title}: ${available ? head!.label_he : he.notAvailable}`}>
      <Text style={styles.chipTitle}>{title}</Text>
      <View style={[styles.chip, { backgroundColor: c.bg }]}>
        <Text style={styles.chipText}>{available ? `${c.dot} ${head!.label_he}` : he.notAvailable}</Text>
      </View>
    </View>
  );
}

export default function ResultScreen() {
  const last = getLastScan();
  const [open, setOpen] = useState<'what' | 'why' | null>(null);
  const [feedbackSent, setFeedbackSent] = useState(false);
  if (!last) {
    router.replace('/');
    return null;
  }
  const { result: r, top3 } = last.output;
  const again = () => router.back();
  const anotherAngle = () => { setPendingPrevious(last.output); router.back(); };
  const onFeedback = async (correct: boolean) => {
    setFeedbackSent(true);
    await sendFeedback({ model_id: getBundle().model_id, status: r.status, produce: r.produce,
                         confidence: r.produce_confidence, correct });
  };
  const tip = r.produce ? STORAGE_TIP_HE[r.produce] : undefined;

  return (
    <SafeAreaView style={styles.fill}>
      <ScrollView contentContainerStyle={styles.pad}>
        <Image source={{ uri: last.photoUri }} style={styles.photo} accessibilityIgnoresInvertColors />

        {r.status === 'ok' ? (
          <View style={styles.card}>
            <View style={styles.identity}>
              <Text style={styles.name}>{r.emoji} {r.produce_he}</Text>
              <Text style={styles.muted}>{confidenceWord(r.produce_confidence)} ({pct(r.produce_confidence)})</Text>
            </View>
            <Text style={styles.rec} accessibilityRole="header">{r.recommendation_he}</Text>
            <View style={styles.chips}>
              <Chip title={he.ripeness} head={r.ripeness} />
              <Chip title={he.freshness} head={r.freshness} />
            </View>
            {tip ? (
              <View style={styles.tip}>
                <Text style={styles.tipTitle}>💡 {he.storageTip}</Text>
                <Text style={styles.body}>{tip}</Text>
              </View>
            ) : null}
          </View>
        ) : (
          <View style={styles.card}>
            {r.status === 'unsure' ? <Text style={styles.name}>🤔 {he.unsureTitle}</Text> : null}
            <Text style={styles.message}>{r.message_he}</Text>
            {r.status === 'unsure' && last.output.angles < 2 ? (
              <Pressable accessibilityRole="button" style={styles.primary} onPress={anotherAngle}>
                <Text style={styles.primaryText}>{he.anotherAngle}</Text>
              </Pressable>
            ) : null}
          </View>
        )}

        <View style={styles.disclaimer}>
          <Text style={styles.disclaimerText}>ⓘ {r.disclaimer_he}</Text>
        </View>

        {r.status === 'ok' || r.status === 'unsure' ? (
          <>
            <Pressable onPress={() => setOpen(open === 'what' ? null : 'what')} accessibilityRole="button">
              <Text style={styles.link}>{open === 'what' ? '▾' : '▸'} {he.whatWeSaw}</Text>
            </Pressable>
            {open === 'what' && top3.map((t) => <Text key={t.produce} style={styles.body}>{t.he} — {pct(t.prob)}</Text>)}
          </>
        ) : null}
        {r.explanation_he.length > 0 && (
          <Pressable onPress={() => setOpen(open === 'why' ? null : 'why')} accessibilityRole="button">
            <Text style={styles.link}>{open === 'why' ? '▾' : '▸'} {he.why}</Text>
          </Pressable>
        )}
        {open === 'why' && r.explanation_he.map((e) => <Text key={e} style={styles.body}>{e}</Text>)}

        <Pressable accessibilityRole="button" style={r.status === 'ok' ? styles.primary : styles.secondary} onPress={again}>
          <Text style={r.status === 'ok' ? styles.primaryText : styles.secondaryText}>{r.status === 'ok' ? he.scanAnother : he.tryAgain}</Text>
        </Pressable>

        {r.status === 'ok' && (
          <View style={styles.feedback}>
            {feedbackSent ? <Text style={styles.muted}>{he.thanks}</Text> : (
              <>
                <Text style={styles.muted}>{he.wasItRight}</Text>
                <Pressable style={styles.thumb} accessibilityLabel={he.yes} onPress={() => onFeedback(true)}><Text style={styles.thumbText}>👍</Text></Pressable>
                <Pressable style={styles.thumb} accessibilityLabel={he.no} onPress={() => onFeedback(false)}><Text style={styles.thumbText}>👎</Text></Pressable>
              </>
            )}
          </View>
        )}
        <Link href="/credits" style={styles.footer}>{he.trustLine} · {he.credits}</Link>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, backgroundColor: '#FAFAF7' },
  pad: { padding: 16, gap: 12 },
  photo: { width: '100%', aspectRatio: 16 / 9, borderRadius: 16 },
  card: { backgroundColor: '#fff', borderRadius: 18, padding: 18, gap: 12, borderWidth: 1, borderColor: '#E4E4DD' },
  identity: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: 6 },
  name: { fontSize: 28, fontWeight: '800', textAlign: 'left' },
  muted: { color: '#6b6b66', fontSize: 14, textAlign: 'left' },
  rec: { fontSize: 24, fontWeight: '700', color: '#1f5c38', textAlign: 'left' },
  chips: { flexDirection: 'row', gap: 12, flexWrap: 'wrap' },
  chipCol: { gap: 4 },
  chipTitle: { fontSize: 13, color: '#6b6b66', textAlign: 'left' },
  chip: { borderRadius: 14, paddingHorizontal: 12, paddingVertical: 7 },
  chipText: { fontSize: 15 },
  tip: { backgroundColor: '#F3F7F2', borderRadius: 12, padding: 12, gap: 4 },
  tipTitle: { fontSize: 14, fontWeight: '700', textAlign: 'left' },
  message: { fontSize: 18, lineHeight: 26, textAlign: 'left' },
  disclaimer: { backgroundColor: '#FFF8E1', borderRadius: 12, padding: 10 },
  disclaimerText: { fontSize: 13, textAlign: 'left' },
  link: { color: '#2f7d4f', fontSize: 16, fontWeight: '600', textAlign: 'left', paddingVertical: 4 },
  body: { fontSize: 15, color: '#333', textAlign: 'left', lineHeight: 22 },
  feedback: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 12 },
  thumb: { minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  thumbText: { fontSize: 22 },
  primary: { backgroundColor: '#2f7d4f', minHeight: 52, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  primaryText: { color: '#fff', fontSize: 18, fontWeight: '700' },
  secondary: { borderWidth: 1.5, borderColor: '#2f7d4f', minHeight: 52, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  secondaryText: { color: '#2f7d4f', fontSize: 18, fontWeight: '700' },
  footer: { color: '#6b6b66', fontSize: 12, textAlign: 'center' },
});
