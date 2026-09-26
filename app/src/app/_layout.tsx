import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { I18nManager } from 'react-native';

// Hebrew-first app: force RTL layout. (Takes effect from the next JS reload on first install;
// production builds also set it natively via app.json "extra.supportsRTL".)
if (!I18nManager.isRTL) {
  I18nManager.allowRTL(true);
  I18nManager.forceRTL(true);
}

export default function RootLayout() {
  return (
    <>
      <StatusBar style="light" />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: '#000' } }}>
        <Stack.Screen name="index" />
        <Stack.Screen name="result" options={{ contentStyle: { backgroundColor: '#FAFAF7' } }} />
        <Stack.Screen name="credits" options={{ headerShown: true, title: 'קרדיט לנתונים', contentStyle: { backgroundColor: '#FAFAF7' } }} />
      </Stack>
    </>
  );
}
