#!/bin/sh
# Fetch the build-time dependencies of the iOS app into ios/vendor (not committed), verified by SHA-256.
#
#   Python-3.14-iOS-support.b11  BeeWare Python-Apple-support: CPython 3.14.7 as Python.xcframework + utils.sh
#   numpy 2.5.2.post1 cp314 iOS  BeeWare's iOS wheels (device + arm64 simulator), minimum iOS 17.0
#
# These are linked into the app at build time; the app downloads nothing at run time.
set -e
cd "$(dirname "$0")/../vendor" 2>/dev/null || { mkdir -p "$(dirname "$0")/../vendor"; cd "$(dirname "$0")/../vendor"; }

fetch() {  # name url sha256
    if [ ! -f "$1" ] || [ "$(shasum -a 256 "$1" | cut -d' ' -f1)" != "$3" ]; then
        echo "fetching $1"
        curl -fL --retry 3 -o "$1.part" "$2"
        mv "$1.part" "$1"
    fi
    got=$(shasum -a 256 "$1" | cut -d' ' -f1)
    [ "$got" = "$3" ] || { echo "error: $1 sha256 $got != $3"; exit 1; }
}

INDEX=https://pypi.anaconda.org/beeware/simple/numpy/
wheel_url() {  # resolve a wheel's href from BeeWare's simple index
    curl -fsL "$INDEX" | tr '"' '\n' | grep -F "$1" | grep -E '^https?://' | head -1 | sed 's/#.*//'
}

fetch Python-3.14-iOS-support.b11.tar.gz \
    https://github.com/beeware/Python-Apple-support/releases/download/3.14-b11/Python-3.14-iOS-support.b11.tar.gz \
    b591f3301bd22a4f423c49c746cac9e55558b909fd14d6eb8327ccc62234ab7b
for w in numpy-2.5.2.post1-cp314-cp314-ios_17_0_arm64_iphoneos.whl:45c17fefb691afed2ced1f58100f14cad5daf9874d8b6683cae1c4efdeb90169 \
         numpy-2.5.2.post1-cp314-cp314-ios_17_0_arm64_iphonesimulator.whl:c5c3057efe1dd428193993ff98dca84ddb34ffddb9c3577e565990c1f665ac1a; do
    name=${w%%:*}
    sha=${w##*:}
    [ -f "$name" ] && [ "$(shasum -a 256 "$name" | cut -d' ' -f1)" = "$sha" ] && continue
    fetch "$name" "$(wheel_url "$name")" "$sha"
done

if [ ! -d py/Python.xcframework ]; then
    mkdir -p py
    tar -xzf Python-3.14-iOS-support.b11.tar.gz -C py
fi
echo "vendor ready"
