// Camera-first home screen (ux-principles.md #1–2): OPEN → "סרוק פרי" → RESULT.
import { CameraView, useCameraPermissions } from 'expo-camera';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useRef, useState } from 'react';
import { ActivityIndicator, Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { inferenceMode, scan } from '../model/engine';
import { peekPendingPrevious, setLastScan, takePendingPrevious } from '../ui/state';
import { he } from '../ui/strings';

export default function CameraScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const camera = useRef<CameraView>(null);
  const [frozen, setFrozen] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [secondAngle, setSecondAngle] = useState(false);

  useFocusEffect(useCallback(() => {
    setFrozen(null);
    setSecondAngle(peekPendingPrevious() !== null);
  }, []));

  if (!permission) return <View style={styles.fill} />;
  if (!permission.granted) {
    return (
      <SafeAreaView style={[styles.fill, styles.center, styles.pad]}>
        <Text style={styles.emoji} accessibilityElementsHidden>🍎🍌🥑</Text>
        <Text style={styles.title}>{he.permissionTitle}</Text>
        <Text style={styles.body}>{he.permissionBody}</Text>
        <Pressable accessibilityRole="button" style={styles.primary} onPress={requestPermission}>
          <Text style={styles.primaryText}>{he.permissionButton}</Text>
        </Pressable>
        <Text style={styles.trust}>{he.trustLine}</Text>
      </SafeAreaView>
    );
  }

  const busy = frozen !== null;
  const onScan = async () => {
    if (busy || !camera.current) return;
    if (!inferenceMode()) { setError(he.noEngine); return; }
    setError(null);
    try {
      const photo = await camera.current.takePictureAsync({ quality: 0.9, shutterSound: false });
      setFrozen(photo.uri); // freeze the frame: "בודק…" happens over what the user just shot
      const output = await scan(photo.uri, takePendingPrevious() ?? undefined);
      setLastScan({ output, photoUri: photo.uri });
      router.push('/result');
    } catch {
      setFrozen(null);
      setError(he.error);
    }
  };

  return (
    <View style={styles.fill}>
      <CameraView ref={camera} style={StyleSheet.absoluteFill} facing="back" />
      {frozen ? <Image source={{ uri: frozen }} style={StyleSheet.absoluteFill} accessibilityIgnoresInvertColors /> : null}
      <SafeAreaView style={styles.overlay} pointerEvents="box-none">
        <View style={styles.hintBox}>
          <Text style={styles.hint}>{secondAngle ? he.anotherAngleHint : he.cameraHint}</Text>
        </View>
        <View style={[styles.frame, busy && styles.frameBusy]} pointerEvents="none">
          {busy ? <View style={styles.checking}><ActivityIndicator color="#fff" /><Text style={styles.checkingText}>{he.analyzing}</Text></View> : null}
        </View>
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Pressable accessibilityRole="button" accessibilityLabel={he.scan} onPress={onScan} disabled={busy}
                   style={({ pressed }) => [styles.scanButton, (pressed || busy) && { opacity: 0.75, transform: [{ scale: 0.98 }] }]}>
          <Text style={styles.scanText}>{secondAngle ? he.anotherAngle : he.scan}</Text>
        </Pressable>
        <Text style={styles.small}>{he.cameraFooter}</Text>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, backgroundColor: '#000' },
  center: { alignItems: 'center', justifyContent: 'center' },
  pad: { padding: 24, backgroundColor: '#FAFAF7', gap: 14 },
  emoji: { fontSize: 44 },
  title: { fontSize: 24, fontWeight: '700', textAlign: 'center' },
  body: { fontSize: 17, textAlign: 'center', color: '#444', lineHeight: 24 },
  primary: { backgroundColor: '#2f7d4f', paddingHorizontal: 32, paddingVertical: 15, borderRadius: 14, minHeight: 48 },
  primaryText: { color: '#fff', fontSize: 18, fontWeight: '700' },
  trust: { color: '#6b6b66', fontSize: 13 },
  overlay: { flex: 1, alignItems: 'center', justifyContent: 'space-between', paddingVertical: 16, paddingHorizontal: 16 },
  hintBox: { backgroundColor: 'rgba(0,0,0,0.55)', paddingHorizontal: 16, paddingVertical: 8, borderRadius: 20 },
  hint: { color: '#fff', fontSize: 16 },
  frame: { width: '74%', aspectRatio: 1, borderRadius: 28, borderWidth: 2, borderColor: 'rgba(255,255,255,0.85)', alignItems: 'center', justifyContent: 'center' },
  frameBusy: { borderColor: '#6cc592' },
  checking: { backgroundColor: 'rgba(0,0,0,0.55)', borderRadius: 16, paddingHorizontal: 18, paddingVertical: 12, alignItems: 'center', gap: 6 },
  checkingText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  error: { color: '#fff', backgroundColor: 'rgba(180,30,30,0.85)', padding: 10, borderRadius: 10 },
  scanButton: { backgroundColor: '#fff', minWidth: 220, minHeight: 64, borderRadius: 32, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 28 },
  scanText: { color: '#1d1d1b', fontSize: 21, fontWeight: '800' },
  small: { color: '#ddd', fontSize: 13 },
});
