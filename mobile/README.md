# ChordFlow phone apps

Two routes. Start with the first: it costs nothing and needs no app store.

## 1. Install the web app on a phone (works today)
After the page is on GitHub Pages (see the root README), open its address on the phone:
- **iPhone (Safari):** Share, then "Add to Home Screen".
- **Android (Chrome):** menu, then "Install app".

It opens full screen with its own icon, and works offline after the first visit (`docs/sw.js`).

## 2. Real iOS and Android apps (Capacitor)
The app is the same web page inside a native shell. Nothing is rewritten.

```
cd mobile
npm install
npx cap add android        # once
npx cap add ios            # once, on a Mac only
npm run sync               # run after every web change
```

### Microphone permission (needed for "Listen")
- **iOS:** after `cap add ios`, open `ios/App/App/Info.plist` and add
  `NSMicrophoneUsageDescription` = "ChordFlow listens to a song to show its chords. Audio stays on your phone."
- **Android:** in `android/app/src/main/AndroidManifest.xml` add
  `<uses-permission android:name="android.permission.RECORD_AUDIO" />` and
  `<uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />`.

### Building
- **Android:** `npm run android` opens Android Studio, then Build > Generate Signed Bundle. Or let GitHub build it for you:
  Actions > "Android debug build" > Run workflow, then download the `.apk` (no installs on your computer).
  Publishing on Google Play is a one-time $25 fee.
- **iOS:** needs a Mac with Xcode and an Apple Developer account ($99 a year). `npm run ios`, then Product > Archive.

### Known risks (none of this has been run on a device yet)
- Live listening uses the microphone through the web view. It should work on current iOS and Android web views, but test on real phones.
- YouTube embeds can refuse to play inside an app shell ("error 153") unless the shell has a real https origin. The config
  above sets one (`https://app.chordflow.local`); if embeds still fail, set `hostname` to your real domain.
- Apple reviews apps that are only a website in a shell more strictly. Live listening, the offline chart tools and the Keys
  and Guitar views are what make it a real app; lean on them in the review notes.
- Streaming-service audio cannot be analyzed, so the app should always describe "Listen" as using the microphone.
