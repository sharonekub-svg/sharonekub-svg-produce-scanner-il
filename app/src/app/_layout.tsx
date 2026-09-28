import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { I18nManager } from 'react-native';

import { loadSession } from '../auth';
import { syncHistory } from '../history';

// Hebrew-first app: force RTL layout. (Takes effect from the next JS reload on first install;
// production builds also set it natively via app.json "extra.supportsRTL".)
if (!I18nManager.isRTL) {
  I18nManager.allowRTL(true);
  I18nManager.forceRTL(true);
}

export default function RootLayout() {
  // Signed-in users: restore the session from the keychain and sync "My scans" with the account.
  useEffect(() => { loadSession().then((s) => { if (s) syncHistory(); }); }, []);
  return (
    <>
      <StatusBar style="light" />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: '#000' } }}>
        <Stack.Screen name="index" />
        <Stack.Screen name="result" options={{ contentStyle: { backgroundColor: '#FAFAF7' } }} />
        <Stack.Screen name="history" options={{ contentStyle: { backgroundColor: '#F6F1E6' } }} />
        <Stack.Screen name="credits" options={{ headerShown: true, title: 'קרדיט לנתונים', contentStyle: { backgroundColor: '#FAFAF7' } }} />
      </Stack>
    </>
  );
}
