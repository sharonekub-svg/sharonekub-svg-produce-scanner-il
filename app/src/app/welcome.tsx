// First-launch intro: three short slides (same content as the web onboarding). Shown once; replayable from "how it works".
import { router } from 'expo-router';
import { useState } from 'react';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { setPref } from '../prefs';
import { he } from '../ui/strings';

const SLIDES = [
  { kicker: he.onb1Kicker, title: he.onb1Title, body: he.onb1Body, img: require('../../assets/samples/banana.jpg'), chip: he.onb1Chip, dark: true },
  { kicker: he.onb2Kicker, title: he.onb2Title, body: he.onb2Body, img: require('../../assets/samples/apple_rotten.jpg'), chip: he.onb2Chip, dark: false },
  { kicker: he.onb3Kicker, title: he.onb3Title, body: he.onb3Body, img: require('../../assets/samples/pomegranate.jpg'), chip: he.onb3Chip, dark: false },
];

export default function WelcomeScreen() {
  const [i, setI] = useState(0);
  const s = SLIDES[i];
  const done = () => { setPref('onboarded', true); router.replace('/'); };
  const fg = s.dark ? '#F6F1E6' : '#2A1C1E';
  return (
    <SafeAreaView style={[styles.fill, { backgroundColor: s.dark ? '#8A0C1B' : '#F6F1E6' }]}>
      <View style={styles.top}>
        <Text style={[styles.brand, { color: fg }]}>{he.appName}</Text>
        <Pressable onPress={done} accessibilityRole="button" hitSlop={10}><Text style={[styles.skip, { color: fg }]}>{he.skip}</Text></Pressable>
      </View>
      <View style={styles.body}>
        <Text style={[styles.kicker, { color: s.dark ? '#E8C766' : '#8A0C1B' }]}>{s.kicker}</Text>
        <Text style={[styles.title, { color: fg }]} accessibilityRole="header">{s.title}</Text>
        <Text style={[styles.text, { color: s.dark ? '#F8E1E4' : '#4A3C3E' }]}>{s.body}</Text>
        <View style={styles.phone}>
          <Image source={s.img} style={styles.img} accessibilityIgnoresInvertColors />
          <View style={styles.chip}><Text style={styles.chipText}>{s.chip}</Text></View>
        </View>
      </View>
      <View style={styles.bottom}>
        <View style={styles.dots}>{SLIDES.map((_, k) => <View key={k} style={[styles.dot, k === i && styles.dotOn]} />)}</View>
        <Pressable onPress={() => (i < SLIDES.length - 1 ? setI(i + 1) : done())} accessibilityRole="button" style={styles.next}>
          <Text style={styles.nextText}>{i < SLIDES.length - 1 ? he.next : he.letsStart}</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  top: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 20, paddingTop: 8 },
  brand: { fontSize: 16, fontWeight: '800' },
  skip: { fontSize: 15, fontWeight: '700', opacity: 0.85 },
  body: { flex: 1, paddingHorizontal: 24, paddingTop: 24, gap: 10 },
  kicker: { fontSize: 13, fontWeight: '800', letterSpacing: 1.5 },
  title: { fontSize: 34, fontWeight: '900', lineHeight: 40 },
  text: { fontSize: 16, lineHeight: 23 },
  phone: { alignSelf: 'center', width: '70%', maxWidth: 280, aspectRatio: 0.8, marginTop: 18, borderRadius: 30, borderWidth: 6, borderColor: '#2A1C1E', overflow: 'hidden', backgroundColor: '#ddd' },
  img: { width: '100%', height: '100%' },
  chip: { position: 'absolute', bottom: 14, alignSelf: 'center', backgroundColor: '#FFFDF8', borderRadius: 16, paddingHorizontal: 14, paddingVertical: 7 },
  chipText: { fontSize: 14, fontWeight: '800', color: '#2A1C1E' },
  bottom: { padding: 20, gap: 14 },
  dots: { flexDirection: 'row', justifyContent: 'center', gap: 8 },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: 'rgba(120,120,110,0.4)' },
  dotOn: { width: 22, backgroundColor: '#8A0C1B' },
  next: { backgroundColor: '#8A0C1B', minHeight: 54, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  nextText: { color: '#fff', fontSize: 18, fontWeight: '800' },
});
