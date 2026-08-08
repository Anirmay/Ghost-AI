import os
import json

CONFIG_FILE = "config.json"
MEMORY_FILE = "memory.txt"

DEFAULT_CONFIG = {
    "api_key": "",
    "hotkey": "ctrl+shift+s",
    "opacity": 0.9,
    "theme": "neon_blue",
    "font_size": 12,
    "width": 450,
    "height": 400,
    "x": 100,
    "y": 100,
    "click_through": False
}

def get_base_dir():
    """Returns the centralized, persistent settings directory in the user's home folder."""
    path = os.path.expanduser("~/.ghostai")
    os.makedirs(path, exist_ok=True)
    return path

def load_config():
    """Loads configuration from config.json, creating it if it doesn't exist."""
    base_dir = get_base_dir()
    path = os.path.join(base_dir, CONFIG_FILE)
    
    # Migrate legacy config if global doesn't exist but local does
    if not os.path.exists(path):
        legacy_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        legacy_path = os.path.join(legacy_dir, CONFIG_FILE)
        if os.path.exists(legacy_path):
            try:
                import shutil
                shutil.copy2(legacy_path, path)
                print(f"[+] Migrated legacy config.json from {legacy_path} to {path}")
            except Exception as e:
                print(f"[-] Error migrating config: {e}")

    if not os.path.exists(path):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Merge with default config to ensure all keys exist
            config = DEFAULT_CONFIG.copy()
            config.update(data)
            return config
    except Exception as e:
        print(f"[-] Error loading config: {e}")
        return DEFAULT_CONFIG.copy()

def save_config(config):
    """Saves the config dict back to config.json."""
    base_dir = get_base_dir()
    path = os.path.join(base_dir, CONFIG_FILE)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[-] Error saving config: {e}")
        return False

def load_memory():
    """Loads text from memory.txt, creating it with instructions if it doesn't exist."""
    base_dir = get_base_dir()
    path = os.path.join(base_dir, MEMORY_FILE)
    
    # Migrate legacy memory if global doesn't exist but local does
    if not os.path.exists(path):
        legacy_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        legacy_path = os.path.join(legacy_dir, MEMORY_FILE)
        if os.path.exists(legacy_path):
            try:
                import shutil
                shutil.copy2(legacy_path, path)
                print(f"[+] Migrated legacy memory.txt from {legacy_path} to {path}")
            except Exception as e:
                print(f"[-] Error migrating memory file: {e}")

    if not os.path.exists(path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("# =========================================================\n")
                f.write("# GHOSTAI PRIVATE MEMORY / KNOWLEDGE BASE\n")
                f.write("# =========================================================\n")
                f.write("# Write down any data you want GhostAI to remember.\n")
                f.write("# You can write bullet points, facts, or paste documents.\n")
                f.write("# The AI assistant will always read this memory file to answer questions correctly.\n")
                f.write("# \n")
                f.write("# Examples:\n")
                f.write("- My name is John Doe.\n")
                f.write("- My main email is j.doe@example.com\n")
                f.write("- I am currently working on a stealth screen overlay project called GhostAI.\n")
            return ""
        except Exception as e:
            print(f"[-] Error initializing memory file: {e}")
            return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"[-] Error loading memory: {e}")
        return ""

def save_memory(content):
    """Saves new content to memory.txt."""
    base_dir = get_base_dir()
    path = os.path.join(base_dir, MEMORY_FILE)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"[-] Error saving memory: {e}")
        return False

def append_to_memory(line):
    """Appends a new line of facts/points to memory.txt."""
    base_dir = get_base_dir()
    path = os.path.join(base_dir, MEMORY_FILE)
    try:
        # Load memory first to see if a newline is needed
        existing = load_memory()
        with open(path, "a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write(f"- {line}\n")
        return True
    except Exception as e:
        print(f"[-] Error appending to memory: {e}")
        return False
