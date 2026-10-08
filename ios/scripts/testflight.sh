#!/bin/sh
# Archive, sign and upload XENO ZIRAN SIMULATOR to App Store Connect (TestFlight + usable for App Store submission).
# It never submits for App Review or external beta review by itself.
#
# Preconditions (not automatable):
#   1. The team's Account Holder has accepted the latest Apple Developer Program License Agreement
#      (developer.apple.com/account) and any pending App Store Connect agreements.
#   2. An App Store Connect app record exists for bundle ID io.platodesign.xenoziransimulator (it does: app 6819625252).
#
# Authentication: the team's App Store Connect API key (no Apple ID session needed).
#   ASC_KEY_ID / ASC_ISSUER_ID (required environment variables)
#   key file: ~/.appstoreconnect/private_keys/AuthKey_<ASC_KEY_ID>.p8
#
# Usage: sh ios/scripts/testflight.sh [build-number]   (version: MARKETING_VERSION in project.yml, now 1.0)
set -e
cd "$(dirname "$0")/.."
BUILD="${1:?give the build number: 1–3 are uploaded — pass 4, 5, … (never reuse one)}"
KEY_ID="${ASC_KEY_ID:?set ASC_KEY_ID (App Store Connect API key id)}"
ISSUER="${ASC_ISSUER_ID:?set ASC_ISSUER_ID (App Store Connect issuer id)}"
KEY="$HOME/.appstoreconnect/private_keys/AuthKey_$KEY_ID.p8"
ARCHIVE="$HOME/Library/Developer/Xcode/Archives/XenoZiranSimulator-$BUILD.xcarchive"
AUTH="-allowProvisioningUpdates -authenticationKeyPath $KEY -authenticationKeyID $KEY_ID -authenticationKeyIssuerID $ISSUER"

(cd ../frontend && npm run build:native)
xcodegen generate
# The archive is built unsigned and signed by the export step below with the Apple Distribution certificate and an
# App Store profile: automatic signing of the archive itself wants a development profile, which needs a
# registered device (the team has none), whereas App Store distribution needs no device.
xcodebuild -project XenoZiranSimulator.xcodeproj -scheme XenoZiranSimulator -configuration Release \
    -destination 'generic/platform=iOS' -archivePath "$ARCHIVE" CURRENT_PROJECT_VERSION="$BUILD" \
    CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY="" archive
# export: signed with the Apple Distribution certificate and an App Store profile (automatic, via the API key)
EXPORT="build/export-$BUILD"
sed 's#<string>upload</string>#<string>export</string>#' ExportOptions.plist > "build/ExportOptions-local.plist"
# shellcheck disable=SC2086
xcodebuild -exportArchive -archivePath "$ARCHIVE" -exportOptionsPlist build/ExportOptions-local.plist \
    -exportPath "$EXPORT" $AUTH
IPA="$EXPORT/XENO ZIRAN SIMULATOR.ipa"
# Apple validation, then upload of the same file; either fails the script on any error (set -e)
xcrun altool --validate-app -f "$IPA" -t ios --apiKey "$KEY_ID" --apiIssuer "$ISSUER"
xcrun altool --upload-app -f "$IPA" -t ios --apiKey "$KEY_ID" --apiIssuer "$ISSUER"
echo "uploaded build $BUILD — App Store Connect → TestFlight shows it after processing"
