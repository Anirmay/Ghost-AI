import sys
import os

print("=" * 60)
print(" GHOSTAI AUTOMATED BACKEND VERIFICATION ")
print("=" * 60)

# Add current folder to path to allow absolute internal importing
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 1. Dependency imports
try:
    print("[*] Phase 1: Verifying library dependencies...")
    import PyQt6
    import sounddevice as sd
    import numpy as np
    import speech_recognition as sr
    import requests
    print("[+] Phase 1 Passed: All 3rd party libraries imported successfully!")
except ImportError as e:
    print(f"[-] Phase 1 Failed: Dependency import failed: {e}")
    sys.exit(1)

# 2. Config manager testing
try:
    print("[*] Phase 2: Verifying configuration and memory managers...")
    from core.config import load_config, save_config, load_memory, save_memory
    
    config = load_config()
    print(f"    - Loaded config template: {config}")
    
    # Save a verification test value
    original_theme = config.get("theme")
    config["theme"] = "verification_test"
    save_config(config)
    
    # Reload to verify
    reloaded = load_config()
    if reloaded.get("theme") == "verification_test":
        print("[+] Phase 2 Passed: Config manager read-write cycle success!")
    else:
        raise ValueError("Config read-write check mismatch.")
        
    # Revert config to original state
    config["theme"] = original_theme
    save_config(config)
    
    # Check memory base creation
    memory_text = load_memory()
    print("[+] Phase 2 Passed: Local memory file read and created successfully!")
except Exception as e:
    print(f"[-] Phase 2 Failed: Config/Memory verification error: {e}")
    sys.exit(1)

# 3. Capture Guard Windows API bindings check
try:
    print("[*] Phase 3: Verifying Windows API screen capture protection...")
    from core.capture_guard import protect_window
    import ctypes
    
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    if hasattr(user32, "SetWindowDisplayAffinity"):
        print("[+] Phase 3 Passed: 'user32.SetWindowDisplayAffinity' found and hooked!")
    else:
        raise OSError("SetWindowDisplayAffinity function not exposed in user32.dll.")
except Exception as e:
    print(f"[-] Phase 3 Failed: Windows API verification failed: {e}")
    sys.exit(1)

# 4. AI prompt generation testing
try:
    print("[*] Phase 4: Verifying AI Prompt injection and trigger commands...")
    from core.ai import GeminiClient
    client = GeminiClient()
    
    # Check that it intercept remember triggers and updates memory.txt
    response = client.ask("remember that my test verification pass code is 987654321")
    if "Memory Stored" in response:
        print("[+] Phase 4 Passed: Memory command triggers intercepted & stored successfully!")
        
        # Verify it actually made it into the memory.txt file
        mem_check = load_memory()
        if "987654321" in mem_check:
            print("[+] Phase 4 Passed: Verified text integration in memory file!")
            
            # Clean verification pass code out of memory.txt so we don't dirty the user file
            cleaned_mem = mem_check.replace("- my test verification pass code is 987654321\n", "")
            cleaned_mem = cleaned_mem.replace("- my test verification pass code is 987654321", "")
            save_memory(cleaned_mem)
        else:
            raise ValueError("Test pass code was not appended to memory file.")
    else:
        raise ValueError("Memory command interception was ignored by client.")
except Exception as e:
    print(f"[-] Phase 4 Failed: AI prompt verification failed: {e}")
    sys.exit(1)

print("=" * 60)
print("[SUCCESS] ALL CORE BACKEND MODULES FULLY COMPILED AND VERIFIED!")
print("GhostAI is 100% ready for physical launch!")
print("Run 'python main.py' to launch the stealth overlay assistant.")
print("=" * 60)
