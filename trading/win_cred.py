"""Windows Credential Manager access with zero dependencies (stdlib ctypes only).

Secrets are stored per-Windows-user, DPAPI-encrypted at rest by the OS.
They never touch the registry, environment variables, or any repo file.

Usage from code:
    from trading.win_cred import get_secret
    key = get_secret("ETRADE_SANDBOX_KEY")

Usage from CLI (avoid passing secrets on the command line when possible):
    python -m trading.win_cred set ETRADE_PROD_KEY        # prompts for value
    python -m trading.win_cred get ETRADE_PROD_KEY        # prints value
    python -m trading.win_cred list                       # list stored names
    python -m trading.win_cred delete ETRADE_PROD_KEY
"""

import ctypes
import ctypes.wintypes as wt
import sys

_advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2  # persists across logins, still per-user secret
_PREFIX = "stocks-automation/"


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wt.DWORD), ("dwHighDateTime", wt.DWORD)]


class _CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ("Flags", wt.DWORD),
        ("Type", wt.DWORD),
        ("TargetName", wt.LPWSTR),
        ("Comment", wt.LPWSTR),
        ("LastWritten", _FILETIME),
        ("CredentialBlobSize", wt.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
        ("Persist", wt.DWORD),
        ("AttributeCount", wt.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wt.LPWSTR),
        ("UserName", wt.LPWSTR),
    ]


_PCREDENTIAL = ctypes.POINTER(_CREDENTIAL)

_advapi32.CredWriteW.argtypes = [_PCREDENTIAL, wt.DWORD]
_advapi32.CredWriteW.restype = wt.BOOL
_advapi32.CredReadW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD,
                                ctypes.POINTER(_PCREDENTIAL)]
_advapi32.CredReadW.restype = wt.BOOL
_advapi32.CredDeleteW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD]
_advapi32.CredDeleteW.restype = wt.BOOL
_advapi32.CredEnumerateW.argtypes = [wt.LPCWSTR, wt.DWORD, ctypes.POINTER(wt.DWORD),
                                     ctypes.POINTER(ctypes.POINTER(_PCREDENTIAL))]
_advapi32.CredEnumerateW.restype = wt.BOOL
_advapi32.CredFree.argtypes = [ctypes.c_void_p]
_advapi32.CredFree.restype = None


def set_secret(name: str, value: str) -> None:
    blob = value.encode("utf-16-le")
    buf = (ctypes.c_byte * len(blob)).from_buffer_copy(blob)
    cred = _CREDENTIAL()
    cred.Flags = 0
    cred.Type = CRED_TYPE_GENERIC
    cred.TargetName = _PREFIX + name
    cred.Comment = "stored by stocks-automation trading/win_cred.py"
    cred.CredentialBlobSize = len(blob)
    cred.CredentialBlob = ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))
    cred.Persist = CRED_PERSIST_LOCAL_MACHINE
    cred.UserName = None
    if not _advapi32.CredWriteW(ctypes.byref(cred), 0):
        raise OSError(f"CredWrite failed: {ctypes.get_last_error()}")


def get_secret(name: str) -> str | None:
    pcred = _PCREDENTIAL()
    ok = _advapi32.CredReadW(_PREFIX + name, CRED_TYPE_GENERIC, 0,
                             ctypes.byref(pcred))
    if not ok:
        return None
    try:
        c = pcred.contents
        raw = ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize)
        return raw.decode("utf-16-le")
    finally:
        _advapi32.CredFree(pcred)


def delete_secret(name: str) -> bool:
    return bool(_advapi32.CredDeleteW(_PREFIX + name, CRED_TYPE_GENERIC, 0))


def list_secrets() -> list[str]:
    count = wt.DWORD()
    pcreds = ctypes.POINTER(_PCREDENTIAL)()
    ok = _advapi32.CredEnumerateW(_PREFIX + "*", 0, ctypes.byref(count),
                                  ctypes.byref(pcreds))
    if not ok:
        return []
    try:
        return [pcreds[i].contents.TargetName[len(_PREFIX):]
                for i in range(count.value)]
    finally:
        _advapi32.CredFree(pcreds)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "list":
        for n in list_secrets():
            print(n)
    elif cmd == "get" and len(argv) == 3:
        v = get_secret(argv[2])
        if v is None:
            print(f"(not found: {argv[2]})", file=sys.stderr)
            return 1
        print(v)
    elif cmd == "set" and len(argv) in (3, 4):
        value = argv[3] if len(argv) == 4 else input(f"value for {argv[2]}: ").strip()
        set_secret(argv[2], value)
        print(f"stored {argv[2]} ({len(value)} chars)")
    elif cmd == "delete" and len(argv) == 3:
        print("deleted" if delete_secret(argv[2]) else "not found")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
