import plistlib
import sys

if len(sys.argv) < 2:
    print("Usage: update_plist.py <path_to_Info.plist>")
    sys.exit(1)

f = sys.argv[1]
with open(f, 'rb') as fp:
    pl = plistlib.load(fp)

pl['CFBundleDocumentTypes'] = [
    {
        'CFBundleTypeExtensions': ['hwdoc'],
        'CFBundleTypeName': 'Handwriter Document',
        'CFBundleTypeRole': 'Editor',
        'LSHandlerRank': 'Owner'
    },
    {
        'CFBundleTypeExtensions': ['hfont'],
        'CFBundleTypeName': 'Handwriter Font',
        'CFBundleTypeRole': 'Editor',
        'LSHandlerRank': 'Owner'
    },
    {
        'CFBundleTypeExtensions': ['hwpap'],
        'CFBundleTypeName': 'Handwriter Paper Preset',
        'CFBundleTypeRole': 'Editor',
        'LSHandlerRank': 'Owner'
    }
]

pl['CFBundleLocalizations'] = ['en', 'ru']
pl['CFBundleDevelopmentRegion'] = 'en'


with open(f, 'wb') as fp:
    plistlib.dump(pl, fp)