import json
import os
import subprocess
import ctypes
from ctypes import wintypes
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


_SYSTEM_SID = "S-1-5-18"
_SYSTEM_ROOT = Path(os.environ.get("SystemRoot", r"C:\Windows"))
_POWERSHELL = _SYSTEM_ROOT / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
_SET_ACL = r"""
$ErrorActionPreference = 'Stop'
$root = $env:DOCUMENT_ACL_ROOT
$userSid = New-Object System.Security.Principal.SecurityIdentifier($env:DOCUMENT_ACL_SID)
$systemSid = New-Object System.Security.Principal.SecurityIdentifier('S-1-5-18')
$rights = [System.Security.AccessControl.FileSystemRights]::FullControl
$inheritance = [System.Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
$propagation = [System.Security.AccessControl.PropagationFlags]::None
$allow = [System.Security.AccessControl.AccessControlType]::Allow
$acl = New-Object System.Security.AccessControl.DirectorySecurity
$acl.SetOwner($userSid)
$acl.SetAccessRuleProtection($true, $false)
$acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($userSid, $rights, $inheritance, $propagation, $allow)))
$acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($systemSid, $rights, $inheritance, $propagation, $allow)))
Set-Acl -LiteralPath $root -AclObject $acl
"""
_READ_ACL = r"""
$ErrorActionPreference = 'Stop'
$rules = (Get-Acl -LiteralPath $env:DOCUMENT_ACL_ROOT).Access | ForEach-Object {
  [pscustomobject]@{
    sid = $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
    rights = [int]$_.FileSystemRights
    type = [int]$_.AccessControlType
    inherited = $_.IsInherited
  }
}
ConvertTo-Json -Compress -InputObject @($rules)
"""


def _powershell(script, *, root, sid=None):
    environment = os.environ.copy()
    environment["DOCUMENT_ACL_ROOT"] = str(root)
    if sid:
        environment["DOCUMENT_ACL_SID"] = sid
    result = subprocess.run(
        [str(_POWERSHELL), "-NoProfile", "-NonInteractive", "-Command", script],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise ImproperlyConfigured("Unable to enforce private document storage ACL")
    return result.stdout.strip()


def current_user_sid():
    result = subprocess.run(
        [str(_POWERSHELL), "-NoProfile", "-NonInteractive", "-Command", "[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    sid = result.stdout.strip()
    if result.returncode != 0 or not sid.startswith("S-"):
        raise ImproperlyConfigured("Unable to identify private storage service identity")
    return sid


def enforce_and_verify_private_acl(root):
    if os.name != "nt":
        raise ImproperlyConfigured("Private document storage ACL enforcement requires Windows")
    sid = current_user_sid()
    try:
        return verify_private_acl(root, sid=sid)
    except ImproperlyConfigured:
        pass
    _powershell(_SET_ACL, root=root, sid=sid)
    return verify_private_acl(root, sid=sid)


def verify_private_acl(root, *, sid=None):
    if os.name != "nt":
        raise ImproperlyConfigured("Private document storage ACL verification requires Windows")
    sid = sid or current_user_sid()
    try:
        rules = json.loads(_powershell(_READ_ACL, root=root))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ImproperlyConfigured("Unable to verify private document storage ACL") from exc
    if isinstance(rules, dict):
        rules = [rules]
    allowed = {sid, _SYSTEM_SID}
    if not isinstance(rules, list) or {rule.get("sid") for rule in rules} != allowed:
        raise ImproperlyConfigured("Private document storage ACL contains an untrusted principal")
    for rule in rules:
        if rule.get("type") != 0 or rule.get("inherited") is not False or not isinstance(rule.get("rights"), int):
            raise ImproperlyConfigured("Private document storage ACL is not an explicit allow-only boundary")
        if rule["rights"] & 0x1F01FF != 0x1F01FF:
            raise ImproperlyConfigured("Private document storage ACL does not grant required control")
    return frozenset(allowed)


class DirectoryReplacementLock:
    def __init__(self, path):
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        )
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32 = kernel32
        self.handle = kernel32.CreateFileW(
            str(path),
            0x0001,  # FILE_LIST_DIRECTORY
            0x00000001 | 0x00000002,  # share read/write, deliberately not delete
            None,
            3,  # OPEN_EXISTING
            0x02000000,  # FILE_FLAG_BACKUP_SEMANTICS
            None,
        )
        invalid = wintypes.HANDLE(-1).value
        if self.handle == invalid:
            raise ImproperlyConfigured("Unable to lock private storage root against replacement")

    def close(self):
        if self.handle and self.handle != wintypes.HANDLE(-1).value:
            self._kernel32.CloseHandle(self.handle)
            self.handle = None

    def __del__(self):
        self.close()


def lock_directory_against_replacement(path):
    if os.name != "nt":
        raise ImproperlyConfigured("Private storage replacement lock requires Windows")
    return DirectoryReplacementLock(path)
