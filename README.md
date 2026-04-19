# NoBrowserFacebookMessenger

Patches the Facebook Messenger APK to open links in the system browser instead of the built-in in-app browser (BrowserLiteActivity).

## How it works

Decompiles the APK with apktool, patches the `MessengerBrowserLauncher` smali method to fire a standard `ACTION_VIEW` intent, recompiles, and signs with a debug key.

## Requirements

- Java
- Python 3
- curl

apktool and uber-apk-signer are downloaded automatically on first run.

## Usage

Download the Messenger APK from [APKMirror](https://www.apkmirror.com/apk/facebook-2/messenger/).

> Tested with version **57.0.0.53.76** (arm64-v8a, variant 341413176).

```bash
./patch_and_build.sh <your_apk.apk>
```

Output: `patched_<your_apk.apk>` in the same directory as the input APK.

## Credits

- [iBotPeaches/Apktool](https://github.com/iBotPeaches/Apktool)
- [patrickfav/uber-apk-signer](https://github.com/patrickfav/uber-apk-signer)