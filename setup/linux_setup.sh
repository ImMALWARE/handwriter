#!/bin/bash
set -e

BUILD_NUM=$1
ARCH=$2
FPM_ARCH=$3
RPM_ARCH=$4
APPIMAGE_ARCH=$5

mkdir -p package_root/usr/bin
mkdir -p package_root/opt/handwriter
cp -r dist/handwriter/* package_root/opt/handwriter/
ln -s /opt/handwriter/handwriter package_root/usr/bin/handwriter
mkdir -p package_root/usr/share/mime/packages
cp setup/handwriter.xml package_root/usr/share/mime/packages/handwriter.xml
mkdir -p package_root/usr/share/applications
cp setup/handwriter.desktop package_root/usr/share/applications/handwriter.desktop
mkdir -p package_root/usr/share/icons/hicolor/256x256/apps
cp img/handwriter.png package_root/usr/share/icons/hicolor/256x256/apps/handwriter.png

fpm -s dir -t deb -n handwriter -v ${BUILD_NUM} -a ${FPM_ARCH} -C package_root .
mv handwriter_*.deb handwriter-linux-${ARCH}.deb

fpm -s dir -t rpm -n handwriter -v ${BUILD_NUM} -a ${RPM_ARCH} -C package_root .
mv handwriter-*.rpm handwriter-linux-${ARCH}.rpm || true

fpm -s dir -t pacman -n handwriter -v ${BUILD_NUM} -a ${RPM_ARCH} -C package_root .
mv handwriter-*.pkg.tar.zst handwriter-linux-${ARCH}.pkg.tar.zst || true

wget -qO appimagetool "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${APPIMAGE_ARCH}.AppImage"
chmod +x appimagetool
mkdir -p AppDir/usr/bin AppDir/usr/share/applications AppDir/usr/share/icons/hicolor/256x256/apps
cp -r dist/handwriter/* AppDir/usr/bin/
cp setup/handwriter.desktop AppDir/handwriter.desktop
cp setup/AppRun AppDir/AppRun
chmod +x AppDir/AppRun
cp img/handwriter.png AppDir/handwriter.png
./appimagetool --appimage-extract-and-run AppDir handwriter-linux-${ARCH}.AppImage || true