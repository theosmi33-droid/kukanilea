import psutil
import platform
import subprocess
import os

def get_hardware_specs():
    specs = {
        "ram_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "os": platform.system(),
        "arch": platform.machine(),
        "vram_gb": 0,
        "gpu_type": "CPU"
    }
    
    # Apple Silicon (Unified Memory) detection
    if specs["os"] == "Darwin" and specs["arch"] == "arm64":
        specs["gpu_type"] = "Metal (Apple Silicon)"
        # Estimating available Unified Memory for GPU (typically up to 70% of total RAM)
        specs["vram_gb"] = round(specs["ram_gb"] * 0.7, 2)
    
    # NVIDIA GPU Detection (Windows/Linux)
    else:
        try:
            startupinfo = None
            creationflags = 0
            if specs["os"] == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = 0x08000000 # CREATE_NO_WINDOW
            
            nvidia_info = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,nounits,noheader"],
                encoding="utf-8",
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            specs["vram_gb"] = round(int(nvidia_info.strip()) / 1024, 2)
            specs["gpu_type"] = "CUDA (NVIDIA)"
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
            
    return specs

def get_optimal_settings(hw: dict) -> dict:
    """Berechnet die strikten Limits basierend auf der Hardware."""
    settings = {}
    settings['worker_threads'] = max(2, min(hw.get('cpu_count', 4) // 2, int(hw.get('ram_gb', 8))))
    settings['db_cache_size_mb'] = max(64, min(512, int(hw.get('ram_gb', 8) * 1024 * 0.1)))
    
    if hw.get('ram_gb', 8) >= 12:
        settings['ai_model'] = 'llama3.1:8b'
    else:
        settings['ai_model'] = 'llama3.2:3b'
        
    return settings

def get_optimal_llm_config():
    specs = get_hardware_specs()
    # Base recommendation: Llama-3.1-8B Q4_K_M requires ~4.9 GB VRAM
    config = {
        "n_gpu_layers": 0,
        "n_ctx": 4096,
        "model_path": "models/llama-3.1-8b-instruct-v0.1.Q4_K_M.gguf"
    }

    if specs["vram_gb"] >= 6:
        config["n_gpu_layers"] = -1  # Full GPU offloading
    elif 2 <= specs["vram_gb"] < 6:
        config["n_gpu_layers"] = 16  # Partial offloading
    
    return config, specs
