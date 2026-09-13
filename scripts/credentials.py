"""Windows per-user DPAPI storage. Never print decrypted credentials."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path


def runtime_dir():
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "runtimes" / "smart-deepseek-router"


def crypt(data, decrypt=False):
    if os.name != "nt":
        raise RuntimeError("DPAPI credential storage is Windows-only; use the environment on other systems")
    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source, target = Blob(len(data), buffer), Blob()
    api = ctypes.WinDLL("crypt32", use_last_error=True)
    fn = api.CryptUnprotectData if decrypt else api.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise RuntimeError("Windows credential encryption/decryption failed")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        kernel.LocalFree(target.data)


def save_key(key, directory=None):
    directory = Path(directory) if directory else runtime_dir()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "credential.dpapi"
    temporary = directory / "credential.dpapi.tmp"
    temporary.write_bytes(crypt(key.encode("utf-8")))
    temporary.replace(target)


def load_key(directory=None):
    directory = Path(directory) if directory else runtime_dir()
    path = directory / "credential.dpapi"
    return crypt(path.read_bytes(), decrypt=True).decode("utf-8") if path.is_file() else ""
