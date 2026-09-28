// First-launch sign-in (only when Google sign-in is enabled in Supabase). Optional: "continue without account".
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { getSession, onAuthChange } from '../auth';
import { getPref, setPref } from '../prefs';
import { Account } from '../ui/Account';
import { he } from '../ui/strings';

const next = () => router.replace(getPref('onboarded') ? '/' : '/welcome');

export default function SignInScreen() {
  const [session, setSession] = useState(getSession());
  useEffect(() => onAuthChange(() => setSession(getSession())), []);
  useEffect(() => { if (session) next(); }, [session]);
  return (
    <SafeAreaView style={styles.fill}>
      <View style={styles.center}>
        <Image source={require('../../assets/icon.png')} style={styles.logo} />
        <Text style={styles.title}>{he.welcomeTitle}</Text>
        <Text style={styles.body}>{he.welcomeBody}</Text>
        <View style={styles.card}><Account session={session} googleOn /></View>
        <Pressable onPress={() => { setPref('guest', true); next(); }} accessibilityRole="button" style={styles.skip}>
          <Text style={styles.skipText}>{he.continueWithout}</Text>
        </Pressable>
        <Text style={styles.small}>{he.signInPrivacy}</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, backgroundColor: '#F6F1E6' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 12 },
  logo: { width: 84, height: 84, borderRadius: 22 },
  title: { fontSize: 30, fontWeight: '900', color: '#1E2721', textAlign: 'center' },
  body: { fontSize: 16, color: '#3C463F', textAlign: 'center', lineHeight: 23, maxWidth: 320 },
  card: { alignSelf: 'stretch', marginTop: 8 },
  skip: { minHeight: 44, justifyContent: 'center', paddingHorizontal: 12 },
  skipText: { fontSize: 15, color: '#7A7F76', textDecorationLine: 'underline' },
  small: { fontSize: 12, color: '#7A7F76', textAlign: 'center', maxWidth: 320, lineHeight: 18 },
});
