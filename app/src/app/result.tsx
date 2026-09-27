// Result (ux-principles.md #3–7): answer first, confidence in words, one useful action,
// disclaimer on assessments, details collapsed. Low confidence → optional second angle.
// Visually reviewed at 390×844 RTL for every state — see docs/ux-review.md.
import { Link, router } from 'expo-router';
import { useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { STORAGE_TIP_HE, confidenceWord } from '../model/advice';
import { getBundle } from '../model/engine';
import type { HeadResult } from '../model/types';
import { donatePhoto, donationEnabled } from '../donation';
import { sendFeedback } from '../feedback';
import { CHIP, pct } from '../ui/chips';
import { getLastScan, setPendingPrevious } from '../ui/state';
import { he } from '../ui/strings';

// Headline colour follows what we tell the user to do — never green for "don't eat".
const REC_TONE: Record<string, { fg: string; bg: string; icon: string }> = {
  eat_now: { fg: '#1f5c38', bg: '#E3F3E8', icon: '✅' },
  eat_soon: { fg: '#8a5300', bg: '#FFF1DB', icon: '⏳' },
  overripe: { fg: '#8a5300', bg: '#FFF1DB', icon: '⏳' },
  wait: { fg: '#6b5a00', bg: '#FFF8D6', icon: '🕒' },
  wait_little: { fg: '#6b5a00', bg: '#FFF8D6', icon: '🕒' },
  discard: { fg: '#9b1c1c', bg: '#FDE4E1', icon: '⚠️' },
};

// Score colour: green 8-10, amber 5-7, red 1-4 (same palette as the recommendation).
function scoreTone(score: number) {
  return score >= 8 ? REC_TONE.eat_now : score >= 5 ? REC_TONE.eat_soon : REC_TONE.discard;
}

const STATUS_HEAD: Record<string, { icon: string; title: string }> = {
  unsure: { icon: '🤔', title: he.unsureTitle },
  retake: { icon: '📷', title: he.retakeTitle },
  not_produce: { icon: '🔍', title: he.notProduceTitle },
};

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

function Disclosure({ label, open, onPress }: { label: string; open: boolean; onPress: () => void }) {
  // RTL: a collapsed disclosure points left (the reading direction), expanded points down.
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityState={{ expanded: open }}>
      <Text style={styles.link}>{open ? '▾' : '◂'} {label}</Text>
    </Pressable>
  );
}

export default function ResultScreen() {
  const last = getLastScan();
  const [open, setOpen] = useState<'what' | 'why' | null>(null);
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [answer, setAnswer] = useState<boolean | null>(null);
  const [donate, setDonate] = useState<'idle' | 'consent' | 'sending' | 'sent' | 'failed'>('idle');
  if (!last) {
    router.replace('/');
    return null;
  }
  const { result: r, top3 } = last.output;
  const again = () => router.back();
  const anotherAngle = () => { setPendingPrevious(last.output); router.back(); };
  const onFeedback = async (correct: boolean) => {
    setFeedbackSent(true);
    setAnswer(correct);
    await sendFeedback({ model_id: getBundle().model_id, status: r.status, produce: r.produce,
                         confidence: r.produce_confidence, correct });
  };
  const onDonate = async () => {
    setDonate('sending');
    const sent = await donatePhoto({ photoUri: last.photoUri, model_id: getBundle().model_id,
                                     predicted: r.produce, correct: answer });
    setDonate(sent ? 'sent' : 'failed');
  };
  const ok = r.status === 'ok';
  const assessed = ok && Boolean(r.ripeness?.available || r.freshness?.available);
  const tone = r.recommendation ? REC_TONE[r.recommendation] : undefined;
  const tip = ok && r.produce && r.recommendation !== 'discard' ? STORAGE_TIP_HE[r.produce] : undefined;
  const statusHead = STATUS_HEAD[r.status];

  return (
    <SafeAreaView style={styles.fill}>
      <ScrollView contentContainerStyle={styles.pad}>
        <Image source={{ uri: last.photoUri }} style={styles.photo} accessibilityIgnoresInvertColors />

        {ok ? (
          <View style={styles.card}>
            <View style={styles.identity}>
              <Text style={styles.name}>{r.emoji} {r.produce_he}</Text>
              <Text style={styles.muted}>{confidenceWord(r.produce_confidence)} ({pct(r.produce_confidence)})</Text>
            </View>

            {r.score != null ? (
              <View style={styles.scoreRow} accessible accessibilityLabel={`${he.qualityScore}: ${r.score} ${he.outOf10}. ${r.score_reason_he ?? ''}`}>
                <View style={[styles.scoreBadge, { backgroundColor: scoreTone(r.score).bg }]}>
                  <Text style={[styles.scoreNum, { color: scoreTone(r.score).fg }]}>{r.score}</Text>
                  <Text style={[styles.scoreOf, { color: scoreTone(r.score).fg }]}>/10</Text>
                </View>
                <View style={styles.flex1}>
                  <Text style={styles.scoreTitle}>{he.qualityScore}</Text>
                  <Text style={styles.body}>{r.score_reason_he}</Text>
                </View>
              </View>
            ) : null}

            {assessed && tone ? (
              <View style={[styles.hero, { backgroundColor: tone.bg }]}>
                <Text style={[styles.rec, { color: tone.fg }]} accessibilityRole="header">{tone.icon} {r.recommendation_he}</Text>
              </View>
            ) : (
              <Text style={styles.identifyOnly}>{r.score_reason_he ?? he.identifyOnly}</Text>
            )}

            {assessed ? (
              <View style={styles.chips}>
                <Chip title={he.ripeness} head={r.ripeness} />
                <Chip title={he.freshness} head={r.freshness} />
              </View>
            ) : null}

            {tip ? (
              <View style={styles.tip}>
                <Text style={styles.tipTitle}>💡 {he.storageTip}</Text>
                <Text style={styles.body}>{tip}</Text>
              </View>
            ) : null}
          </View>
        ) : (
          <View style={styles.card}>
            {statusHead ? <Text style={styles.stateTitle}>{statusHead.icon} {statusHead.title}</Text> : null}
            <Text style={styles.message}>{r.message_he}</Text>
          </View>
        )}

        {ok ? (
          <View style={styles.disclaimer}>
            <Text style={styles.disclaimerText}>{'\u200F'}ⓘ {r.disclaimer_he}</Text>{/* RLM: ⓘ is bidi-L; keep the paragraph RTL */}
          </View>
        ) : null}

        {ok || r.status === 'unsure' ? (
          <>
            <Disclosure label={he.whatWeSaw} open={open === 'what'} onPress={() => setOpen(open === 'what' ? null : 'what')} />
            {open === 'what' && top3.map((t) => <Text key={t.produce} style={styles.body}>{t.he} — {pct(t.prob)}</Text>)}
          </>
        ) : null}
        {assessed && r.explanation_he.length > 0 ? (
          <>
            <Disclosure label={he.why} open={open === 'why'} onPress={() => setOpen(open === 'why' ? null : 'why')} />
            {open === 'why' && r.explanation_he.map((e) => <Text key={e} style={styles.body}>{e}</Text>)}
          </>
        ) : null}

        {r.status === 'unsure' && last.output.angles < 2 ? (
          <>
            <Pressable accessibilityRole="button" style={styles.primary} onPress={anotherAngle}>
              <Text style={styles.primaryText}>{he.anotherAngle}</Text>
            </Pressable>
            <Pressable accessibilityRole="button" style={styles.secondary} onPress={again}>
              <Text style={styles.secondaryText}>{he.tryAgain}</Text>
            </Pressable>
          </>
        ) : (
          <Pressable accessibilityRole="button" style={styles.primary} onPress={again}>
            <Text style={styles.primaryText}>{ok ? he.scanAnother : he.tryAgain}</Text>
          </Pressable>
        )}

        {ok && (
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
        {feedbackSent && donationEnabled() ? (
          <View style={styles.donate}>
            {donate === 'idle' || donate === 'failed' ? (
              <>
                <Text style={styles.muted}>{donate === 'failed' ? he.donateFailed : he.donateAsk}</Text>
                <Pressable accessibilityRole="button" style={styles.secondarySmall} onPress={() => setDonate('consent')}>
                  <Text style={styles.secondaryText}>{he.donateButton}</Text>
                </Pressable>
              </>
            ) : donate === 'consent' ? (
              <>
                <Text style={styles.body}>{he.donateConsent}</Text>
                <View style={styles.row}>
                  <Pressable accessibilityRole="button" style={[styles.primary, styles.flex]} onPress={onDonate}>
                    <Text style={styles.primaryText}>{he.donateConfirm}</Text>
                  </Pressable>
                  <Pressable accessibilityRole="button" style={[styles.secondary, styles.flex]} onPress={() => setDonate('idle')}>
                    <Text style={styles.secondaryText}>{he.donateCancel}</Text>
                  </Pressable>
                </View>
              </>
            ) : (
              <Text style={styles.muted}>{donate === 'sending' ? he.donateSending : he.donateThanks}</Text>
            )}
          </View>
        ) : null}
        <Link href="/credits" style={styles.footer}>{he.trustLine} · {he.credits}</Link>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, backgroundColor: '#FAFAF7' },
  pad: { padding: 16, gap: 12 },
  photo: { width: '100%', aspectRatio: 2, borderRadius: 16 },
  card: { backgroundColor: '#fff', borderRadius: 18, padding: 18, gap: 12, borderWidth: 1, borderColor: '#E4E4DD' },
  identity: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: 6 },
  name: { fontSize: 30, fontWeight: '800' },
  muted: { color: '#6b6b66', fontSize: 14 },
  hero: { borderRadius: 14, paddingHorizontal: 14, paddingVertical: 12 },
  rec: { fontSize: 22, fontWeight: '800' },
  identifyOnly: { fontSize: 14, color: '#6b6b66' },
  scoreRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  scoreBadge: { flexDirection: 'row', direction: 'ltr', alignItems: 'baseline', borderRadius: 14, paddingHorizontal: 12, paddingVertical: 6 },
  scoreNum: { fontSize: 34, fontWeight: '800' },
  scoreOf: { fontSize: 16, fontWeight: '700' },
  scoreTitle: { fontSize: 13, color: '#6b6b66' },
  flex1: { flex: 1 },
  chips: { flexDirection: 'row', gap: 12, flexWrap: 'wrap' },
  chipCol: { gap: 4 },
  chipTitle: { fontSize: 13, color: '#6b6b66' },
  chip: { borderRadius: 14, paddingHorizontal: 12, paddingVertical: 7 },
  chipText: { fontSize: 15 },
  tip: { backgroundColor: '#F3F7F2', borderRadius: 12, padding: 12, gap: 4 },
  tipTitle: { fontSize: 14, fontWeight: '700' },
  stateTitle: { fontSize: 24, fontWeight: '800' },
  message: { fontSize: 18, lineHeight: 26 },
  disclaimer: { backgroundColor: '#FFF8E1', borderRadius: 12, padding: 10 },
  disclaimerText: { fontSize: 13 },
  link: { color: '#2f7d4f', fontSize: 16, fontWeight: '600', paddingVertical: 4 },
  body: { fontSize: 15, color: '#333', lineHeight: 22 },
  feedback: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 12 },
  thumb: { minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  thumbText: { fontSize: 22 },
  primary: { backgroundColor: '#2f7d4f', minHeight: 52, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  primaryText: { color: '#fff', fontSize: 18, fontWeight: '700' },
  secondary: { borderWidth: 1.5, borderColor: '#2f7d4f', minHeight: 52, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  secondaryText: { color: '#2f7d4f', fontSize: 18, fontWeight: '700' },
  donate: { backgroundColor: '#F3F7F2', borderRadius: 12, padding: 12, gap: 10 },
  row: { flexDirection: 'row', gap: 10 },
  flex: { flex: 1, paddingHorizontal: 8 },
  secondarySmall: { borderWidth: 1.5, borderColor: '#2f7d4f', minHeight: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  footer: { color: '#6b6b66', fontSize: 12, textAlign: 'center' },
});
