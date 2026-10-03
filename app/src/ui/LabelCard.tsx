// Labelling card on the result screen, only for labeler accounts (../labels.ts): confirm or change the type,
// then one tap — good / small problem / rotten — stores this photo with that label. Shown above everything else
// so a market round of photos is: shoot → tap → back to the camera.
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { type LabelCondition, amILabeler, labelledToday, sendLabel } from '../labels';
import { getBundle } from '../model/engine';
import { he } from './strings';

const CONDITIONS: { key: LabelCondition; bg: string; fg: string }[] = [
  { key: 'good', bg: '#E3F3E8', fg: '#1f5c38' },
  { key: 'early', bg: '#FFF1DB', fg: '#8a5300' },
  { key: 'rotten', bg: '#FDE4E1', fg: '#9b1c1c' },
];

export function LabelCard({ photoUri, guess, onDone }: { photoUri: string; guess: string | null; onDone: () => void }) {
  const [show, setShow] = useState(false);
  const [produce, setProduce] = useState<string | null>(guess && guess !== 'other' ? guess : null);
  const [choosing, setChoosing] = useState(false);
  const [state, setState] = useState<'idle' | 'sending' | 'sent' | 'failed'>('idle');
  useEffect(() => { amILabeler().then(setShow); }, []);
  if (!show) return null;

  const b = getBundle();
  const meta = (p: string) => b.produce_meta[p];
  const types = b.outputs.produce.filter((p) => p !== 'other' && meta(p))
    .sort((x, y) => meta(x).he.localeCompare(meta(y).he, 'he'));
  const send = async (c: LabelCondition) => {
    if (!produce) { setChoosing(true); return; }
    setState('sending');
    setState((await sendLabel(photoUri, b.model_id, guess, produce, c)) ? 'sent' : 'failed');
  };

  if (state === 'sent') {
    return (
      <View style={styles.card}>
        <Text style={styles.title}>✓ {he.labelSaved(labelledToday())}</Text>
        <Pressable accessibilityRole="button" style={styles.next} onPress={onDone}>
          <Text style={styles.nextText}>📸 {he.labelNext}</Text>
        </Pressable>
      </View>
    );
  }
  return (
    <View style={styles.card} accessibilityLabel={he.labelTitle}>
      <Text style={styles.title}>🏷️ {he.labelTitle}</Text>
      <Pressable accessibilityRole="button" onPress={() => setChoosing(!choosing)} style={styles.type}>
        <Text style={styles.typeText}>{produce ? `${meta(produce).emoji} ${meta(produce).he}` : he.labelPickType}</Text>
        <Text style={styles.change}>{choosing ? '▾' : he.labelChange}</Text>
      </Pressable>
      {choosing ? (
        <ScrollView style={styles.grid} contentContainerStyle={styles.gridIn} nestedScrollEnabled>
          {types.map((p) => (
            <Pressable key={p} accessibilityRole="button" onPress={() => { setProduce(p); setChoosing(false); }}
                       style={[styles.chip, p === produce && styles.chipOn]}>
              <Text style={styles.chipText}>{meta(p).emoji} {meta(p).he}</Text>
            </Pressable>
          ))}
        </ScrollView>
      ) : null}
      <View style={styles.row}>
        {CONDITIONS.map((c) => (
          <Pressable key={c.key} accessibilityRole="button" disabled={state === 'sending'} onPress={() => send(c.key)}
                     style={[styles.btn, { backgroundColor: c.bg }]}>
            <Text style={[styles.btnText, { color: c.fg }]}>{he.labelCond[c.key]}</Text>
          </Pressable>
        ))}
      </View>
      {state === 'sending' ? <Text style={styles.muted}>{he.donateSending}</Text> : null}
      {state === 'failed' ? <Text style={styles.muted}>{he.labelFailed}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: '#F1ECFF', borderRadius: 16, padding: 14, gap: 10, borderWidth: 1, borderColor: '#D9CCFF' },
  title: { fontSize: 16, fontWeight: '800', color: '#3b2a7a', textAlign: 'right' },
  type: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#fff',
          borderRadius: 12, paddingVertical: 10, paddingHorizontal: 12 },
  typeText: { fontSize: 16, fontWeight: '700', color: '#222' },
  change: { fontSize: 14, color: '#5b45b0', fontWeight: '600' },
  grid: { maxHeight: 220 },
  gridIn: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { backgroundColor: '#fff', borderRadius: 16, paddingVertical: 6, paddingHorizontal: 10, borderWidth: 1, borderColor: '#E4DDF7' },
  chipOn: { borderColor: '#5b45b0', borderWidth: 2 },
  chipText: { fontSize: 14, color: '#222' },
  row: { flexDirection: 'row', gap: 8 },
  btn: { flex: 1, borderRadius: 12, paddingVertical: 14, alignItems: 'center' },
  btnText: { fontSize: 16, fontWeight: '800' },
  next: { backgroundColor: '#5b45b0', borderRadius: 12, paddingVertical: 12, alignItems: 'center' },
  nextText: { color: '#fff', fontSize: 16, fontWeight: '800' },
  muted: { fontSize: 13, color: '#666', textAlign: 'right' },
});
