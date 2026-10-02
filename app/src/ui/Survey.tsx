// One-time user survey card on the result screen (logic and privacy: ../survey.ts). Two short questions,
// one at a time; "not now" snoozes for a week, answering or closing ends it for good.
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { loadHistory } from '../history';
import { ANSWERS, QUESTIONS, finishSurvey, sendSurveyAnswer, shouldAskSurvey, snoozeSurvey } from '../survey';
import { he } from './strings';

export function SurveyCard() {
  const [step, setStep] = useState<number | 'done' | 'hidden'>(() => {
    const times = loadHistory().map((h) => h.t);
    return shouldAskSurvey(times) ? 0 : 'hidden';
  });
  if (step === 'hidden') return null;
  if (step === 'done') return <View style={styles.card}><Text style={styles.muted}>{he.surveyThanks}</Text></View>;

  const q = QUESTIONS[step];
  const onAnswer = (a: (typeof ANSWERS)[number]) => {
    sendSurveyAnswer(q, a, loadHistory().length); // background; never blocks the UI
    if (step + 1 < QUESTIONS.length) setStep(step + 1);
    else { finishSurvey(); setStep('done'); }
  };
  return (
    <View style={styles.card} accessibilityLabel={he.surveyTitle}>
      <Text style={styles.kicker}>{he.surveyTitle} · {step + 1}/{QUESTIONS.length}</Text>
      <Text style={styles.question}>{he.surveyQ[q]}</Text>
      <View style={styles.answers}>
        {ANSWERS.map((a) => (
          <Pressable key={a} accessibilityRole="button" style={styles.answer} onPress={() => onAnswer(a)}>
            <Text style={styles.answerText}>{he.surveyA[a]}</Text>
          </Pressable>
        ))}
      </View>
      <View style={styles.footer}>
        <Pressable accessibilityRole="button" onPress={() => { snoozeSurvey(); setStep('hidden'); }}>
          <Text style={styles.link}>{he.surveyLater}</Text>
        </Pressable>
        <Pressable accessibilityRole="button" onPress={() => { finishSurvey(); setStep('hidden'); }}>
          <Text style={styles.link}>{he.surveyNever}</Text>
        </Pressable>
      </View>
      <Text style={styles.note}>{he.surveyPrivacy}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: '#FBF1EE', borderRadius: 12, padding: 12, gap: 10 },
  kicker: { fontSize: 12, color: '#6b6b66', textAlign: 'right' },
  question: { fontSize: 16, fontWeight: '600', color: '#1d1d1b', textAlign: 'right', lineHeight: 22 },
  answers: { flexDirection: 'row-reverse', flexWrap: 'wrap', gap: 8 },
  answer: { borderWidth: 1.5, borderColor: '#8A0C1B', borderRadius: 999, minHeight: 40, paddingHorizontal: 14, justifyContent: 'center' },
  answerText: { color: '#8A0C1B', fontSize: 14, fontWeight: '600' },
  footer: { flexDirection: 'row-reverse', gap: 18 },
  link: { color: '#6b6b66', fontSize: 13, textDecorationLine: 'underline' },
  muted: { color: '#6b6b66', fontSize: 14, textAlign: 'right' },
  note: { color: '#8a8a85', fontSize: 11, textAlign: 'right' },
});
