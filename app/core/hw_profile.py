import psutil
import platform

def get_hardware_profile():
    """
    Simplified hardware profiling inspired by llmfit.
    Determines available RAM and suggests an Ollama model.
    """
    total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)
    os_info = platform.system()
    
    profile = {
        "ram_gb": round(total_ram_gb, 2),
        "os": os_info,
        "recommended_model": "llama3.2:3b" # Default safe bet
    }
    
    if total_ram_gb < 8:
        profile["recommended_model"] = "llama3.2:1b"
        profile["tier"] = "Entry (Limited Performance)"
    elif total_ram_gb < 16:
        profile["recommended_model"] = "llama3.2:3b"
        profile["tier"] = "Standard (Balanced)"
    elif total_ram_gb < 32:
        profile["recommended_model"] = "mistral:7b"
        profile["tier"] = "Power (High Quality)"
    else:
        profile["recommended_model"] = "llama3:8b"
        profile["tier"] = "Enterprise (Maximum Quality)"
        
    return profile

if __name__ == "__main__":
    print(get_hardware_profile())
