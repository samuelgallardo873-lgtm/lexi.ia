"""Almacenamiento de credenciales SAE mediante Windows Credential Manager."""

import ctypes
import json
import os
from ctypes import wintypes

TARGET = "LexBot/SAE"


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD),
                ("dwHighDateTime", wintypes.DWORD)]


class _CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", _FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def _api():
    if os.name != "nt":
        raise OSError("Las credenciales del SAE se almacenan en Windows Credential Manager.")
    advapi = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    advapi.CredWriteW.argtypes = [ctypes.POINTER(_CREDENTIALW), wintypes.DWORD]
    advapi.CredWriteW.restype = wintypes.BOOL
    advapi.CredReadW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(_CREDENTIALW)),
    ]
    advapi.CredReadW.restype = wintypes.BOOL
    advapi.CredFree.argtypes = [ctypes.c_void_p]
    advapi.CredFree.restype = None
    return advapi


def guardar_credenciales(cuit, password):
    if not cuit.strip() or not password:
        raise ValueError("Se requieren CUIT y contraseña para guardar las credenciales.")
    advapi = _api()
    payload = json.dumps(
        {"cuit": cuit.strip(), "password": password},
        ensure_ascii=False,
    ).encode("utf-8")
    blob = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
    cred = _CREDENTIALW(
        Flags=0,
        Type=1,  # CRED_TYPE_GENERIC
        TargetName=TARGET,
        Comment="Credenciales locales de LexBot para el portal SAE",
        CredentialBlobSize=len(payload),
        CredentialBlob=ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte)),
        Persist=2,  # CRED_PERSIST_LOCAL_MACHINE
        AttributeCount=0,
        Attributes=None,
        TargetAlias=None,
        UserName=cuit.strip(),
    )
    if not advapi.CredWriteW(ctypes.byref(cred), 0):
        raise ctypes.WinError(ctypes.get_last_error())


def leer_credenciales():
    advapi = _api()
    cred_ptr = ctypes.POINTER(_CREDENTIALW)()
    if not advapi.CredReadW(TARGET, 1, 0, ctypes.byref(cred_ptr)):
        error = ctypes.get_last_error()
        if error == 1168:  # ERROR_NOT_FOUND
            return None
        raise ctypes.WinError(error)
    try:
        cred = cred_ptr.contents
        raw = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict) or not data.get("cuit") or not data.get("password"):
            raise ValueError("El registro de credenciales de LexBot está incompleto.")
        return {"cuit": str(data["cuit"]), "password": str(data["password"])}
    finally:
        advapi.CredFree(cred_ptr)
