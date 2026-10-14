import time
import random
import threading
import ctypes
from typing import Optional, Callable, Tuple

try:
    import pydirectinput
    pydirectinput.PAUSE = 0.01
except ImportError:
    pydirectinput = None

try:
    import winsound
except ImportError:
    winsound = None

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002

user32 = ctypes.windll.user32

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class ClickerEngine:
    def __init__(self, enable_beep: bool = True):
        self.enable_beep = enable_beep
        self.is_busy = False
        self._lock = threading.Lock()

    def play_beep(self, freq: int = 1200, duration_ms: int = 80):
        if not self.enable_beep or winsound is None:
            return
        threading.Thread(
            target=lambda: winsound.Beep(freq, duration_ms),
            daemon=True
        ).start()

    def mouse_click(self, button: str = "right", hold_duration: float = 0.06):
        btn = button.lower()
        if pydirectinput is not None:
            try:
                pydirectinput.mouseDown(button=btn)
                time.sleep(hold_duration)
                pydirectinput.mouseUp(button=btn)
                return
            except Exception:
                pass

        if btn == "right":
            user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            time.sleep(hold_duration)
            user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
        else:
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(hold_duration)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def foreground_fixed_click(
        self,
        screen_x: int,
        screen_y: int,
        button: str = "right",
        hold_duration: float = 0.06,
        jitter_px: int = 0,
        restore_cursor: bool = True
    ):
        old_pt = POINT()
        user32.GetCursorPos(ctypes.byref(old_pt))

        jx = random.randint(-jitter_px, jitter_px) if jitter_px > 0 else 0
        jy = random.randint(-jitter_px, jitter_px) if jitter_px > 0 else 0
        target_x = screen_x + jx
        target_y = screen_y + jy

        user32.SetCursorPos(target_x, target_y)
        time.sleep(0.015)
        self.mouse_click(button=button, hold_duration=hold_duration)

        if restore_cursor:
            time.sleep(0.015)
            user32.SetCursorPos(old_pt.x, old_pt.y)

    def post_background_click(
        self,
        hwnd: int,
        client_x: int,
        client_y: int,
        button: str = "right",
        hold_duration: float = 0.06,
        jitter_px: int = 0
    ) -> bool:
        if not hwnd or not user32.IsWindow(hwnd):
            return False

        btn = button.lower()
        jx = random.randint(-jitter_px, jitter_px) if jitter_px > 0 else 0
        jy = random.randint(-jitter_px, jitter_px) if jitter_px > 0 else 0
        cx = max(0, client_x + jx)
        cy = max(0, client_y + jy)
        lParam = (int(cy) << 16) | (int(cx) & 0xFFFF)

        if btn == "right":
            down_msg = WM_RBUTTONDOWN
            up_msg = WM_RBUTTONUP
            wParam = MK_RBUTTON
        else:
            down_msg = WM_LBUTTONDOWN
            up_msg = WM_LBUTTONUP
            wParam = MK_LBUTTON

        user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lParam)
        user32.PostMessageW(hwnd, down_msg, wParam, lParam)
        time.sleep(hold_duration)
        user32.PostMessageW(hwnd, up_msg, 0, lParam)
        return True

    def click_target(
        self,
        button: str = "right",
        mode: str = "cursor",
        target_hwnd: Optional[int] = None,
        point: Optional[Tuple[int, int]] = None,
        hold_duration: float = 0.06,
        jitter_px: int = 0,
        restore_cursor: bool = True
    ):
        if mode == "background" and target_hwnd and point:
            success = self.post_background_click(
                hwnd=target_hwnd,
                client_x=point[0],
                client_y=point[1],
                button=button,
                hold_duration=hold_duration,
                jitter_px=jitter_px
            )
            if success:
                return

        if mode == "fixed" and point:
            self.foreground_fixed_click(
                screen_x=point[0],
                screen_y=point[1],
                button=button,
                hold_duration=hold_duration,
                jitter_px=jitter_px,
                restore_cursor=restore_cursor
            )
            return

        self.mouse_click(button=button, hold_duration=hold_duration)

    def execute_action(
        self,
        action_type: str = "sequence",
        primary_button: str = "right",
        secondary_button: str = "right",
        delay: float = 0.5,
        use_humanizer: bool = True,
        mode: str = "cursor",
        target_hwnd: Optional[int] = None,
        point1: Optional[Tuple[int, int]] = None,
        point2: Optional[Tuple[int, int]] = None,
        jitter_px: int = 3,
        restore_cursor: bool = True,
        on_step_callback: Optional[Callable[[str], None]] = None,
        on_complete_callback: Optional[Callable[[], None]] = None,
    ):
        with self._lock:
            if self.is_busy:
                return
            self.is_busy = True

        def worker():
            try:
                jitter_hold = random.uniform(-0.02, 0.04) if use_humanizer else 0.0
                jitter_delay = random.uniform(-0.04, 0.06) if use_humanizer else 0.0
                jpx = jitter_px if use_humanizer else 0

                pt1 = point1
                pt2 = point2 if point2 is not None else point1

                if action_type == "sequence":
                    self.play_beep(1500, 70)
                    step1_desc = f"Click 1 ({primary_button.upper()})"
                    if pt1 and mode != "cursor":
                        step1_desc += f" at ({pt1[0]}, {pt1[1]})"
                    if on_step_callback:
                        on_step_callback(step1_desc)

                    self.click_target(
                        button=primary_button,
                        mode=mode,
                        target_hwnd=target_hwnd,
                        point=pt1,
                        hold_duration=0.06 + max(0, jitter_hold),
                        jitter_px=jpx,
                        restore_cursor=restore_cursor
                    )

                    time.sleep(max(0.1, delay + jitter_delay))

                    step2_desc = f"Click 2 ({secondary_button.upper()})"
                    if pt2 and mode != "cursor":
                        step2_desc += f" at ({pt2[0]}, {pt2[1]})"
                    if on_step_callback:
                        on_step_callback(step2_desc)

                    self.click_target(
                        button=secondary_button,
                        mode=mode,
                        target_hwnd=target_hwnd,
                        point=pt2,
                        hold_duration=0.06,
                        jitter_px=jpx,
                        restore_cursor=restore_cursor
                    )
                    self.play_beep(1100, 50)

                elif action_type == "single":
                    self.play_beep(1400, 70)
                    step_desc = f"Single Click ({primary_button.upper()})"
                    if pt1 and mode != "cursor":
                        step_desc += f" at ({pt1[0]}, {pt1[1]})"
                    if on_step_callback:
                        on_step_callback(step_desc)

                    self.click_target(
                        button=primary_button,
                        mode=mode,
                        target_hwnd=target_hwnd,
                        point=pt1,
                        hold_duration=0.06 + max(0, jitter_hold),
                        jitter_px=jpx,
                        restore_cursor=restore_cursor
                    )

                elif action_type == "double":
                    self.play_beep(1400, 70)
                    step_desc = f"Double Click ({primary_button.upper()})"
                    if pt1 and mode != "cursor":
                        step_desc += f" at ({pt1[0]}, {pt1[1]})"
                    if on_step_callback:
                        on_step_callback(step_desc)

                    self.click_target(
                        button=primary_button,
                        mode=mode,
                        target_hwnd=target_hwnd,
                        point=pt1,
                        hold_duration=0.06,
                        jitter_px=jpx,
                        restore_cursor=restore_cursor
                    )
                    time.sleep(0.08 + max(0, jitter_hold))
                    self.click_target(
                        button=primary_button,
                        mode=mode,
                        target_hwnd=target_hwnd,
                        point=pt1,
                        hold_duration=0.06,
                        jitter_px=jpx,
                        restore_cursor=restore_cursor
                    )

            finally:
                with self._lock:
                    self.is_busy = False
                if on_complete_callback:
                    on_complete_callback()

        threading.Thread(target=worker, daemon=True).start()
