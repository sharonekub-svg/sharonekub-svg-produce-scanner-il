// First-launch landing: one screen that says what the app does, then straight to the camera.
// Google sign-in is optional (link below the button); the three-slide intro stays available from "how it works".
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Image, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { googleEnabled } from '../auth';
import { setPref } from '../prefs';
import { he } from '../ui/strings';

const ROWS = [
  { icon: '📸', text: he.landRow1 },
  { icon: '⭐', text: he.landRow2 },
  { icon: '💡', text: he.landRow3 },
];

export default function LandingScreen() {
  const [googleOn, setGoogleOn] = useState(false);
  useEffect(() => { googleEnabled().then(setGoogleOn); }, []);
  const start = () => { setPref('onboarded', true); router.replace('/'); };
  const signIn = () => { setPref('onboarded', true); router.replace('/signin'); };
  return (
    <SafeAreaView style={styles.fill}>
      <ScrollView contentContainerStyle={styles.pad}>
        <Image source={require('../../assets/icon.png')} style={styles.logo} accessibilityIgnoresInvertColors />
        <Text style={styles.brand}>{he.appName}</Text>
        <Text style={styles.title} accessibilityRole="header">{he.landTitle}</Text>
        <Text style={styles.sub}>{he.landSub}</Text>
        <View style={styles.rows}>
          {ROWS.map((r) => (
            <View key={r.icon} style={styles.row}>
              <Text style={styles.rowIcon}>{r.icon}</Text>
              <Text style={styles.rowText}>{r.text}</Text>
            </View>
          ))}
        </View>
        <Text style={styles.badges}>{Platform.OS === 'web' ? he.landBadgesWeb : he.landBadgesApp}</Text>
        <Pressable onPress={start} accessibilityRole="button" style={styles.cta}>
          <Text style={styles.ctaText}>{he.landCta}</Text>
        </Pressable>
        {googleOn ? (
          <Pressable onPress={signIn} accessibilityRole="button" style={styles.link}>
            <Text style={styles.linkText}>{he.landSignIn}</Text>
          </Pressable>
        ) : null}
        <Text style={styles.small}>{he.visualOnlyBanner}</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, backgroundColor: '#8A0C1B' },
  pad: { flexGrow: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 14 },
  logo: { width: 96, height: 96, borderRadius: 24, borderWidth: 2, borderColor: 'rgba(255,255,255,.35)' },
  brand: { color: '#FFD34D', fontSize: 16, fontWeight: '800', letterSpacing: 1 },
  title: { color: '#fff', fontSize: 32, fontWeight: '900', textAlign: 'center', lineHeight: 38, maxWidth: 340 },
  sub: { color: '#F8E1E4', fontSize: 17, textAlign: 'center', lineHeight: 25, maxWidth: 340 },
  rows: { alignSelf: 'stretch', maxWidth: 360, width: '100%', marginTop: 6, gap: 10 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: 'rgba(255,255,255,.1)', borderRadius: 16, padding: 14 },
  rowIcon: { fontSize: 26 },
  rowText: { flex: 1, color: '#fff', fontSize: 17, fontWeight: '700', textAlign: 'right' },
  badges: { color: '#FFD34D', fontSize: 15, fontWeight: '800', marginTop: 4 },
  cta: { alignSelf: 'stretch', maxWidth: 360, width: '100%', backgroundColor: '#FFD34D', minHeight: 58, borderRadius: 18,
         alignItems: 'center', justifyContent: 'center', marginTop: 6 },
  ctaText: { color: '#5a0610', fontSize: 20, fontWeight: '900' },
  link: { minHeight: 44, justifyContent: 'center', paddingHorizontal: 12 },
  linkText: { color: '#fff', fontSize: 15, textDecorationLine: 'underline' },
  small: { color: 'rgba(255,255,255,.65)', fontSize: 12 },
});
