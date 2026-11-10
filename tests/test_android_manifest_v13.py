from pathlib import Path
import re
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def test_android_manifest_has_unique_attributes_and_activities():
    path=ROOT/'android/app/src/main/AndroidManifest.xml'
    xml=path.read_text()
    assert xml.count('android:networkSecurityConfig=')==1
    assert xml.count('android:name=".CodeEditorActivity"')==1
    root=ET.fromstring(xml)
    app=root.find('application')
    names=[a.get('{http://schemas.android.com/apk/res/android}name') for a in app.findall('activity')]
    assert len(names)==len(set(names))
