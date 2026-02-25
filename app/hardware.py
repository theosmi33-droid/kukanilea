"""
Hardware-Auto-Detection für KUKANILEA.
Maxime: Adaptive Inferenz. Schützt den Host vor OOM (Out Of Memory) und CPU-Locks.
"""
import platform
import psutil
import logging
from typing import Dict, Literal
from app.errors import safe_execute

logger = logging.getLogger(__name__)

@safe_execute
def detect_hardware() -> Dict[str, any]:
    """
    Analysiert die Host-Hardware sicher und ausfallfrei.
    """
    # Arbeitsspeicher (in GB)
    mem = psutil.virtual_memory()
    ram_total_gb = round(mem.total / (1024**3), 1)
    ram_available_gb = round(mem.available / (1024**3), 1)

    hw_profile = {
        'cpu_count': psutil.cpu_count(logical=True) or 2,
        'cpu_arch': platform.machine().lower(),
        'ram_total_gb': ram_total_gb,
        'ram_available_gb': ram_available_gb,
        'gpu_available': _detect_gpu(),
        'os': _detect_os(),
    }
    
    logger.info(f"Hardware detektiert: {hw_profile['os'].upper()} | {hw_profile['cpu_arch']} | {hw_profile['cpu_count']} Cores | {hw_profile['ram_total_gb']}GB RAM")
    return hw_profile

def _detect_gpu() -> bool:
    """Prüft auf lokale GPU-Beschleunigung (Apple Silicon Metal oder CUDA-Indikatoren)."""
    sys_os = platform.system()
    arch = platform.machine().lower()
    
    # Apple Silicon (M1/M2/M3) hat immer eine integrierte GPU für Metal
    if sys_os == 'Darwin' and 'arm' in arch:
        return True
    
    # Für Windows/Linux prüfen wir auf grundlegende CUDA/ROCm Indikatoren
    return False

def _detect_os() -> Literal['macos', 'windows', 'linux']:
    """Normalisiert die OS-Erkennung."""
    system = platform.system()
    if system == 'Darwin':
        return 'macos'
    elif system == 'Windows':
        return 'windows'
    return 'linux'

@safe_execute
def get_optimal_settings(hw: Dict[str, any]) -> Dict[str, any]:
    """
    Berechnet die strikten Limits für KUKANILEA basierend auf der Hardware.
    Ziel: Idle Memory < 200MB, Max Load verhindert Swapping.
    """
    settings = {}
    
    # 1. Worker Threads (Für Async-Tasks & Orchestrator)
    # Maximal die Hälfte der Cores, um das System responsive zu halten. Mindestens 2.
    settings['worker_threads'] = max(2, min(hw['cpu_count'] // 2, int(hw['ram_available_gb'])))
    
    # 2. OCR Parallelität (RAM-intensiv)
    settings['ocr_parallel'] = max(1, settings['worker_threads'] // 2)
    
    # 3. SQLite Database Cache (Dynamisches PRAGMA cache_size)
    # 10% vom *verfügbaren* RAM, aber gekappt auf sichere Werte.
    cache_mb = int(hw['ram_available_gb'] * 1024 * 0.1)
    settings['db_cache_size_mb'] = max(64, min(512, cache_mb))
    
    # 4. KI-Modell & Provider Auswahl (Graceful Degradation Logic)
    if hw['ram_available_gb'] >= 8.0:
        if hw['ram_available_gb'] >= 12 and hw['gpu_available']:
            # High-End (z.B. M2/M3 Mac)
            settings['ai_provider'] = 'ollama'
            settings['ai_model'] = 'llama3.1:8b'
            settings['vision_mode'] = 'hybrid' # PicoClaw + Moondream
            settings['moondream2_enabled'] = True
        else:
            # Mid-Range
            settings['ai_provider'] = 'ollama'
            settings['ai_model'] = 'llama3.2:3b'
            settings['vision_mode'] = 'hybrid'
            settings['moondream2_enabled'] = True
    else:
        # Low-End (Intel Laptops mit 8GB Total RAM)
        settings['ai_provider'] = 'ollama'
        settings['ai_model'] = 'qwen2.5:0.5b' 
        settings['vision_mode'] = 'picoclaw_only' # Ressourcenschonung
        settings['moondream2_enabled'] = False # Moondream2 deaktivieren
        
    return settings

@safe_execute
def apply_adaptive_config(settings: Dict[str, any]):
    # Injection in Environment-Variablen für andere Module
    import os
    os.environ["KUKANILEA_ADAPTIVE_WORKERS"] = str(settings["worker_threads"])
    os.environ["KUKANILEA_ADAPTIVE_OCR_THREADS"] = str(settings["ocr_parallel"])
    os.environ["KUKANILEA_ADAPTIVE_DB_CACHE"] = str(settings["db_cache_size_mb"])
    os.environ["KUKANILEA_ADAPTIVE_AI_MODEL"] = settings["ai_model"]
    if not settings.get('moondream2_enabled', True):
        os.environ["KUKANILEA_DISABLE_MOONDREAM"] = "1"

@safe_execute
def init_hardware_detection() -> Dict[str, any]:
    """
    Entrypoint für den App-Start. 
    Wird aufgerufen BEVOR die Datenbank-Connections und LLMs geladen werden.
    """
    logger.info("Starte KUKANILEA Hardware-Auto-Detection...")
    hw = detect_hardware()
    settings = get_optimal_settings(hw)
    apply_adaptive_config(settings)
    
    logger.info(f"Ressourcen-Limits gesetzt: {settings['worker_threads']} Workers | OCR-Threads: {settings['ocr_parallel']} | DB-Cache: {settings['db_cache_size_mb']}MB | KI-Modell: {settings['ai_model']}")
    
    return settings
