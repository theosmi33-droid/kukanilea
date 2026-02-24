"""
scripts/build/spec_base.py
Basis-Konfiguration für das Gold v1.5.0 Bundling.
Zwingt statische Modelle und Certs in das Binary.
"""
import os
from PyInstaller.utils.hooks import collect_data_files

def get_datas():
    datas = [
        ('templates', 'templates'),
        ('static', 'static'),
        ('app/core/certs/license_pub.pem', 'app/core/certs'),
        # Bundling ONNX models for 100% Offline performance
        # ('assets/models/picoclaw.onnx', 'assets/models'),
        # ('assets/models/whisper-tiny.bin', 'assets/models'),
    ]
    # Ensure instance is NEVER bundled
    return [d for d in datas if d[0] != 'instance']

# Hidden imports for critical Gold features
HIDDEN_IMPORTS = [
    'cryptography',
    'fastapi',
    'uvicorn',
    'onnxruntime',
    'faster_whisper'
]
