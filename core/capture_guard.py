import ctypes
from ctypes import wintypes

WDA_NONE = 0x00000000
WDA_MONITOR = 0x00000001
WDA_EXCLUDEFROMCAPTURE = 0x00000011  # 17 (Win10 version 2004+)

def protect_window(hwnd: int) -> bool:
    """
    Applies display affinity to prevent window from being captured in screen shares/recordings.
    It returns True if successful, False otherwise.
    """
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        
        # Check if SetWindowDisplayAffinity exists in user32.dll
        if not hasattr(user32, "SetWindowDisplayAffinity"):
            print("[-] SetWindowDisplayAffinity is not supported on this platform.")
            return False
            
        user32.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
        
        # Try applying WDA_EXCLUDEFROMCAPTURE (17) which completely hides the window in captures
        hwnd_ptr = ctypes.c_void_p(hwnd)
        success = user32.SetWindowDisplayAffinity(hwnd_ptr, WDA_EXCLUDEFROMCAPTURE)
        if success:
            print("[+] Successfully set display affinity to WDA_EXCLUDEFROMCAPTURE (17)")
            return True
            
        # Fallback to WDA_MONITOR (1) if WDA_EXCLUDEFROMCAPTURE fails
        error_code = ctypes.get_last_error()
        print(f"[-] WDA_EXCLUDEFROMCAPTURE failed with error code: {error_code}. Trying WDA_MONITOR...")
        
        success = user32.SetWindowDisplayAffinity(hwnd_ptr, WDA_MONITOR)
        if success:
            print("[+] Successfully set display affinity to WDA_MONITOR (1)")
            return True
            
        error_code = ctypes.get_last_error()
        print(f"[-] Failed to set any display protection. Error code: {error_code}")
        return False
    except Exception as e:
        print(f"[-] Exception during protect_window: {e}")
        return False
