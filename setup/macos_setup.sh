#!/bin/bash
set -e

ARCH=$1

python setup/update_plist.py dist/Handwriter.app/Contents/Info.plist

create-dmg \
  --volname "Handwriter" \
  --volicon "img/handwriter.icns" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "Handwriter.app" 200 190 \
  --hide-extension "Handwriter.app" \
  --app-drop-link 400 190 \
  "Handwriter-macOS-${ARCH}.dmg" \
  "dist/Handwriter.app" || true

if [ ! -f "Handwriter-macOS-${ARCH}.dmg" ]; then
  hdiutil create -volname "Handwriter" -srcfolder dist/Handwriter.app -ov -format UDZO "Handwriter-macOS-${ARCH}.dmg"
fi
