# Set up APK signing

Use a stable private signing key for a distributable build. Keep the same
key for future updates. A key is **not** your ADB key and is not included in
the image. See Google's [app-signing guide](https://developer.android.com/studio/publish/app-signing).

**Already have a release key?** Skip creation and set the variables below
to its path, alias and certificate fingerprint.

To create one **once**:

The directory, filename and alias below are generic examples. Choose your
own values; do not publish your actual signing configuration.

```bash
mkdir -p "$HOME/release-signing"
chmod 700 "$HOME/release-signing"
keytool -genkeypair -storetype JKS \
  -keystore "$HOME/release-signing/example-release.jks" \
  -alias example-release -keyalg RSA -keysize 4096 -validity 10000
```

Answer the prompts. Keep passwords private; do not put them in command
lines, screenshots, Git or chat. Back up the keystore securely.
Do not regenerate it for every build.

```bash
export APK_RELEASE_KEYSTORE="$HOME/release-signing/example-release.jks"
export APK_RELEASE_KEY_ALIAS="example-release"
keytool -list -v -keystore "$APK_RELEASE_KEYSTORE" -alias "$APK_RELEASE_KEY_ALIAS"
```

Copy the **SHA256** certificate fingerprint from that output and replace
the placeholder here. Colons are accepted:

```bash
export APK_RELEASE_CERT_SHA256="PASTE_YOUR_CERTIFICATE_SHA256_HERE"
```

The builder checks that fingerprint and prompts for signing passwords.
Without all three variables, it either refuses an incomplete configuration
or uses debug signing when none are set. Debug signing is not for release.

**Updating a debug-signed or differently signed image:** do not assume the
new E-Ink APK will preserve its old data. Android signature mismatches may
require app-data cleanup or a clean install. Back up first.

## How the builder uses the key

When none of the three variables is set, the offline builder uses
uber-apk-signer's debug signing configuration, for personal testing only.
The signer prompts for passwords; the build script does not accept passwords
as command-line arguments or save them. To return to a debug build, run
`unset APK_RELEASE_KEYSTORE APK_RELEASE_KEY_ALIAS APK_RELEASE_CERT_SHA256`.

The builder requires all three settings together,
asks the signer to verify the expected certificate, and verifies the resulting
APK. Keep the keystore backed up and privately managed; never commit it or its
passwords. Use this same key for every future A9 build. Changing the
certificate may cause Android to reject an update or reset the app's data.
Moving an already-flashed debug-signed system app to the release certificate
requires a fresh migration plan; test on a disposable device before publishing.
The experimental source-APK builder uses this same signer and configuration;
it does not use Gradle's separate debug signing key.

## Unified release builds and APK reuse

`python3 tools/build-release.py "$BASE"` builds and signs the source APK
automatically. Export all three release-key variables in that same terminal
before starting it. Signing remains interactive; never put passwords in the
release command or a configuration file.

With `--built-apk /path/to/signed.apk`, the builder does not rebuild or re-sign
the APK. It verifies its signature/alignment and, if `APK_RELEASE_CERT_SHA256`
is set, requires that fingerprint. Only the public fingerprint is needed for
this mode; the keystore and alias are not used and no password is requested.
Without an expected fingerprint, verification does not establish that the APK
uses your release key.
