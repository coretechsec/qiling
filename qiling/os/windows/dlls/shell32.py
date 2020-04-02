#!/usr/bin/env python3
#
# Cross Platform and Multi Architecture Advanced Binary Emulation Framework
# Built on top of Unicorn emulator (www.unicorn-engine.org)

import struct
import time
from qiling.os.windows.const import *
from qiling.os.fncc import *
from qiling.os.utils import *
from qiling.os.windows.fncc import *
from qiling.os.windows.utils import *
from qiling.os.memory import align
from qiling.os.windows.thread import *
from qiling.os.windows.handle import *
from qiling.exception import *


# DWORD_PTR SHGetFileInfoW(
#   LPCWSTR     pszPath,
#   DWORD       dwFileAttributes,
#   SHFILEINFOW *psfi,
#   UINT        cbFileInfo,
#   UINT        uFlags
# );
@winapi(cc=STDCALL, params={
    "pszPath": WSTRING,
    "dwFileAttributes": DWORD,
    "psfi": POINTER,
    "cbFileInfo": UINT,
    "uFlags": UINT
})
def hook_SHGetFileInfoW(ql, address, params):
    flags = params["uFlags"]
    if flags == SHGFI_LARGEICON:
        return 1
    else:
        ql.dprint(0, flags)
        raise QlErrorNotImplemented("[!] API not implemented")


def _ShellExecute(ql, dic: dict):
    handle_window = int.from_bytes(dic["hwnd"], byteorder="little") if not isinstance(dic["hwnd"], int) else dic["hwnd"]
    pt_operation = int.from_bytes(dic["lpVerb"], byteorder="little") if not isinstance(dic["lpVerb"], int) \
        else dic["lpVerb"]
    pt_file = int.from_bytes(dic["lpFile"], byteorder="little") if not isinstance(dic["lpFile"], int) else dic["lpFile"]
    pt_params = int.from_bytes(dic["lpParameters"], byteorder="little") if not isinstance(dic["lpParameters"], int) \
        else dic["lpParameters"]
    pt_directory = int.from_bytes(dic["lpDirectory"], byteorder="little") if not isinstance(dic["lpDirectory"], int) \
        else dic["lpDirectory"]

    operation = read_wstring(ql, pt_operation) if pt_operation != 0 else ""
    params = read_wstring(ql, pt_params) if pt_params != 0 else ""
    file = read_wstring(ql, pt_file) if pt_file != 0 else ""
    directory = read_wstring(ql, pt_file) if pt_directory != 0 else ""
    show = int.from_bytes(dic["nShow"], byteorder="little") if not isinstance(dic["nShow"], int) else dic["nShow"]

    ql.dprint(2, "[=] Sample executed a shell command!")
    ql.dprint(2, "[-] Operation: %s " % operation)
    ql.dprint(2, "[-] Parameters: %s " % params)
    ql.dprint(2, "[-] File: %s " % file)
    ql.dprint(2, "[-] Directory: %s " % directory)
    if show == SW_HIDE:
        ql.dprint(2, "[=] Sample is creating a hidden window!")
    if operation == "runas":
        ql.dprint(2, "[=] Sample is executing shell command as administrator!")
    process = Thread(ql, status=0, isFake=True)
    handle = Handle(thread=process)
    ql.handle_manager.append(handle)
    return handle


# typedef struct _SHELLEXECUTEINFOA {
#   DWORD     cbSize;
#   ULONG     fMask;
#   HWND      hwnd;
#   LPCSTR    lpVerb;
#   LPCSTR    lpFile;
#   LPCSTR    lpParameters;
#   LPCSTR    lpDirectory;
#   int       nShow;
#   HINSTANCE hInstApp;
#   void      *lpIDList;
#   LPCSTR    lpClass;
#   HKEY      hkeyClass;
#   DWORD     dwHotKey;
#   union {
#     HANDLE hIcon;
#     HANDLE hMonitor;
#   } DUMMYUNIONNAME;
#   HANDLE    hProcess;
# } SHELLEXECUTEINFOA, *LPSHELLEXECUTEINFOA;


# BOOL ShellExecuteExW(
#   SHELLEXECUTEINFOA *pExecInfo
# );
@winapi(cc=STDCALL, params={
    "pExecInfo": POINTER
})
def hook_ShellExecuteExW(ql, address, params):
    pointer = params["pExecInfo"]

    shell_execute_info = {"cbSize": ql.uc.mem_read(pointer, 4),
                          "fMask": ql.uc.mem_read(pointer + 4, 4),
                          "hwnd": ql.uc.mem_read(pointer + 8, ql.pointersize),
                          "lpVerb": ql.uc.mem_read(pointer + 8 + ql.pointersize, ql.pointersize),
                          "lpFile": ql.uc.mem_read(pointer + 8 + ql.pointersize * 2, ql.pointersize),
                          "lpParameters": ql.uc.mem_read(pointer + 8 + ql.pointersize * 3, ql.pointersize),
                          "lpDirectory": ql.uc.mem_read(pointer + 8 + ql.pointersize * 4, ql.pointersize),
                          "nShow": ql.uc.mem_read(pointer + 8 + ql.pointersize * 5, 4),
                          "hInstApp": ql.uc.mem_read(pointer + 12 + ql.pointersize * 5, 4),  # Must be > 32 for success
                          "lpIDList": ql.uc.mem_read(pointer + 16 + ql.pointersize * 5, ql.pointersize),
                          "lpClass": ql.uc.mem_read(pointer + 16 + ql.pointersize * 6, ql.pointersize),
                          "hkeyClass": ql.uc.mem_read(pointer + 16 + ql.pointersize * 7, ql.pointersize),
                          "dwHotKey": ql.uc.mem_read(pointer + 16 + ql.pointersize * 8, 4),
                          "dummy": ql.uc.mem_read(pointer + 20 + ql.pointersize * 8, ql.pointersize),
                          "hprocess": ql.uc.mem_read(pointer + 20 + ql.pointersize * 9, ql.pointersize),
                          }

    handle = _ShellExecute(ql, shell_execute_info)

    # Write results
    shell_execute_info["hInstApp"] = 0x21.to_bytes(4, byteorder="little")
    shell_execute_info["hprocess"] = ql.pack(handle.id)
    # Check everything is correct
    values = b"".join(shell_execute_info.values())
    assert len(values) == shell_execute_info["cbSize"][0]

    # Rewrite memory
    ql.uc.mem_write(pointer, values)
    return 1


# HINSTANCE ShellExecuteW(
#   HWND    hwnd,
#   LPCWSTR lpOperation,
#   LPCWSTR lpFile,
#   LPCWSTR lpParameters,
#   LPCWSTR lpDirectory,
#   INT     nShowCmd
# );
@winapi(cc=STDCALL, params={
    "hwnd": HANDLE,
    "lpVerb": POINTER,
    "lpFile": POINTER,
    "lpParameters": POINTER,
    "lpDirectory": POINTER,
    "nShow": INT
})
def hook_ShellExecuteW(ql, address, params):
    _ = _ShellExecute(ql, params)
    return 33


# BOOL SHGetSpecialFolderPathW(
#   HWND   hwnd,
#   LPWSTR pszPath,
#   int    csidl,
#   BOOL   fCreate
# );
@winapi(cc=STDCALL, params={
    "hwnd": HANDLE,
    "pszPath": POINTER,
    "csidl": INT,
    "fCreate": BOOL
})
def hook_SHGetSpecialFolderPathW(ql, address, params):
    directory_id = params["csidl"]
    dst = params["pszPath"]
    if directory_id == CSIDL_COMMON_APPDATA:
        path = ql.config["PATHS"]["appdata"]
        # We always create the directory
        appdata_dir = path.split("C:\\")[1].replace("\\", "/")
        ql.dprint(0, "[+] dir path: %s" % path)
        path_emulated = os.path.join(ql.rootfs, appdata_dir)
        ql.dprint(0, "[!] emulated path: %s" % path_emulated)
        ql.uc.mem_write(dst, (path + "\x00").encode("utf-16le"))
        # FIXME: Somehow winodws path is wrong
        if not os.path.exists(path_emulated):
            try:
                os.makedirs(path_emulated, 0o755)
                ql.dprint(0, "[!] os.makedirs completed")
            except:
                ql.dprint(0, "[!] os.makedirs fail")    
    else:
        raise QlErrorNotImplemented("[!] API not implemented")
    return 1