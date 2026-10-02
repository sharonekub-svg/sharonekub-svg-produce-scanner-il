// Return page of Google sign-in (auth.ts redirects here). On the web it hands the URL back to the sign-in
// popup's opener and closes the popup; in the phone app the deep link is already captured by
// openAuthSessionAsync, so this route only prevents an "unmatched route" screen and goes home.
import { Redirect } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';

WebBrowser.maybeCompleteAuthSession();

export default function AuthCallback() {
  return <Redirect href="/" />;
}
