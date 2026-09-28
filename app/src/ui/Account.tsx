// Account card (history, info and sign-in screens): Google sign-in when enabled, or the signed-in
// user with sign out / delete account. Shared by the app screens.
import { useState } from 'react';
import { Alert, Image, Pressable, StyleSheet, Text, View } from 'react-native';

import { type Session, deleteAccount, signIn, signOut } from '../auth';
import { syncHistory } from '../history';
import { he } from './strings';

// Account card: sign in (only when Google sign-in is enabled), or who is signed in + sign out / delete.
export function Account({ session, googleOn }: { session: Session | null; googleOn: boolean }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  if (!session && !googleOn) return null;
  const onSignIn = async () => {
    setBusy(true); setMsg(null);
    const ok = await signIn();
    setBusy(false);
    if (ok) syncHistory(); else setMsg(he.signInFailed);
  };
  const onDelete = () => Alert.alert(he.deleteAccountTitle, he.deleteAccountBody, [
    { text: he.donateCancel, style: 'cancel' },
    { text: he.deleteAccount, style: 'destructive', onPress: async () => { if (!(await deleteAccount())) setMsg(he.deleteFailed); } },
  ]);
  return session ? (
    <View style={styles.account}>
      <View style={styles.accountRow}>
        {session.avatar ? <Image source={{ uri: session.avatar }} style={styles.avatar} /> : null}
        <View style={styles.flex1}>
          <Text style={styles.accountTitle}>{he.signedInAs}</Text>
          <Text style={styles.small}>{session.name}</Text>
        </View>
        <Pressable onPress={signOut} accessibilityRole="button" style={styles.linkBtn}><Text style={styles.link}>{he.signOut}</Text></Pressable>
      </View>
      <Pressable onPress={onDelete} accessibilityRole="button" style={styles.linkBtn}><Text style={[styles.link, styles.danger]}>{he.deleteAccount}</Text></Pressable>
      {msg ? <Text style={styles.small}>{msg}</Text> : null}
    </View>
  ) : (
    <View style={styles.account}>
      <Text style={styles.body}>{he.signInCta}</Text>
      <Pressable onPress={onSignIn} disabled={busy} accessibilityRole="button" style={[styles.google, busy && { opacity: 0.6 }]}>
        <Text style={styles.googleG}>G</Text><Text style={styles.googleText}>{he.signInGoogle}</Text>
      </Pressable>
      {msg ? <Text style={styles.small}>{msg}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  account: { alignSelf: 'stretch', backgroundColor: '#FFFDF8', borderRadius: 18, padding: 14, gap: 10, marginBottom: 12, borderWidth: 1, borderColor: '#E6DFD0' },
  accountRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  avatar: { width: 36, height: 36, borderRadius: 18 },
  accountTitle: { fontSize: 15, fontWeight: '800', color: '#1E2721' },
  linkBtn: { minHeight: 36, justifyContent: 'center' },
  link: { color: '#2f7d4f', fontSize: 15, fontWeight: '700' },
  danger: { color: '#C0392B' },
  google: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: '#fff', borderWidth: 1, borderColor: '#dadce0', borderRadius: 14, minHeight: 52 },
  googleG: { fontSize: 20, fontWeight: '900', color: '#4285F4' },
  googleText: { fontSize: 17, fontWeight: '700', color: '#1f1f1f' },
  flex1: { flex: 1 },
  small: { fontSize: 12, color: '#7A7F76', marginTop: 2 },
  body: { fontSize: 15, color: '#3C463F', textAlign: 'center', lineHeight: 22 },
});
