// Camera-first home screen (ux-principles.md #1–2): OPEN → "סרוק פרי" → RESULT.
// Same controls as the web version: sample photos + "how it works" on top; gallery · shutter · my scans below.
// First launch: optional Google sign-in (when enabled), then the three-slide intro.
import { Asset } from 'expo-asset';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Image, Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { getSession, loadSession, onAuthChange } from '../auth';
import { addToHistory } from '../history';
import { inferenceMode, scan } from '../model/engine';
import { getPref } from '../prefs';
import { peekPendingPrevious, setLastScan, takePendingPrevious } from '../ui/state';
import { he } from '../ui/strings';

const SAMPLES = [
  { key: 'banana', src: require('../../assets/samples/banana.jpg') },
  { key: 'apple_rotten', src: require('../../assets/samples/apple_rotten.jpg') },
  { key: 'pomegranate', src: require('../../assets/samples/pomegranate.jpg') },
];

let firstLaunchChecked = false;

export default function CameraScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const camera = useRef<CameraView>(null);
  const [frozen, setFrozen] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [secondAngle, setSecondAngle] = useState(false);
  const [samplesOpen, setSamplesOpen] = useState(false);
  const [avatar, setAvatar] = useState<string | null>(getSession()?.avatar ?? null);
  useEffect(() => {
    loadSession().then((s) => setAvatar(s?.avatar ?? null));
    return onAuthChange(() => setAvatar(getSession()?.avatar ?? null));
  }, []);

  useFocusEffect(useCallback(() => {
    setFrozen(null);
    setSecondAngle(peekPendingPrevious() !== null);
  }, []));

  // First launch: sign-in screen (only if Google sign-in is on and the user hasn't chosen "without account"), then intro.
  useEffect(() => {
    if (firstLaunchChecked) return;
    firstLaunchChecked = true;
    (async () => {
      // First visit: the one-screen landing (sign-in is an optional link there, the intro slides stay in "how it works").
      if (!getPref('onboarded')) router.replace('/landing');
    })();
  }, []);

  const busy = frozen !== null;
  const run = async (uri: string, sample = false) => {
    if (!inferenceMode()) { setError(he.noEngine); return; }
    setError(null);
    setFrozen(uri); // freeze the frame: "בודק…" happens over what the user just shot
    try {
      const output = await scan(uri, takePendingPrevious() ?? undefined);
      setLastScan({ output, photoUri: uri, sample });
      addToHistory(uri, output); // background; never blocks the result
      router.push('/result');
    } catch {
      setFrozen(null);
      setError(he.error);
    }
  };
  const onScan = async () => {
    if (busy || !camera.current) return;
    try {
      const photo = await camera.current.takePictureAsync({ quality: 0.9, shutterSound: false });
      await run(photo.uri);
    } catch { setError(he.error); }
  };
  const onGallery = async () => {
    if (busy) return;
    const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.9 });
    if (!res.canceled && res.assets[0]) await run(res.assets[0].uri);
  };
  const onSample = async (src: number) => {
    setSamplesOpen(false);
    const a = Asset.fromModule(src);
    await a.downloadAsync();
    await run(a.localUri ?? a.uri, true);
  };

  const top = (
    <View style={styles.topBar}>
      <View style={styles.brand}>
        <Image source={require('../../assets/icon.png')} style={styles.brandIcon} />
        <Text style={styles.brandText}>{he.appName}</Text>
      </View>
      <View style={styles.topBtns}>
        <Pressable onPress={() => setSamplesOpen(true)} disabled={busy} accessibilityRole="button" style={styles.glassWide}>
          <Text style={styles.glassText}>✦ {he.sample}</Text>
        </Pressable>
        <Pressable onPress={() => router.push('/info')} disabled={busy} accessibilityRole="button" accessibilityLabel={he.howItWorks} style={styles.glass}>
          <Text style={styles.glassText}>i</Text>
        </Pressable>
        <Pressable onPress={() => router.push('/profile')} disabled={busy} accessibilityRole="button" accessibilityLabel={he.profile} style={styles.glass}>
          {avatar ? <Image source={{ uri: avatar }} style={styles.glassAvatar} /> : <Text style={styles.glassText}>👤</Text>}
        </Pressable>
      </View>
    </View>
  );

  const samples = (
    <Modal visible={samplesOpen} transparent animationType="slide" onRequestClose={() => setSamplesOpen(false)}>
      <Pressable style={styles.scrim} onPress={() => setSamplesOpen(false)} />
      <View style={styles.sheet}>
        <Text style={styles.sheetTitle}>{he.samplesTitle}</Text>
        <Text style={styles.sheetBody}>{he.samplesBody}</Text>
        <View style={styles.samples}>
          {SAMPLES.map((s) => (
            <Pressable key={s.key} onPress={() => onSample(s.src)} accessibilityRole="button" accessibilityLabel={he.sampleNames[s.key]} style={styles.sample}>
              <Image source={s.src} style={styles.sampleImg} />
              <Text style={styles.sampleText}>{he.sampleNames[s.key]}</Text>
            </Pressable>
          ))}
        </View>
        <Pressable onPress={() => setSamplesOpen(false)} accessibilityRole="button" style={styles.secondary}>
          <Text style={styles.secondaryText}>{he.backToCamera}</Text>
        </Pressable>
      </View>
    </Modal>
  );

  if (!permission) return <View style={styles.fill} />;
  if (!permission.granted) {
    return (
      <SafeAreaView style={[styles.fill, styles.permission]}>
        {top}
        <View style={[styles.center, styles.pad]}>
          <Text style={styles.emoji} accessibilityElementsHidden>🍎🍌🥑</Text>
          <Text style={styles.title}>{he.permissionTitle}</Text>
          <Text style={styles.body}>{he.permissionBody}</Text>
          <Pressable accessibilityRole="button" style={styles.primary} onPress={requestPermission}>
            <Text style={styles.primaryText}>{he.permissionButton}</Text>
          </Pressable>
          <Pressable accessibilityRole="button" onPress={onGallery}><Text style={styles.link}>{he.gallery}</Text></Pressable>
          <Text style={styles.trust}>{he.trustLine}</Text>
        </View>
        {samples}
      </SafeAreaView>
    );
  }

  return (
    <View style={styles.fill}>
      <CameraView ref={camera} style={StyleSheet.absoluteFill} facing="back" />
      {frozen ? <Image source={{ uri: frozen }} style={StyleSheet.absoluteFill} accessibilityIgnoresInvertColors /> : null}
      <SafeAreaView style={styles.overlay} pointerEvents="box-none">
        {top}
        <View style={styles.hintBox}>
          <Text style={styles.hint}>{secondAngle ? he.anotherAngleHint : he.cameraHint}</Text>
        </View>
        <View style={[styles.frame, busy && styles.frameBusy]} pointerEvents="none">
          {busy ? <View style={styles.checking}><ActivityIndicator color="#fff" /><Text style={styles.checkingText}>{he.analyzing}</Text></View> : null}
        </View>
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <View style={styles.controls}>
          <View style={styles.side}>
            <Pressable onPress={onGallery} disabled={busy} accessibilityRole="button" accessibilityLabel={he.gallery} style={styles.glassBig}><Text style={styles.sideIcon}>🖼</Text></Pressable>
            <Text style={styles.sideLabel}>{he.gallery}</Text>
          </View>
          <View style={styles.side}>
            <Pressable accessibilityRole="button" accessibilityLabel={secondAngle ? he.anotherAngle : he.scan} onPress={onScan} disabled={busy}
                       style={({ pressed }) => [styles.shutter, (pressed || busy) && { opacity: 0.75, transform: [{ scale: 0.96 }] }]}>
              <View style={styles.shutterInner} />
            </Pressable>
            <Text style={styles.shutterLabel}>{secondAngle ? he.anotherAngle : he.scan}</Text>
          </View>
          <View style={styles.side}>
            <Pressable onPress={() => router.push('/history')} disabled={busy} accessibilityRole="button" accessibilityLabel={he.myScans} style={styles.glassBig}><Text style={styles.sideIcon}>🕘</Text></Pressable>
            <Text style={styles.sideLabel}>{he.myScans}</Text>
          </View>
        </View>
      </SafeAreaView>
      {samples}
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, backgroundColor: '#000' },
  permission: { backgroundColor: '#FAFAF7' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  pad: { padding: 24, gap: 14 },
  emoji: { fontSize: 44 },
  title: { fontSize: 24, fontWeight: '700', textAlign: 'center' },
  body: { fontSize: 17, textAlign: 'center', color: '#444', lineHeight: 24 },
  primary: { backgroundColor: '#8A0C1B', paddingHorizontal: 32, paddingVertical: 15, borderRadius: 14, minHeight: 48 },
  primaryText: { color: '#fff', fontSize: 18, fontWeight: '700' },
  link: { color: '#8A0C1B', fontSize: 16, fontWeight: '700', padding: 8 },
  trust: { color: '#6b6b66', fontSize: 13 },
  overlay: { flex: 1, alignItems: 'center', justifyContent: 'space-between', paddingVertical: 12, paddingHorizontal: 16 },
  topBar: { alignSelf: 'stretch', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 4, paddingTop: 4 },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  brandIcon: { width: 32, height: 32, borderRadius: 9 },
  brandText: { color: '#fff', fontSize: 16, fontWeight: '800', textShadowColor: 'rgba(0,0,0,0.5)', textShadowRadius: 4 },
  topBtns: { flexDirection: 'row', gap: 8 },
  glassAvatar: { width: 40, height: 40, borderRadius: 20 },
  glass: { width: 44, height: 44, borderRadius: 22, backgroundColor: 'rgba(0,0,0,0.45)', alignItems: 'center', justifyContent: 'center' },
  glassWide: { height: 44, borderRadius: 22, paddingHorizontal: 14, backgroundColor: 'rgba(0,0,0,0.45)', alignItems: 'center', justifyContent: 'center' },
  glassText: { color: '#fff', fontSize: 15, fontWeight: '800' },
  hintBox: { backgroundColor: 'rgba(0,0,0,0.55)', paddingHorizontal: 16, paddingVertical: 8, borderRadius: 20 },
  hint: { color: '#fff', fontSize: 16 },
  frame: { width: '74%', aspectRatio: 1, borderRadius: 28, borderWidth: 2, borderColor: 'rgba(255,255,255,0.85)', alignItems: 'center', justifyContent: 'center' },
  frameBusy: { borderColor: '#FFD34D' },
  checking: { backgroundColor: 'rgba(0,0,0,0.55)', borderRadius: 16, paddingHorizontal: 18, paddingVertical: 12, alignItems: 'center', gap: 6 },
  checkingText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  error: { color: '#fff', backgroundColor: 'rgba(180,30,30,0.85)', padding: 10, borderRadius: 10 },
  controls: { alignSelf: 'stretch', flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-around', paddingBottom: 4 },
  side: { alignItems: 'center', gap: 6, minWidth: 88 },
  glassBig: { width: 54, height: 54, borderRadius: 27, backgroundColor: 'rgba(0,0,0,0.45)', alignItems: 'center', justifyContent: 'center' },
  sideIcon: { fontSize: 22 },
  sideLabel: { color: '#fff', fontSize: 13, fontWeight: '700', textShadowColor: 'rgba(0,0,0,0.6)', textShadowRadius: 3 },
  shutter: { width: 78, height: 78, borderRadius: 39, borderWidth: 4, borderColor: '#fff', alignItems: 'center', justifyContent: 'center' },
  shutterInner: { width: 62, height: 62, borderRadius: 31, backgroundColor: '#fff' },
  shutterLabel: { color: '#fff', fontSize: 15, fontWeight: '800', textShadowColor: 'rgba(0,0,0,0.6)', textShadowRadius: 3 },
  scrim: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)' },
  sheet: { backgroundColor: '#F6F1E6', borderTopLeftRadius: 26, borderTopRightRadius: 26, padding: 20, gap: 10 },
  sheetTitle: { fontSize: 24, fontWeight: '900', color: '#2A1C1E' },
  sheetBody: { fontSize: 15, color: '#4A3C3E' },
  samples: { flexDirection: 'row', gap: 10, marginVertical: 6 },
  sample: { flex: 1, alignItems: 'center', gap: 6 },
  sampleImg: { width: '100%', height: 104, borderRadius: 16 },
  sampleText: { fontSize: 14, fontWeight: '700', color: '#2A1C1E' },
  secondary: { borderWidth: 1.5, borderColor: '#8A0C1B', minHeight: 50, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  secondaryText: { color: '#8A0C1B', fontSize: 16, fontWeight: '700' },
});
