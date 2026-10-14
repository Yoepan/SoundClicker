import ctypes
from ctypes import wintypes
from typing import List, Dict, Optional, Tuple

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WINSTA_ALL = 0x37F
DESKTOP_ALL = 0x1FF

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

user32.WindowFromPoint.argtypes = [POINT]
user32.WindowFromPoint.restype = wintypes.HWND

user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]
user32.ScreenToClient.restype = wintypes.BOOL

user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]
user32.ClientToScreen.restype = wintypes.BOOL

class WindowManager:
    @staticmethod
    def ensure_desktop():
        try:
            hwinsta = user32.OpenWindowStationW("winsta0", False, WINSTA_ALL)
            if hwinsta:
                user32.SetProcessWindowStation(hwinsta)
                hdesk = user32.OpenDesktopW("default", 0, False, DESKTOP_ALL)
                if hdesk:
                    user32.SetThreadDesktop(hdesk)
        except Exception:
            pass

    @classmethod
    def list_windows(cls) -> List[Dict[str, any]]:
        cls.ensure_desktop()
        windows = []

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def enum_cb(hwnd, lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.strip()

            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top

            ignored = [
                "Program Manager", "Settings", "Windows Input Experience",
                "Default IME", "MSCTFIME UI"
            ]
            if w > 120 and h > 120 and title and title not in ignored:
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                windows.append({
                    "hwnd": int(hwnd),
                    "pid": int(pid.value),
                    "title": title,
                    "rect": (rect.left, rect.top, rect.right, rect.bottom),
                    "display": f"{title} (HWND: {hwnd})"
                })
            return True

        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        return windows

    @classmethod
    def get_window_at_point(cls, screen_x: int, screen_y: int) -> Tuple[Optional[int], str, Optional[int]]:
        cls.ensure_desktop()
        pt = POINT(screen_x, screen_y)
        hwnd = user32.WindowFromPoint(pt)
        if not hwnd:
            return None, "No Window", None

        root = user32.GetAncestor(hwnd, 2)
        target = root if root else hwnd

        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(target, ctypes.byref(pid))

        length = user32.GetWindowTextLengthW(target)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(target, buff, length + 1)
            return int(target), buff.value.strip(), int(pid.value)
        return int(target), f"HWND {target}", int(pid.value)

    @classmethod
    def get_pid_from_hwnd(cls, hwnd: int) -> Optional[int]:
        if not hwnd or not user32.IsWindow(hwnd):
            return None
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value)

    @classmethod
    def screen_to_client(cls, hwnd: int, screen_x: int, screen_y: int) -> Tuple[int, int]:
        cls.ensure_desktop()
        pt = POINT(screen_x, screen_y)
        user32.ScreenToClient(hwnd, ctypes.byref(pt))
        return pt.x, pt.y

    @classmethod
    def client_to_screen(cls, hwnd: int, client_x: int, client_y: int) -> Tuple[int, int]:
        cls.ensure_desktop()
        pt = POINT(client_x, client_y)
        user32.ClientToScreen(hwnd, ctypes.byref(pt))
        return pt.x, pt.y

    @classmethod
    def is_window_valid(cls, hwnd: int) -> bool:
        return bool(user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd))

    @classmethod
    def bring_to_foreground(cls, hwnd: int):
        cls.ensure_desktop()
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
