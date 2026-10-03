// Result (ux-principles.md #3–7): answer first, confidence in words, one useful action,
// disclaimer on assessments, details collapsed. Low confidence → optional second angle.
// Visually reviewed at 390×844 RTL for every state — see docs/ux-review.md.
import { Link, router } from 'expo-router';
import { useState } from 'react';
import { Image, Pressable, ScrollView, Share, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { STORAGE_TIP_HE, TOUCH_HE, angleHintHe, confidenceWord, needsAnotherAngle, stageUseHe, surfaceHe, verdictHe } from '../model/advice';
import { decide } from '../model/decision';
import { type ScanOutput, getBundle } from '../model/engine';
import { addToHistory } from '../history';
import type { HeadResult } from '../model/types';
import { donatePhoto, donationEnabled } from '../donation';
import { type Rating, sendRating } from '../feedback';
import { CHIP, pct, score100, step5 } from '../ui/chips';
import { getLastScan, setLastScan, setPendingPrevious } from '../ui/state';
import { he } from '../ui/strings';
import { SurveyCard } from '../ui/Survey';

// Headline colour follows what we tell the user to do — never green for "don't eat".
const REC_TONE: Record<string, { fg: string; bg: string; icon: string }> = {
  eat_now: { fg: '#1f5c38', bg: '#E3F3E8', icon: '✅' },
  eat_soon: { fg: '#8a5300', bg: '#FFF1DB', icon: '⏳' },
  overripe: { fg: '#8a5300', bg: '#FFF1DB', icon: '⏳' },
  wait: { fg: '#6b5a00', bg: '#FFF8D6', icon: '🕒' },
  wait_little: { fg: '#6b5a00', bg: '#FFF8D6', icon: '🕒' },
  discard: { fg: '#9b1c1c', bg: '#FDE4E1', icon: '⚠️' },
  check_defects: { fg: '#9b1c1c', bg: '#FDE4E1', icon: '🔎' },
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

// One "analysis details" row: round icon, small title, value (same layout as the web result page).
function Row({ icon, title, value, bg, note }: { icon: string; title: string; value: string; bg: string; note?: string }) {
  return (
    <View style={styles.row2} accessible accessibilityLabel={`${title}: ${value}`}>
      <View style={[styles.rowIcon, { backgroundColor: bg }]}><Text style={styles.rowIconText}>{icon}</Text></View>
      <View style={styles.flex1}>
        <Text style={styles.rowTitle}>{title}</Text>
        <Text style={note ? styles.body : styles.rowValue}>{value}</Text>
        {note ? <Text style={styles.rowTitle}>{note}</Text> : null}
      </View>
    </View>
  );
}

function headRow(icon: string, title: string, head: HeadResult | null, value?: string | null) {
  if (!head?.available) return null;
  const c = CHIP[head.label ?? 'unknown'] ?? CHIP.unknown;
  return <Row key={title} icon={icon} title={title} value={value ?? head.label_he ?? he.notAvailable} bg={c.bg} />;
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
  const [rating, setRating] = useState<Rating | null>(null);
  const [donate, setDonate] = useState<'idle' | 'consent' | 'sending' | 'sent' | 'failed'>('idle');
  const [picked, setPicked] = useState<ScanOutput | null>(null);
  if (!last) {
    router.replace('/');
    return null;
  }
  const fromHistory = Boolean(last.fromHistory);
  const output = picked ?? last.output;
  const { result: r, top3 } = output;
  // "Unsure": let the user say which fruit it is, then assess it as that fruit (identification by the user).
  const candidates = r.status === 'unsure' ? top3.filter((t) => t.produce !== 'other').slice(0, 3) : [];
  const onPick = (name: string) => {
    const res = decide(getBundle(), last.output.probs, null, null, undefined, name);
    const next = { ...last.output, result: res };
    setPicked(next);
    setLastScan({ ...last, output: next });
    if (!fromHistory) addToHistory(last.photoUri, next);
  };
  const canDonate = !fromHistory && !last.sample && donationEnabled();
  const onShare = () => {
    const sc = r.score != null ? ` – ${score100(r)}/100 (${verdictHe(r.score)})` : '';
    Share.share({ message: he.shareText(r.produce_he ?? '', sc) }).catch(() => {});
  };
  const again = () => (fromHistory ? router.dismissTo('/') : router.back());
  const anotherAngle = () => { setPendingPrevious(last.output); router.back(); };
  const onRate = (v: Rating) => {
    setFeedbackSent(true);
    setRating(v);
    if (v === 'poor' && canDonate) setDonate('consent'); // the photos we most need to learn from
    sendRating({ model_id: getBundle().model_id, produce: r.produce, score: r.score ?? null, verdict: v });
  };
  const onDonate = async () => {
    setDonate('sending');
    const sent = await donatePhoto({ photoUri: last.photoUri, model_id: getBundle().model_id, predicted: r.produce,
                                     correct: null, score: r.score ?? null, quality_verdict: rating });
    setDonate(sent ? 'sent' : 'failed');
  };
  const ok = r.status === 'ok';
  const assessed = ok && Boolean(r.ripeness?.available || r.freshness?.available || r.visual_spoilage?.available || r.condition?.available);
  const tone = r.recommendation ? REC_TONE[r.recommendation] : undefined;
  const tip = ok && r.produce && r.recommendation !== 'discard' && r.recommendation !== 'check_defects' ? STORAGE_TIP_HE[r.produce] : undefined;
  const stageUse = ok && r.ripeness?.available && r.recommendation !== 'discard' ? stageUseHe(r.produce, r.ripeness.label) : null;
  const statusHead = STATUS_HEAD[r.status];

  return (
    <SafeAreaView style={styles.fill}>
      <ScrollView contentContainerStyle={styles.pad}>
        <View style={styles.photoWrap}>
          {last.photoUri ? <Image source={{ uri: last.photoUri }} style={styles.photo} accessibilityIgnoresInvertColors />
            : <View style={[styles.photo, styles.photoEmpty]}><Text style={styles.photoEmoji}>{r.emoji}</Text></View>}
          {ok && r.produce_confidence != null ? (
            <View style={[styles.confRing, r.produce_confidence < 0.85 && styles.confRingLow]} accessible accessibilityLabel={`${he.confidence}: ${pct(r.produce_confidence)}`}>
              <Text style={styles.confSpark}>✦</Text>
              <Text style={styles.confText}>{pct(r.produce_confidence)}</Text>
            </View>
          ) : null}
        </View>

        {ok ? (
          <View style={styles.card}>
            <View style={styles.identity}>
              <View style={styles.flex1}>
                <View style={styles.namePill}><Text style={styles.name}>{r.produce_he}</Text></View>
                <Text style={[styles.muted, styles.confWord]}>{r.chosen_by_user ? he.chosenByYou : `${confidenceWord(r.produce_confidence)} בזיהוי`}</Text>
              </View>
              <View style={[styles.fruitBubble, { backgroundColor: r.score != null ? scoreTone(r.score).bg : '#EFE8DA' }]}>
                <Text style={styles.fruitEmoji}>{r.emoji}</Text>
              </View>
            </View>

            {r.score != null ? (
              <View style={styles.scoreBlock} accessible
                    accessibilityLabel={`${he.qualityScore}: ${score100(r)} ${he.outOf100}. ${r.score_reason_he ?? ''}`}>
                <View style={styles.scoreRow}>
                  <View style={styles.scoreBadge}>
                    <Text style={[styles.scoreNum, { color: scoreTone(r.score).fg }]}>{score100(r)}</Text>
                    <Text style={styles.scoreOf}>/100</Text>
                  </View>
                  <View style={[styles.stagePill, { backgroundColor: scoreTone(r.score).bg }]}>
                    <Text style={[styles.stageText, { color: scoreTone(r.score).fg }]}>{verdictHe(r.score)}</Text>
                  </View>
                  {r.general_score ? (
                    <View style={styles.generalPill}><Text style={styles.generalText}>{he.generalScore}</Text></View>
                  ) : null}
                </View>
                <View style={styles.meter}><View style={[styles.meterFill, { width: `${r.overall ?? r.score * 10}%`, backgroundColor: scoreTone(r.score).fg }]} /></View>
                {r.condition_score != null && r.condition_confidence != null ? (
                  <Text style={styles.breakdown}>{he.breakdown(r.ripeness_score != null ? step5(r.ripeness_score) : null, step5(r.condition_score), step5(r.condition_confidence * 100))}</Text>
                ) : null}
                <Text style={styles.body}>{r.score_reason_he}</Text>
                {r.issues_he && r.issues_he.length ? (
                  <View style={styles.issues}>
                    <Text style={styles.issuesTitle}>{he.issuesFound}</Text>
                    {r.issues_he.map((x) => <Text key={x} style={styles.issue}>• {x}</Text>)}
                  </View>
                ) : null}
              </View>
            ) : null}

            {assessed && tone ? (
              <View style={[styles.hero, { backgroundColor: tone.bg }]}>
                <Text style={[styles.rec, { color: tone.fg }]} accessibilityRole="header">{tone.icon} {r.recommendation_he}</Text>
              </View>
            ) : r.score != null ? null : (  // the score block above already shows score_reason_he
              <Text style={styles.identifyOnly}>{r.score_reason_he ?? he.identifyOnly}</Text>
            )}

            {assessed ? (
              <View style={styles.details}>
                <Text style={styles.sectionTitle}>{he.details}</Text>
                {headRow('🌿', he.ripeness, r.ripeness)}
                {r.condition?.available ? headRow('🔍', he.condition, r.condition, r.low_confidence ? he.issuesUnclear : null) : (
                  <>
                    {headRow('💧', he.freshness, r.freshness)}
                    {headRow('🔍', he.skin, r.visual_spoilage, surfaceHe(r.freshness, r.visual_spoilage))}
                  </>
                )}
                {r.produce && TOUCH_HE[r.produce] ? (
                  <Row icon="✋" title={he.touch} value={TOUCH_HE[r.produce]} bg="#EFE8DA" note={he.touchNote} />
                ) : null}
              </View>
            ) : null}

            {stageUse ? (
              <View style={styles.tip}>
                <Text style={styles.tipTitle}>🍽️ {he.stageUse}</Text>
                <Text style={styles.body}>{stageUse}</Text>
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
            <Text style={styles.message}>{candidates.length ? he.pickBody : r.message_he}</Text>
            {candidates.map((c) => {
              const meta = getBundle().produce_meta[c.produce];
              return (
                <Pressable key={c.produce} onPress={() => onPick(c.produce)} accessibilityRole="button" style={styles.pick}>
                  <Text style={styles.pickEmoji}>{meta?.emoji}</Text>
                  <Text style={styles.pickName}>{c.he}</Text>
                  <Text style={styles.muted}>{pct(c.prob)}</Text>
                </Pressable>
              );
            })}
          </View>
        )}

        {!fromHistory && !r.chosen_by_user && needsAnotherAngle(r, last.output.angles) ? (
          <View style={styles.donate}>
            <Text style={styles.tipTitle}>📷 {he.betterAngleTitle}</Text>
            <Text style={styles.body}>{he.betterAngleBody(angleHintHe(r.produce))}</Text>
            <Pressable accessibilityRole="button" style={styles.secondarySmall} onPress={anotherAngle}>
              <Text style={styles.secondaryText}>{he.anotherAngle}</Text>
            </Pressable>
          </View>
        ) : null}
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
          <View style={styles.row}>
            {ok ? (
              <Pressable accessibilityRole="button" style={[styles.secondary, styles.flex]} onPress={onShare}>
                <Text style={styles.secondaryText}>⤴ {he.share}</Text>
              </Pressable>
            ) : null}
            <Pressable accessibilityRole="button" style={[styles.primary, styles.flex]} onPress={again}>
              <Text style={styles.primaryText}>{fromHistory ? he.newScan : ok ? he.scanAnother : he.tryAgain}</Text>
            </Pressable>
          </View>
        )}

        {ok && !fromHistory && (
          <View style={styles.feedback}>
            {feedbackSent ? <Text style={styles.muted}>{he.thanks}</Text> : (
              <>
                <Text style={styles.muted}>{he.rateQ}</Text>
                {(['great', 'okay', 'poor'] as const).map((v) => (
                  <Pressable key={v} accessibilityRole="button" style={styles.rate} onPress={() => onRate(v)}>
                    <Text style={styles.rateText}>{he.rateA[v]}</Text>
                  </Pressable>
                ))}
              </>
            )}
          </View>
        )}
        {ok && !fromHistory && !last.sample ? <SurveyCard /> : null}
        {ok && canDonate ? (
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
                {rating === 'poor' ? <Text style={styles.muted}>{he.rateDonateAsk}</Text> : null}
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
  pick: { flexDirection: 'row', alignItems: 'center', gap: 12, borderWidth: 1.5, borderColor: '#8A0C1B', borderRadius: 14, minHeight: 52, paddingHorizontal: 14 },
  pickEmoji: { fontSize: 24 },
  pickName: { flex: 1, fontSize: 18, fontWeight: '800', color: '#8A0C1B' },
  photoWrap: { width: '68%', maxWidth: 280, alignSelf: 'center', marginBottom: 12 },
  photo: { width: '100%', aspectRatio: 1, borderRadius: 24 },
  photoEmpty: { backgroundColor: '#EFE8DA', alignItems: 'center', justifyContent: 'center' },
  photoEmoji: { fontSize: 96 },
  confRing: { position: 'absolute', bottom: -18, end: -14, width: 64, height: 64, borderRadius: 32, backgroundColor: '#fff',
    borderWidth: 4, borderColor: 'rgba(79,190,120,0.45)', alignItems: 'center', justifyContent: 'center',
    shadowColor: '#D94A5A', shadowOpacity: 0.55, shadowRadius: 12, shadowOffset: { width: 0, height: 0 }, elevation: 6 },
  confRingLow: { borderColor: 'rgba(217,154,30,0.45)', shadowColor: '#D99A1E' },
  confSpark: { color: '#8A0C1B', fontSize: 14, lineHeight: 16 },
  confText: { color: '#8A0C1B', fontSize: 14, fontWeight: '800' },
  namePill: { alignSelf: 'flex-start', backgroundColor: '#FBE9EB', borderRadius: 14, paddingHorizontal: 14, paddingVertical: 4,
    shadowColor: '#D94A5A', shadowOpacity: 0.3, shadowRadius: 9, shadowOffset: { width: 0, height: 0 } },
  confWord: { marginTop: 6 },
  fruitBubble: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center' },
  fruitEmoji: { fontSize: 26 },
  scoreBlock: { gap: 10 },
  breakdown: { fontSize: 14, fontWeight: '700', color: '#4A3C3E', textAlign: 'right' },
  issues: { gap: 2 },
  issuesTitle: { fontSize: 13, fontWeight: '800', color: '#6b6b66', textAlign: 'right' },
  issue: { fontSize: 15, color: '#2A1C1E', textAlign: 'right' },
  stagePill: { borderRadius: 12, paddingHorizontal: 12, paddingVertical: 4 },
  generalPill: { borderRadius: 12, paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1, borderColor: '#C9C2B2' },
  generalText: { fontSize: 12, fontWeight: '700', color: '#6b6b66' },
  stageText: { fontSize: 14, fontWeight: '800' },
  meter: { height: 8, borderRadius: 4, backgroundColor: '#EFE8DA', overflow: 'hidden' },
  meterFill: { height: '100%', borderRadius: 4 },
  details: { gap: 8 },
  sectionTitle: { fontSize: 15, fontWeight: '800' },
  row2: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#FFFDF8', borderRadius: 16, padding: 10,
    borderWidth: 1, borderColor: '#EEE8DC' },
  rowIcon: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  rowIconText: { fontSize: 18 },
  rowTitle: { fontSize: 12, color: '#6b6b66' },
  rowValue: { fontSize: 15, fontWeight: '700' },
  card: { backgroundColor: '#fff', borderRadius: 18, padding: 18, gap: 12, borderWidth: 1, borderColor: '#E4E4DD' },
  identity: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 6 },
  name: { fontSize: 22, fontWeight: '800', color: '#8A0C1B' },
  muted: { color: '#6b6b66', fontSize: 14 },
  hero: { borderRadius: 14, paddingHorizontal: 14, paddingVertical: 12 },
  rec: { fontSize: 22, fontWeight: '800' },
  identifyOnly: { fontSize: 14, color: '#6b6b66' },
  scoreRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  scoreBadge: { flexDirection: 'row', direction: 'ltr', alignItems: 'baseline' },
  scoreNum: { fontSize: 52, fontWeight: '900', lineHeight: 56 },
  scoreOf: { fontSize: 16, fontWeight: '500', color: '#6b6b66' },
  flex1: { flex: 1 },
  tip: { backgroundColor: '#FBF1EE', borderRadius: 12, padding: 12, gap: 4 },
  tipTitle: { fontSize: 14, fontWeight: '700' },
  stateTitle: { fontSize: 24, fontWeight: '800' },
  message: { fontSize: 18, lineHeight: 26 },
  disclaimer: { backgroundColor: '#FFF8E1', borderRadius: 12, padding: 10 },
  disclaimerText: { fontSize: 13 },
  link: { color: '#8A0C1B', fontSize: 16, fontWeight: '600', paddingVertical: 4 },
  body: { fontSize: 15, color: '#333', lineHeight: 22 },
  feedback: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'center', gap: 10 },
  rate: { minHeight: 40, paddingHorizontal: 14, borderRadius: 999, borderWidth: 1.5, borderColor: '#8A0C1B', justifyContent: 'center' },
  rateText: { color: '#8A0C1B', fontSize: 14, fontWeight: '700' },
  primary: { backgroundColor: '#8A0C1B', minHeight: 52, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  primaryText: { color: '#fff', fontSize: 18, fontWeight: '700' },
  secondary: { borderWidth: 1.5, borderColor: '#8A0C1B', minHeight: 52, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  secondaryText: { color: '#8A0C1B', fontSize: 18, fontWeight: '700' },
  donate: { backgroundColor: '#FBF1EE', borderRadius: 12, padding: 12, gap: 10 },
  row: { flexDirection: 'row', gap: 10 },
  flex: { flex: 1, paddingHorizontal: 8 },
  secondarySmall: { borderWidth: 1.5, borderColor: '#8A0C1B', minHeight: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  footer: { color: '#6b6b66', fontSize: 12, textAlign: 'center' },
});
