import os
import sys
import time
import datetime
import threading
import ctypes
from tkinter import filedialog
import customtkinter as ctk

from sounddetector import SoundDetector, AudioDeviceManager
from clicker_engine import ClickerEngine
from window_helper import WindowManager, POINT

try:
    import keyboard
except ImportError:
    keyboard = None

user32 = ctypes.windll.user32

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SoundClickerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SoundClicker 2.1 - By Evanonymous")
        self.geometry("680x880")
        self.minsize(620, 750)
        self.configure(fg_color="#0C0D10")

        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Evanonymous.SoundClicker.2.1")
        except Exception:
            pass

        base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
        icon_path = os.path.join(base_dir, "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self.is_running = False
        self.total_triggers = 0
        self.devices = AudioDeviceManager.get_devices()
        self.selected_device_obj = None

        self.open_windows = []
        self.selected_target_hwnd = None
        self.selected_target_pid = None
        self.point1_screen = None
        self.point1_client = None
        self.point2_screen = None
        self.point2_client = None
        self.is_picking_point = False
        self.cue_expanded = True
        self.target_expanded = True
        self.macro_expanded = True
        self.log_visible = True

        self.clicker = ClickerEngine(enable_beep=True)
        self.detector = SoundDetector(
            device_obj=None,
            target_pid=None,
            match_threshold=0.50,
            cooldown=3.0,
            on_level_callback=self._on_level_update,
            on_trigger_callback=self._on_sound_triggered,
            on_status_callback=self._on_detector_status,
        )

        self._build_ui()
        self._init_default_device()
        self._refresh_window_list()
        self._auto_load_existing_sound()
        self._register_hotkey()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._log("SoundClicker 2.1 initialized. Ready.")

    def _build_ui(self):
        self.main_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_fg_color="transparent",
            scrollbar_button_color="#1E222A",
            scrollbar_button_hover_color="#2A2F3A"
        )
        self.main_frame.pack(fill="both", expand=True, padx=18, pady=12)

        if hasattr(self.main_frame, "_scrollbar"):
            try:
                self.main_frame._scrollbar.configure(width=6, corner_radius=3)
            except Exception:
                pass

        header = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header.pack(fill="x", pady=(2, 8))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")

        app_title = ctk.CTkLabel(
            title_box,
            text="SOUNDCLICKER 2.1",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color="#FFFFFF"
        )
        app_title.pack(anchor="w")

        app_sub = ctk.CTkLabel(
            title_box,
            text="SOUND-ACTIVATED AUTO CLICKER • BY EVANONYMOUS",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#9CA3AF"
        )
        app_sub.pack(anchor="w")

        self.hotkey_badge = ctk.CTkLabel(
            header,
            text="HOTKEY: F6",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#181B22",
            border_width=1,
            border_color="#2A2F3A",
            corner_radius=6,
            text_color="#D1D5DB",
            padx=12,
            pady=5
        )
        self.hotkey_badge.pack(side="right", pady=4)

        self.reset_btn = ctk.CTkButton(
            header,
            text="↺ Reset Defaults",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#181B22",
            hover_color="#222730",
            text_color="#9CA3AF",
            height=28,
            width=110,
            corner_radius=6,
            border_width=1,
            border_color="#2A2F3A",
            command=self._reset_default_settings
        )
        self.reset_btn.pack(side="right", padx=(0, 8), pady=4)

        self.telemetry_card = ctk.CTkFrame(
            self.main_frame,
            corner_radius=10,
            fg_color="#14171D",
            border_width=1,
            border_color="#232731"
        )
        self.telemetry_card.pack(fill="x", pady=(0, 6), ipady=3)

        stat_head = ctk.CTkFrame(self.telemetry_card, fg_color="transparent")
        stat_head.pack(fill="x", padx=16, pady=(8, 4))

        self.status_pill = ctk.CTkLabel(
            stat_head,
            text="STANDBY",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#181B22",
            border_width=1,
            border_color="#2A2F3A",
            corner_radius=6,
            text_color="#9CA3AF",
            padx=10,
            pady=3
        )
        self.status_pill.pack(side="left")

        self.isolation_pill = ctk.CTkLabel(
            stat_head,
            text="Audio: Follow Window",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#181B22",
            border_width=1,
            border_color="#2A2F3A",
            corner_radius=6,
            text_color="#9CA3AF",
            padx=10,
            pady=3
        )
        self.isolation_pill.pack(side="left", padx=8)

        self.trigger_pill = ctk.CTkLabel(
            stat_head,
            text="TRIGGERS: 0",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#181B22",
            border_width=1,
            border_color="#2A2F3A",
            corner_radius=6,
            text_color="#E5E7EB",
            padx=10,
            pady=3
        )
        self.trigger_pill.pack(side="right")

        self.meter_bar = ctk.CTkProgressBar(
            self.telemetry_card,
            height=6,
            corner_radius=3,
            fg_color="#181B22",
            progress_color="#4B5563"
        )
        self.meter_bar.pack(fill="x", padx=16, pady=(4, 4))
        self.meter_bar.set(0.0)

        metric_row = ctk.CTkFrame(self.telemetry_card, fg_color="transparent")
        metric_row.pack(fill="x", padx=16, pady=(0, 6))

        self.similarity_val_lbl = ctk.CTkLabel(
            metric_row,
            text="Similarity: 0%",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#9CA3AF"
        )
        self.similarity_val_lbl.pack(side="left")

        self.threshold_val_lbl = ctk.CTkLabel(
            metric_row,
            text="Threshold: 50%",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#6B7280"
        )
        self.threshold_val_lbl.pack(side="right")

        dev_row = ctk.CTkFrame(self.telemetry_card, fg_color="transparent")
        dev_row.pack(fill="x", padx=16, pady=(2, 8))

        ctk.CTkLabel(
            dev_row,
            text="Source Audio:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9CA3AF",
            width=90,
            anchor="w"
        ).pack(side="left")

        self.audio_sources = [
            "Auto: Follow Target Window (Isolated Audio)",
            "Master Loopback: All System Sounds (Default Speaker)"
        ]
        if self.devices:
            for d in self.devices:
                self.audio_sources.append(d["display"])

        self.device_dropdown = ctk.CTkOptionMenu(
            dev_row,
            values=self.audio_sources,
            command=self._on_device_selected,
            fg_color="#181B22",
            button_color="#242832",
            button_hover_color="#2F3543",
            dropdown_fg_color="#14171D",
            dropdown_hover_color="#242832",
            text_color="#E5E7EB",
            height=28,
            corner_radius=6
        )
        self.device_dropdown.set(self.audio_sources[0])
        self.device_dropdown.pack(side="left", fill="x", expand=True)

        # Target Audio Cue Section
        self.cue_card = ctk.CTkFrame(
            self.main_frame,
            corner_radius=10,
            fg_color="#14171D",
            border_width=1,
            border_color="#232731"
        )
        self.cue_card.pack(fill="x", pady=5)

        cue_header = ctk.CTkFrame(self.cue_card, fg_color="transparent")
        cue_header.pack(fill="x", padx=16, pady=(10, 6))

        self.cue_toggle_btn = ctk.CTkButton(
            cue_header,
            text="▼  TARGET AUDIO CUE",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="transparent",
            hover_color="#1A1D24",
            text_color="#E5E7EB",
            anchor="w",
            height=26,
            corner_radius=4,
            command=self._toggle_cue_card
        )
        self.cue_toggle_btn.pack(side="left")

        self.sound_info_badge = ctk.CTkLabel(
            cue_header,
            text="No cue loaded",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#181B22",
            border_width=1,
            border_color="#2A2F3A",
            corner_radius=6,
            text_color="#9CA3AF",
            padx=8,
            pady=2
        )
        self.sound_info_badge.pack(side="right")

        self.cue_body = ctk.CTkFrame(self.cue_card, fg_color="transparent")
        self.cue_body.pack(fill="x", padx=16, pady=(0, 10))

        cue_btn_row = ctk.CTkFrame(self.cue_body, fg_color="transparent")
        cue_btn_row.pack(fill="x", pady=(2, 6))

        self.record_btn = ctk.CTkButton(
            cue_btn_row,
            text="Auto-Capture Cue",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#242832",
            hover_color="#2F3543",
            border_width=1,
            border_color="#3A4150",
            text_color="#FFFFFF",
            height=32,
            corner_radius=6,
            command=self._record_live_sample
        )
        self.record_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.upload_btn = ctk.CTkButton(
            cue_btn_row,
            text="Import Audio",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#181B22",
            hover_color="#222730",
            border_width=1,
            border_color="#2A2F3A",
            text_color="#E5E7EB",
            height=32,
            corner_radius=6,
            command=self._upload_sound_file
        )
        self.upload_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.play_btn = ctk.CTkButton(
            cue_btn_row,
            text="Test Cue",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#181B22",
            hover_color="#222730",
            border_width=1,
            border_color="#2A2F3A",
            text_color="#E5E7EB",
            height=32,
            width=85,
            corner_radius=6,
            command=self._play_template
        )
        self.play_btn.pack(side="left")

        sens_row = ctk.CTkFrame(self.cue_body, fg_color="transparent")
        sens_row.pack(fill="x", pady=(4, 2))

        ctk.CTkLabel(
            sens_row,
            text="Match Sensitivity:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9CA3AF",
            width=120,
            anchor="w"
        ).pack(side="left")

        self.match_slider = ctk.CTkSlider(
            sens_row,
            from_=0.30,
            to=0.90,
            number_of_steps=60,
            height=14,
            fg_color="#181B22",
            progress_color="#4B5563",
            button_color="#E5E7EB",
            button_hover_color="#FFFFFF",
            command=self._on_match_change
        )
        self.match_slider.set(0.50)
        self.match_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.match_display_pill = ctk.CTkLabel(
            sens_row,
            text="50%",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#181B22",
            border_width=1,
            border_color="#2A2F3A",
            corner_radius=5,
            text_color="#E5E7EB",
            width=46,
            pady=2
        )
        self.match_display_pill.pack(side="right")

        # Target Window & Click Position Section
        self.target_card = ctk.CTkFrame(
            self.main_frame,
            corner_radius=10,
            fg_color="#14171D",
            border_width=1,
            border_color="#232731"
        )
        self.target_card.pack(fill="x", pady=5)

        target_header = ctk.CTkFrame(self.target_card, fg_color="transparent")
        target_header.pack(fill="x", padx=16, pady=(10, 6))

        self.target_toggle_btn = ctk.CTkButton(
            target_header,
            text="▼  TARGET WINDOW AND CLICK POSITION",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="transparent",
            hover_color="#1A1D24",
            text_color="#E5E7EB",
            anchor="w",
            height=26,
            corner_radius=4,
            command=self._toggle_target_card
        )
        self.target_toggle_btn.pack(side="left")

        self.target_status_badge = ctk.CTkLabel(
            target_header,
            text="Mode: Background",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#181B22",
            border_width=1,
            border_color="#2A2F3A",
            corner_radius=6,
            text_color="#D1D5DB",
            padx=8,
            pady=2
        )
        self.target_status_badge.pack(side="right")

        self.target_body = ctk.CTkFrame(self.target_card, fg_color="transparent")
        self.target_body.pack(fill="x", padx=16, pady=(0, 10))

        self.delivery_row = ctk.CTkFrame(self.target_body, fg_color="transparent")
        self.delivery_row.pack(fill="x", pady=4)

        ctk.CTkLabel(
            self.delivery_row,
            text="Delivery Method:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9CA3AF",
            width=120,
            anchor="w"
        ).pack(side="left")

        self.delivery_mode_dropdown = ctk.CTkOptionMenu(
            self.delivery_row,
            values=[
                "Background (PostMessage - Alt-Tab Safe)",
                "Foreground (Fixed Coordinate Snap)",
                "Follow Cursor (Current Mouse Position)"
            ],
            command=self._on_delivery_mode_change,
            fg_color="#181B22",
            button_color="#242832",
            button_hover_color="#2F3543",
            dropdown_fg_color="#14171D",
            dropdown_hover_color="#242832",
            text_color="#E5E7EB",
            height=28,
            corner_radius=6
        )
        self.delivery_mode_dropdown.set("Background (PostMessage - Alt-Tab Safe)")
        self.delivery_mode_dropdown.pack(side="left", fill="x", expand=True)

        self.win_row = ctk.CTkFrame(self.target_body, fg_color="transparent")
        self.win_row.pack(fill="x", pady=4)

        ctk.CTkLabel(
            self.win_row,
            text="Target Window:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9CA3AF",
            width=120,
            anchor="w"
        ).pack(side="left")

        self.window_dropdown = ctk.CTkOptionMenu(
            self.win_row,
            values=["Auto-Detect from Click"],
            command=self._on_window_selected,
            fg_color="#181B22",
            button_color="#242832",
            button_hover_color="#2F3543",
            dropdown_fg_color="#14171D",
            dropdown_hover_color="#242832",
            text_color="#E5E7EB",
            height=28,
            corner_radius=6
        )
        self.window_dropdown.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.refresh_win_btn = ctk.CTkButton(
            self.win_row,
            text="Refresh",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            width=75,
            height=28,
            fg_color="#181B22",
            hover_color="#222730",
            border_width=1,
            border_color="#2A2F3A",
            text_color="#E5E7EB",
            corner_radius=6,
            command=self._refresh_window_list
        )
        self.refresh_win_btn.pack(side="right")

        self.p1_row = ctk.CTkFrame(self.target_body, fg_color="transparent")
        self.p1_row.pack(fill="x", pady=(6, 4))

        ctk.CTkLabel(
            self.p1_row,
            text="Point 1 (Primary):",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#E5E7EB",
            width=120,
            anchor="w"
        ).pack(side="left")

        ctk.CTkLabel(self.p1_row, text="X:", font=ctk.CTkFont(size=12), text_color="#9CA3AF").pack(side="left", padx=(0, 4))
        self.p1_x_entry = ctk.CTkEntry(self.p1_row, width=65, height=28, corner_radius=6, fg_color="#0E1015", border_color="#2A2F3A", text_color="#E5E7EB")
        self.p1_x_entry.insert(0, "0")
        self.p1_x_entry.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(self.p1_row, text="Y:", font=ctk.CTkFont(size=12), text_color="#9CA3AF").pack(side="left", padx=(0, 4))
        self.p1_y_entry = ctk.CTkEntry(self.p1_row, width=65, height=28, corner_radius=6, fg_color="#0E1015", border_color="#2A2F3A", text_color="#E5E7EB")
        self.p1_y_entry.insert(0, "0")
        self.p1_y_entry.pack(side="left", padx=(0, 10))

        self.p1_pick_btn = ctk.CTkButton(
            self.p1_row,
            text="Pick Point 1",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#242832",
            hover_color="#2F3543",
            border_width=1,
            border_color="#3A4150",
            text_color="#FFFFFF",
            width=110,
            height=28,
            corner_radius=6,
            command=lambda: self._start_picking_point(1)
        )
        self.p1_pick_btn.pack(side="left", padx=(0, 6))

        self.p1_test_btn = ctk.CTkButton(
            self.p1_row,
            text="Test",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#181B22",
            hover_color="#222730",
            border_width=1,
            border_color="#2A2F3A",
            text_color="#E5E7EB",
            width=58,
            height=28,
            corner_radius=6,
            command=lambda: self._test_point(1)
        )
        self.p1_test_btn.pack(side="left")

        self.p1_badge = ctk.CTkLabel(
            self.p1_row,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#6B7280"
        )
        self.p1_badge.pack(side="right")

        self.p2_container = ctk.CTkFrame(self.target_body, fg_color="transparent")
        self.p2_container.pack(fill="x", pady=(2, 4))

        p2_ctrl_row = ctk.CTkFrame(self.p2_container, fg_color="transparent")
        p2_ctrl_row.pack(fill="x", pady=2)

        self.use_p2_chk = ctk.CTkCheckBox(
            p2_ctrl_row,
            text="Use separate Point 2 for Click 2 (Sequence mode)",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#374151",
            hover_color="#4B5563",
            border_color="#4B5563",
            checkmark_color="#FFFFFF",
            corner_radius=4,
            command=self._on_p2_toggle
        )
        self.use_p2_chk.pack(anchor="w")

        self.p2_inputs_row = ctk.CTkFrame(self.p2_container, fg_color="transparent")

        ctk.CTkLabel(
            self.p2_inputs_row,
            text="Point 2 (Secondary):",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#E5E7EB",
            width=120,
            anchor="w"
        ).pack(side="left")

        ctk.CTkLabel(self.p2_inputs_row, text="X:", font=ctk.CTkFont(size=12), text_color="#9CA3AF").pack(side="left", padx=(0, 4))
        self.p2_x_entry = ctk.CTkEntry(self.p2_inputs_row, width=65, height=28, corner_radius=6, fg_color="#0E1015", border_color="#2A2F3A", text_color="#E5E7EB")
        self.p2_x_entry.insert(0, "0")
        self.p2_x_entry.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(self.p2_inputs_row, text="Y:", font=ctk.CTkFont(size=12), text_color="#9CA3AF").pack(side="left", padx=(0, 4))
        self.p2_y_entry = ctk.CTkEntry(self.p2_inputs_row, width=65, height=28, corner_radius=6, fg_color="#0E1015", border_color="#2A2F3A", text_color="#E5E7EB")
        self.p2_y_entry.insert(0, "0")
        self.p2_y_entry.pack(side="left", padx=(0, 10))

        self.p2_pick_btn = ctk.CTkButton(
            self.p2_inputs_row,
            text="Pick Point 2",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#242832",
            hover_color="#2F3543",
            border_width=1,
            border_color="#3A4150",
            text_color="#FFFFFF",
            width=110,
            height=28,
            corner_radius=6,
            command=lambda: self._start_picking_point(2)
        )
        self.p2_pick_btn.pack(side="left", padx=(0, 6))

        self.p2_test_btn = ctk.CTkButton(
            self.p2_inputs_row,
            text="Test",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#181B22",
            hover_color="#222730",
            border_width=1,
            border_color="#2A2F3A",
            text_color="#E5E7EB",
            width=58,
            height=28,
            corner_radius=6,
            command=lambda: self._test_point(2)
        )
        self.p2_test_btn.pack(side="left")

        self.p2_badge = ctk.CTkLabel(
            self.p2_inputs_row,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#6B7280"
        )
        self.p2_badge.pack(side="right")

        # Action Macro Sequence Section
        self.macro_card = ctk.CTkFrame(
            self.main_frame,
            corner_radius=10,
            fg_color="#14171D",
            border_width=1,
            border_color="#232731"
        )
        self.macro_card.pack(fill="x", pady=5)

        macro_header = ctk.CTkFrame(self.macro_card, fg_color="transparent")
        macro_header.pack(fill="x", padx=16, pady=(10, 6))

        self.macro_toggle_btn = ctk.CTkButton(
            macro_header,
            text="▼  ACTION MACRO SEQUENCE",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="transparent",
            hover_color="#1A1D24",
            text_color="#E5E7EB",
            anchor="w",
            height=26,
            corner_radius=4,
            command=self._toggle_macro_card
        )
        self.macro_toggle_btn.pack(side="left")

        self.macro_body = ctk.CTkFrame(self.macro_card, fg_color="transparent")
        self.macro_body.pack(fill="x", padx=16, pady=(0, 10))

        mode_row = ctk.CTkFrame(self.macro_body, fg_color="transparent")
        mode_row.pack(fill="x", pady=4)

        ctk.CTkLabel(
            mode_row,
            text="Action Mode:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9CA3AF",
            width=120,
            anchor="w"
        ).pack(side="left")

        self.action_mode_dropdown = ctk.CTkOptionMenu(
            mode_row,
            values=[
                "Sequential (Click 1 -> Delay -> Click 2)",
                "Single Click",
                "Double Click"
            ],
            command=self._on_action_type_change,
            fg_color="#181B22",
            button_color="#242832",
            button_hover_color="#2F3543",
            dropdown_fg_color="#14171D",
            dropdown_hover_color="#242832",
            text_color="#E5E7EB",
            height=28,
            corner_radius=6
        )
        self.action_mode_dropdown.set("Sequential (Click 1 -> Delay -> Click 2)")
        self.action_mode_dropdown.pack(side="left", fill="x", expand=True)

        self.btn_config_row = ctk.CTkFrame(self.macro_body, fg_color="transparent")
        self.btn_config_row.pack(fill="x", pady=4)

        ctk.CTkLabel(
            self.btn_config_row,
            text="Click 1:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9CA3AF",
            width=55,
            anchor="w"
        ).pack(side="left")

        self.btn1_dropdown = ctk.CTkOptionMenu(
            self.btn_config_row,
            values=["Right Click", "Left Click"],
            width=110,
            fg_color="#181B22",
            button_color="#242832",
            button_hover_color="#2F3543",
            dropdown_fg_color="#14171D",
            dropdown_hover_color="#242832",
            text_color="#E5E7EB",
            height=28,
            corner_radius=6
        )
        self.btn1_dropdown.set("Right Click")
        self.btn1_dropdown.pack(side="left", padx=(0, 20))

        self.btn2_lbl = ctk.CTkLabel(
            self.btn_config_row,
            text="Click 2:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9CA3AF",
            width=55,
            anchor="w"
        )
        self.btn2_lbl.pack(side="left")

        self.btn2_dropdown = ctk.CTkOptionMenu(
            self.btn_config_row,
            values=["Right Click", "Left Click"],
            width=110,
            fg_color="#181B22",
            button_color="#242832",
            button_hover_color="#2F3543",
            dropdown_fg_color="#14171D",
            dropdown_hover_color="#242832",
            text_color="#E5E7EB",
            height=28,
            corner_radius=6
        )
        self.btn2_dropdown.set("Right Click")
        self.btn2_dropdown.pack(side="left")

        self.delay_row = ctk.CTkFrame(self.macro_body, fg_color="transparent")
        self.delay_row.pack(fill="x", pady=4)

        ctk.CTkLabel(
            self.delay_row,
            text="Action Delay:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9CA3AF",
            width=120,
            anchor="w"
        ).pack(side="left")

        self.delay_slider = ctk.CTkSlider(
            self.delay_row,
            from_=0.1,
            to=3.0,
            number_of_steps=29,
            height=14,
            fg_color="#181B22",
            progress_color="#4B5563",
            button_color="#E5E7EB",
            button_hover_color="#FFFFFF",
            command=self._on_delay_change
        )
        self.delay_slider.set(0.5)
        self.delay_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.delay_display_pill = ctk.CTkLabel(
            self.delay_row,
            text="0.50s",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#181B22",
            border_width=1,
            border_color="#2A2F3A",
            corner_radius=5,
            text_color="#E5E7EB",
            width=46,
            pady=2
        )
        self.delay_display_pill.pack(side="right")

        cool_row = ctk.CTkFrame(self.macro_body, fg_color="transparent")
        cool_row.pack(fill="x", pady=4)

        ctk.CTkLabel(
            cool_row,
            text="Cooldown Window:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9CA3AF",
            width=120,
            anchor="w"
        ).pack(side="left")

        self.cool_slider = ctk.CTkSlider(
            cool_row,
            from_=0.5,
            to=8.0,
            number_of_steps=75,
            height=14,
            fg_color="#181B22",
            progress_color="#4B5563",
            button_color="#E5E7EB",
            button_hover_color="#FFFFFF",
            command=self._on_cooldown_change
        )
        self.cool_slider.set(3.0)
        self.cool_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.cool_display_pill = ctk.CTkLabel(
            cool_row,
            text="3.0s",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#181B22",
            border_width=1,
            border_color="#2A2F3A",
            corner_radius=5,
            text_color="#E5E7EB",
            width=46,
            pady=2
        )
        self.cool_display_pill.pack(side="right")

        opts_frame = ctk.CTkFrame(
            self.macro_body,
            fg_color="#0E1015",
            border_width=1,
            border_color="#232731",
            corner_radius=6
        )
        opts_frame.pack(fill="x", pady=(6, 4))
        opts_frame.grid_columnconfigure(0, weight=1, uniform="chk_col")
        opts_frame.grid_columnconfigure(1, weight=1, uniform="chk_col")

        self.humanizer_chk = ctk.CTkCheckBox(
            opts_frame,
            text="Anti-Detection Timing Jitter (±35ms)",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#374151",
            hover_color="#4B5563",
            border_color="#4B5563",
            checkmark_color="#FFFFFF",
            corner_radius=4
        )
        self.humanizer_chk.select()
        self.humanizer_chk.grid(row=0, column=0, padx=12, pady=(10, 6), sticky="w")

        self.pixel_jitter_chk = ctk.CTkCheckBox(
            opts_frame,
            text="Coordinate Drift (±3px)",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#374151",
            hover_color="#4B5563",
            border_color="#4B5563",
            checkmark_color="#FFFFFF",
            corner_radius=4
        )
        self.pixel_jitter_chk.select()
        self.pixel_jitter_chk.grid(row=0, column=1, padx=12, pady=(10, 6), sticky="w")

        self.beep_chk = ctk.CTkCheckBox(
            opts_frame,
            text="Audio Beep Feedback",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#374151",
            hover_color="#4B5563",
            border_color="#4B5563",
            checkmark_color="#FFFFFF",
            corner_radius=4,
            command=self._on_beep_toggle
        )
        self.beep_chk.select()
        self.beep_chk.grid(row=1, column=0, padx=12, pady=(6, 10), sticky="w")

        self.restore_cursor_chk = ctk.CTkCheckBox(
            opts_frame,
            text="Restore Cursor After Click",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#374151",
            hover_color="#4B5563",
            border_color="#4B5563",
            checkmark_color="#FFFFFF",
            corner_radius=4
        )
        self.restore_cursor_chk.select()
        self.restore_cursor_chk.grid(row=1, column=1, padx=12, pady=(6, 10), sticky="w")

        master_btn_box = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        master_btn_box.pack(fill="x", pady=(6, 6))

        self.toggle_btn = ctk.CTkButton(
            master_btn_box,
            text="START LISTENING (F6)",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            height=44,
            corner_radius=8,
            fg_color="#E5E7EB",
            hover_color="#FFFFFF",
            text_color="#0C0D10",
            command=self.toggle_listening
        )
        self.toggle_btn.pack(fill="x")

        self.console_card = ctk.CTkFrame(
            self.main_frame,
            corner_radius=10,
            fg_color="#14171D",
            border_width=1,
            border_color="#232731"
        )
        self.console_card.pack(fill="both", expand=True, pady=(2, 6))

        console_head = ctk.CTkFrame(self.console_card, fg_color="transparent")
        console_head.pack(fill="x", padx=16, pady=(8, 4))

        ctk.CTkLabel(
            console_head,
            text="ACTIVITY TELEMETRY",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#9CA3AF"
        ).pack(side="left")

        ctk.CTkButton(
            console_head,
            text="Clear",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            width=50,
            height=22,
            fg_color="#181B22",
            hover_color="#222730",
            border_width=1,
            border_color="#2A2F3A",
            text_color="#9CA3AF",
            corner_radius=4,
            command=self._clear_log
        ).pack(side="right")

        self.log_toggle_btn = ctk.CTkButton(
            console_head,
            text="▼ Hide Log",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            width=76,
            height=22,
            fg_color="#181B22",
            hover_color="#222730",
            border_width=1,
            border_color="#2A2F3A",
            text_color="#9CA3AF",
            corner_radius=4,
            command=self._toggle_log_visibility
        )
        self.log_toggle_btn.pack(side="right", padx=(0, 6))

        self.log_box = ctk.CTkTextbox(
            self.console_card,
            height=95,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0E1015",
            border_width=1,
            border_color="#232731",
            text_color="#D1D5DB",
            corner_radius=6,
            scrollbar_button_color="#181B22",
            scrollbar_button_hover_color="#222730"
        )
        self.log_box.pack(fill="both", expand=True, padx=14, pady=(2, 10))

        if hasattr(self.log_box, "_y_scrollbar") and self.log_box._y_scrollbar:
            try:
                self.log_box._y_scrollbar.configure(width=6, corner_radius=3)
            except Exception:
                pass

    def _refresh_window_list(self):
        try:
            self.open_windows = WindowManager.list_windows()
            names = ["Auto-Detect from Click"]
            for w in self.open_windows:
                names.append(w["display"])
            self.window_dropdown.configure(values=names)

            if self.selected_target_hwnd is None:
                for w in self.open_windows:
                    if "Growtopia" in w["title"]:
                        self.selected_target_hwnd = w["hwnd"]
                        self.selected_target_pid = w["pid"]
                        self.window_dropdown.set(w["display"])
                        self._log(f"Auto-selected window: {w['title']} (HWND: {w['hwnd']}, PID: {w['pid']})")
                        if "Follow Target Window" in self.device_dropdown.get():
                            self.detector.update_settings(target_pid=self.selected_target_pid)
                            self.isolation_pill.configure(text=f"PID: {w['pid']} (Isolated)", text_color="#D1D5DB")
                        break
        except Exception as e:
            self._log(f"Error refreshing windows: {e}")

    def _on_window_selected(self, choice: str):
        if "Auto-Detect" in choice:
            self.selected_target_hwnd = None
            self.selected_target_pid = None
            self._log("Window target: Auto-detect from click position.")
            if "Follow Target Window" in self.device_dropdown.get():
                self.detector.update_settings(target_pid=None)
                self.isolation_pill.configure(text="Audio: Follow Window", text_color="#9CA3AF")
            return

        for w in self.open_windows:
            if w["display"] == choice:
                self.selected_target_hwnd = w["hwnd"]
                self.selected_target_pid = w["pid"]
                self._log(f"Target window set: {w['title']} (HWND: {w['hwnd']}, PID: {w['pid']})")
                if "Follow Target Window" in self.device_dropdown.get():
                    self.detector.update_settings(target_pid=self.selected_target_pid)
                    self.isolation_pill.configure(text=f"PID: {w['pid']} (Isolated)", text_color="#D1D5DB")
                    self._log(f"Audio isolated to target process PID {w['pid']} ({w['title']}). YouTube/browser sound ignored.")
                break

    def _set_target_window_by_hwnd(self, hwnd: int, title: str, pid: Optional[int] = None):
        self.selected_target_hwnd = hwnd
        if pid is None:
            pid = WindowManager.get_pid_from_hwnd(hwnd)
        self.selected_target_pid = pid

        if "Follow Target Window" in self.device_dropdown.get() and pid:
            self.detector.update_settings(target_pid=pid)
            self.isolation_pill.configure(text=f"PID: {pid} (Isolated)", text_color="#D1D5DB")
            self._log(f"Audio isolated to {title} (PID: {pid}). YouTube/browser audio ignored.")

        for w in self.open_windows:
            if w["hwnd"] == hwnd:
                self.window_dropdown.set(w["display"])
                return

        new_disp = f"{title} (HWND: {hwnd})"
        self.open_windows.append({"hwnd": hwnd, "title": title, "pid": pid, "display": new_disp})
        values = list(self.window_dropdown.cget("values"))
        if new_disp not in values:
            values.append(new_disp)
            self.window_dropdown.configure(values=values)
        self.window_dropdown.set(new_disp)

    def _on_delivery_mode_change(self, choice: str):
        if "Background" in choice:
            self.target_status_badge.configure(text="Mode: Background", text_color="#D1D5DB")
            self.win_row.pack(fill="x", pady=4, after=self.delivery_row)
            self.p1_row.pack(fill="x", pady=(6, 4), after=self.win_row)
            if self.action_mode_dropdown.get().startswith("Sequential"):
                self.p2_container.pack(fill="x", pady=(2, 4), after=self.p1_row)
            self._log("Delivery mode: Background PostMessage.")
        elif "Foreground" in choice:
            self.target_status_badge.configure(text="Mode: Foreground Snap", text_color="#D1D5DB")
            self.win_row.pack(fill="x", pady=4, after=self.delivery_row)
            self.p1_row.pack(fill="x", pady=(6, 4), after=self.win_row)
            if self.action_mode_dropdown.get().startswith("Sequential"):
                self.p2_container.pack(fill="x", pady=(2, 4), after=self.p1_row)
            self._log("Delivery mode: Foreground Snap.")
        else:
            self.target_status_badge.configure(text="Mode: Follow Cursor", text_color="#9CA3AF")
            self.win_row.pack_forget()
            self.p1_row.pack_forget()
            self.p2_container.pack_forget()
            self._log("Delivery mode: Follow cursor.")

    def _on_p2_toggle(self):
        if self.use_p2_chk.get() == 1:
            self.p2_inputs_row.pack(fill="x", pady=2)
        else:
            self.p2_inputs_row.pack_forget()

    def _start_picking_point(self, point_num: int):
        if self.is_picking_point:
            return
        self.is_picking_point = True

        target_btn = self.p1_pick_btn if point_num == 1 else self.p2_pick_btn
        target_btn.configure(text="Click target on screen...", fg_color="#374151")
        self._log(f"Move mouse to Point {point_num} on screen/game, then click LEFT. (Press ESC to cancel)")

        def worker():
            WindowManager.ensure_desktop()

            while user32.GetAsyncKeyState(0x01) & 0x8000:
                time.sleep(0.05)
                if not self.is_picking_point:
                    return

            captured = False
            while self.is_picking_point and not captured:
                if user32.GetAsyncKeyState(0x1B) & 0x8000:
                    self.after(0, lambda: self._log("Point capture cancelled."))
                    break

                if user32.GetAsyncKeyState(0x01) & 0x8000:
                    pt = POINT()
                    user32.GetCursorPos(ctypes.byref(pt))
                    screen_x, screen_y = pt.x, pt.y

                    hwnd, title, pid = WindowManager.get_window_at_point(screen_x, screen_y)
                    target_hwnd = hwnd if hwnd else self.selected_target_hwnd
                    if target_hwnd:
                        cx, cy = WindowManager.screen_to_client(target_hwnd, screen_x, screen_y)
                    else:
                        cx, cy = screen_x, screen_y

                    self.clicker.play_beep(1800, 80)
                    self.after(0, self._on_point_captured, point_num, screen_x, screen_y, cx, cy, hwnd, title, pid)
                    captured = True
                    break

                time.sleep(0.01)

            self.is_picking_point = False
            self.after(0, lambda: target_btn.configure(text=f"Pick Point {point_num}", fg_color="#242832"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_point_captured(self, point_num: int, sx: int, sy: int, cx: int, cy: int, hwnd: Optional[int], title: str, pid: Optional[int]):
        is_bg = "Background" in self.delivery_mode_dropdown.get()
        use_x = cx if is_bg else sx
        use_y = cy if is_bg else sy

        if point_num == 1:
            self.point1_screen = (sx, sy)
            self.point1_client = (cx, cy)
            self.p1_x_entry.delete(0, "end")
            self.p1_x_entry.insert(0, str(use_x))
            self.p1_y_entry.delete(0, "end")
            self.p1_y_entry.insert(0, str(use_y))
            self.p1_badge.configure(text=f"Screen: {sx},{sy} | Client: {cx},{cy}")
        else:
            self.point2_screen = (sx, sy)
            self.point2_client = (cx, cy)
            self.p2_x_entry.delete(0, "end")
            self.p2_x_entry.insert(0, str(use_x))
            self.p2_y_entry.delete(0, "end")
            self.p2_y_entry.insert(0, str(use_y))
            self.p2_badge.configure(text=f"Screen: {sx},{sy} | Client: {cx},{cy}")

        if hwnd and title:
            self._set_target_window_by_hwnd(hwnd, title, pid)

        self._log(f"Point {point_num} saved: Screen=({sx}, {sy}), Client=({cx}, {cy}) on '{title}'")

    def _get_entry_point(self, point_num: int) -> Optional[tuple]:
        try:
            if point_num == 1:
                x = int(self.p1_x_entry.get().strip())
                y = int(self.p1_y_entry.get().strip())
            else:
                x = int(self.p2_x_entry.get().strip())
                y = int(self.p2_y_entry.get().strip())
            return (x, y)
        except Exception:
            return None

    def _test_point(self, point_num: int):
        pt = self._get_entry_point(point_num)
        if pt is None:
            self._log(f"Point {point_num} has invalid coordinates.")
            return

        delivery_choice = self.delivery_mode_dropdown.get()
        btn = "right" if (point_num == 1 and "Right" in self.btn1_dropdown.get()) else "left"

        if "Background" in delivery_choice:
            hwnd = self.selected_target_hwnd
            if not hwnd or not WindowManager.is_window_valid(hwnd):
                self._log("Please select a target window for background test.")
                return
            self.clicker.play_beep(1600, 70)
            self.clicker.post_background_click(
                hwnd=hwnd,
                client_x=pt[0],
                client_y=pt[1],
                button=btn,
                hold_duration=0.06
            )
            self._log(f"Background click sent to HWND {hwnd} at Client ({pt[0]}, {pt[1]})")
        else:
            self.clicker.play_beep(1600, 70)
            old_pt = POINT()
            user32.GetCursorPos(ctypes.byref(old_pt))
            user32.SetCursorPos(pt[0], pt[1])
            self._log(f"Cursor moved to Screen ({pt[0]}, {pt[1]}) for 1.2s...")

            def restore():
                user32.SetCursorPos(old_pt.x, old_pt.y)
                self._log("Cursor restored.")

            self.after(1200, restore)

    def _auto_load_existing_sound(self):
        base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
        for filename in ["recorded_sound.wav", "recorded_splash.wav", "splash_sample.wav"]:
            path = os.path.join(base_dir, filename)
            if os.path.exists(path):
                success, msg = self.detector.load_sound_file(path)
                if success:
                    self.sound_info_badge.configure(
                        text=f"Loaded: {msg}",
                        fg_color="#181B22",
                        text_color="#D1D5DB"
                    )
                    self._log(f"Auto-loaded sound cue: {msg}")
                    return

    def _upload_sound_file(self):
        filetypes = [
            ("Audio Files", "*.wav *.mp3 *.ogg *.flac"),
            ("WAV Files", "*.wav"),
            ("All Files", "*.*")
        ]
        path = filedialog.askopenfilename(title="Select Target Audio Cue", filetypes=filetypes)
        if not path:
            return

        success, msg = self.detector.load_sound_file(path)
        if success:
            self.sound_info_badge.configure(
                text=f"Loaded: {msg}",
                fg_color="#181B22",
                text_color="#D1D5DB"
            )
            self._log(f"Target sound cue imported: {msg}")
            self.detector.play_template()
        else:
            self.sound_info_badge.configure(
                text="Import Error",
                fg_color="#22242B",
                text_color="#9CA3AF"
            )
            self._log(f"Load error: {msg}")

    def _record_live_sample(self):
        if "Follow Target Window" in self.device_dropdown.get() and self.selected_target_pid:
            self.detector.update_settings(target_pid=self.selected_target_pid)
            self._log(f"Listening for audio cue from target window PID {self.selected_target_pid} (trigger sound now)...")
        else:
            self._log("Listening for audio cue (trigger sound now)...")

        self.record_btn.configure(text="Capturing...", fg_color="#374151")
        self.status_pill.configure(
            text="CAPTURING AUDIO",
            fg_color="#282E3B",
            text_color="#FFFFFF"
        )
        self.update()

        def worker():
            def status_cb(txt):
                self.after(0, lambda: self._log(txt))

            success, msg = self.detector.record_live_smart(
                timeout=12.0,
                trigger_threshold=0.020,
                status_callback=status_cb
            )

            def update_ui():
                self.record_btn.configure(text="Auto-Capture Cue", fg_color="#242832")
                self.status_pill.configure(
                    text="STANDBY" if not self.is_running else "ACTIVE LISTENING",
                    fg_color="#181B22" if not self.is_running else "#282E3B",
                    text_color="#9CA3AF" if not self.is_running else "#FFFFFF"
                )
                if success:
                    self.sound_info_badge.configure(
                        text=f"Captured: {msg}",
                        fg_color="#181B22",
                        text_color="#D1D5DB"
                    )
                    self._log(f"Audio cue captured: {msg}")
                else:
                    self.sound_info_badge.configure(
                        text="Capture Failed",
                        fg_color="#22242B",
                        text_color="#9CA3AF"
                    )
                    self._log(f"Capture failed: {msg}")

            self.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def _play_template(self):
        if self.detector.template_norm is None:
            self._log("No target sound cue loaded yet.")
            return
        self._log("Auditioning loaded cue...")
        self.detector.play_template()

    def _on_match_change(self, value):
        val = round(float(value), 2)
        pct = int(val * 100)
        self.match_display_pill.configure(text=f"{pct}%")
        self.detector.update_settings(match_threshold=val)
        self.threshold_val_lbl.configure(text=f"Threshold: {pct}%")

    def _on_action_type_change(self, choice):
        if "Single" in choice or "Double" in choice:
            self.btn2_lbl.pack_forget()
            self.btn2_dropdown.pack_forget()
            self.delay_row.pack_forget()
            self.p2_container.pack_forget()
        else:
            self.btn2_lbl.pack(side="left")
            self.btn2_dropdown.pack(side="left")
            self.delay_row.pack(fill="x", pady=4, after=self.btn_config_row)
            if "Cursor" not in self.delivery_mode_dropdown.get():
                self.p2_container.pack(fill="x", pady=(2, 4), after=self.p1_row)

    def _on_delay_change(self, value):
        val = round(float(value), 2)
        self.delay_display_pill.configure(text=f"{val:.2f}s")

    def _on_cooldown_change(self, value):
        val = round(float(value), 1)
        self.cool_display_pill.configure(text=f"{val:.1f}s")
        self.detector.update_settings(cooldown=val)

    def _on_beep_toggle(self):
        self.clicker.enable_beep = bool(self.beep_chk.get() == 1)

    def _init_default_device(self):
        default_lb = AudioDeviceManager.get_default_loopback()
        if default_lb:
            self.selected_device_obj = default_lb["obj"]
        elif self.devices:
            self.selected_device_obj = self.devices[0]["obj"]

        if "Follow Target Window" in self.device_dropdown.get():
            if self.selected_target_pid:
                self.detector.update_settings(target_pid=self.selected_target_pid, device_obj=None)
                self.isolation_pill.configure(text=f"PID: {self.selected_target_pid} (Isolated)", text_color="#D1D5DB")
            else:
                self.detector.update_settings(target_pid=None, device_obj=self.selected_device_obj)
                self.isolation_pill.configure(text="Audio: Follow Window", text_color="#9CA3AF")
        elif "Master Loopback" in self.device_dropdown.get():
            self.detector.update_settings(target_pid=None, device_obj=self.selected_device_obj)
            self.isolation_pill.configure(text="Audio: Master Loopback", text_color="#9CA3AF")

    def _on_device_selected(self, choice):
        if "Follow Target Window" in choice:
            if self.selected_target_pid:
                self.detector.update_settings(target_pid=self.selected_target_pid, device_obj=None)
                self.isolation_pill.configure(text=f"PID: {self.selected_target_pid} (Isolated)", text_color="#D1D5DB")
                self._log(f"Audio source: Isolated to target window process (PID: {self.selected_target_pid}).")
            else:
                self._init_default_device()
                self.detector.update_settings(target_pid=None)
                self.isolation_pill.configure(text="Audio: Follow Window", text_color="#9CA3AF")
                self._log("Audio source: Auto (Will isolate to target window once selected/picked).")
            return
        elif "Master Loopback" in choice:
            self._init_default_device()
            self.detector.update_settings(target_pid=None, device_obj=self.selected_device_obj)
            self.isolation_pill.configure(text="Audio: Master Loopback", text_color="#9CA3AF")
            self._log("Audio source: Master Loopback (All system sounds captured).")
            return

        for d in self.devices:
            if d["display"] == choice:
                self.selected_device_obj = d["obj"]
                self.detector.update_settings(device_obj=self.selected_device_obj, target_pid=None)
                self.isolation_pill.configure(text="Audio: Manual Device", text_color="#9CA3AF")
                self._log(f"Audio source changed: {choice}")
                break

    def _register_hotkey(self):
        if keyboard is None:
            return
        try:
            keyboard.add_hotkey("F6", lambda: self.after(0, self.toggle_listening))
        except Exception as e:
            self._log(f"Failed to bind F6 hotkey: {e}")

    def toggle_listening(self):
        if not self.is_running:
            if self.detector.template_norm is None:
                self._log("Notice: Record or import a target sound cue before starting.")
                return

            delivery_choice = self.delivery_mode_dropdown.get()
            if "Background" in delivery_choice:
                if not self.selected_target_hwnd or not WindowManager.is_window_valid(self.selected_target_hwnd):
                    self._log("Warning: Target window not selected or invalid for Background Mode.")

            if "Follow Target Window" in self.device_dropdown.get():
                if self.selected_target_pid:
                    self.detector.update_settings(target_pid=self.selected_target_pid, device_obj=None)
                    self._log(f"Listening with isolated audio from PID {self.selected_target_pid}. Other apps (YouTube/browser) excluded.")
                else:
                    self.detector.update_settings(target_pid=None)
                    self._log("Notice: Target window not selected yet. Capturing loopback until window is chosen.")

            self.is_running = True
            self.clicker.play_beep(1350, 100)
            self.toggle_btn.configure(
                text="STOP LISTENING (F6)",
                fg_color="#242832",
                hover_color="#2F3543",
                text_color="#FFFFFF"
            )
            self.status_pill.configure(
                text="ACTIVE LISTENING",
                fg_color="#282E3B",
                text_color="#FFFFFF"
            )
            self.detector.start()
            self._log("Listening active.")
        else:
            self.is_running = False
            self.clicker.play_beep(750, 100)
            self.toggle_btn.configure(
                text="START LISTENING (F6)",
                fg_color="#E5E7EB",
                hover_color="#FFFFFF",
                text_color="#0C0D10"
            )
            self.status_pill.configure(
                text="STANDBY",
                fg_color="#181B22",
                text_color="#9CA3AF"
            )
            self.meter_bar.set(0.0)
            self.similarity_val_lbl.configure(text="Similarity: 0%")
            self.detector.stop()
            self._log("Listening paused.")

    def _toggle_cue_card(self):
        if self.cue_expanded:
            self.cue_body.pack_forget()
            self.cue_toggle_btn.configure(text="▶  TARGET AUDIO CUE")
            self.cue_expanded = False
        else:
            self.cue_body.pack(fill="x", padx=16, pady=(0, 10))
            self.cue_toggle_btn.configure(text="▼  TARGET AUDIO CUE")
            self.cue_expanded = True

    def _toggle_target_card(self):
        if self.target_expanded:
            self.target_body.pack_forget()
            self.target_toggle_btn.configure(text="▶  TARGET WINDOW AND CLICK POSITION")
            self.target_expanded = False
        else:
            self.target_body.pack(fill="x", padx=16, pady=(0, 10))
            self.target_toggle_btn.configure(text="▼  TARGET WINDOW AND CLICK POSITION")
            self.target_expanded = True

    def _toggle_macro_card(self):
        if self.macro_expanded:
            self.macro_body.pack_forget()
            self.macro_toggle_btn.configure(text="▶  ACTION MACRO SEQUENCE")
            self.macro_expanded = False
        else:
            self.macro_body.pack(fill="x", padx=16, pady=(0, 10))
            self.macro_toggle_btn.configure(text="▼  ACTION MACRO SEQUENCE")
            self.macro_expanded = True

    def _toggle_log_visibility(self):
        if self.log_visible:
            self.log_box.pack_forget()
            self.log_toggle_btn.configure(text="▶ Show Log")
            self.log_visible = False
        else:
            self.log_box.pack(fill="both", expand=True, padx=14, pady=(2, 10))
            self.log_toggle_btn.configure(text="▼ Hide Log")
            self.log_visible = True

    def _reset_default_settings(self):
        self.match_slider.set(0.50)
        self._on_match_change(0.50)

        self.delay_slider.set(0.50)
        self._on_delay_change(0.50)

        self.cool_slider.set(3.0)
        self._on_cooldown_change(3.0)

        self.delivery_mode_dropdown.set("Background (PostMessage - Alt-Tab Safe)")
        self._on_delivery_mode_change("Background (PostMessage - Alt-Tab Safe)")

        self.action_mode_dropdown.set("Sequential (Click 1 -> Delay -> Click 2)")
        self._on_action_type_change("Sequential (Click 1 -> Delay -> Click 2)")

        self.btn1_dropdown.set("Right Click")
        self.btn2_dropdown.set("Right Click")

        self.device_dropdown.set(self.audio_sources[0])
        self._on_device_selected(self.audio_sources[0])

        self.humanizer_chk.select()
        self.pixel_jitter_chk.select()
        self.beep_chk.select()
        self.clicker.enable_beep = True
        self.restore_cursor_chk.select()

        self.use_p2_chk.deselect()
        self._on_p2_toggle()

        self.point1_screen = None
        self.point1_client = None
        self.p1_x_entry.delete(0, "end")
        self.p1_x_entry.insert(0, "0")
        self.p1_y_entry.delete(0, "end")
        self.p1_y_entry.insert(0, "0")
        self.p1_badge.configure(text="")

        self.point2_screen = None
        self.point2_client = None
        self.p2_x_entry.delete(0, "end")
        self.p2_x_entry.insert(0, "0")
        self.p2_y_entry.delete(0, "end")
        self.p2_y_entry.insert(0, "0")
        self.p2_badge.configure(text="")

        self.window_dropdown.set("Auto-Detect from Click")
        self.selected_target_hwnd = None
        self.selected_target_pid = None
        self.detector.update_settings(match_threshold=0.50, cooldown=3.0, target_pid=None)
        self.isolation_pill.configure(text="Audio: Follow Window", text_color="#9CA3AF")

        if not self.cue_expanded:
            self._toggle_cue_card()
        if not self.target_expanded:
            self._toggle_target_card()
        if not self.macro_expanded:
            self._toggle_macro_card()
        if not self.log_visible:
            self._toggle_log_visibility()

        self._log("[Settings] All parameters restored to default values.")

    def _on_level_update(self, rms: float, match_score: float):
        self.after(0, self._update_meter_gui, rms, match_score)

    def _update_meter_gui(self, rms: float, match_score: float):
        match_pct = int(match_score * 100)
        self.similarity_val_lbl.configure(text=f"Similarity: {match_pct}%")

        meter_val = min(1.0, max(0.0, match_score))
        self.meter_bar.set(meter_val)

        if match_score >= self.detector.match_threshold:
            self.meter_bar.configure(progress_color="#FFFFFF")
        elif match_score >= self.detector.match_threshold * 0.7:
            self.meter_bar.configure(progress_color="#9CA3AF")
        else:
            self.meter_bar.configure(progress_color="#4B5563")

    def _on_sound_triggered(self, match_score: float):
        self.after(0, self._handle_sound_triggered, match_score)

    def _handle_sound_triggered(self, match_score: float):
        if not self.is_running:
            return

        self.total_triggers += 1
        self.trigger_pill.configure(text=f"TRIGGERS: {self.total_triggers}")
        self._log(f"Sound matched: {int(match_score * 100)}%")

        self.status_pill.configure(
            text="TRIGGERED",
            fg_color="#374151",
            text_color="#FFFFFF"
        )

        mode_choice = self.action_mode_dropdown.get()
        if "Single" in mode_choice:
            action_type = "single"
        elif "Double" in mode_choice:
            action_type = "double"
        else:
            action_type = "sequence"

        btn1 = "right" if "Right" in self.btn1_dropdown.get() else "left"
        btn2 = "right" if "Right" in self.btn2_dropdown.get() else "left"
        delay = float(self.delay_slider.get())
        cooldown = float(self.cool_slider.get())
        use_humanizer = bool(self.humanizer_chk.get() == 1)

        delivery_choice = self.delivery_mode_dropdown.get()
        if "Background" in delivery_choice:
            click_mode = "background"
        elif "Foreground" in delivery_choice:
            click_mode = "fixed"
        else:
            click_mode = "cursor"

        target_hwnd = self.selected_target_hwnd if click_mode == "background" else None
        pt1 = self._get_entry_point(1) if click_mode != "cursor" else None
        pt2 = self._get_entry_point(2) if (click_mode != "cursor" and self.use_p2_chk.get() == 1) else pt1

        use_pixel_jitter = bool(self.pixel_jitter_chk.get() == 1)
        pixel_jitter_radius = 3 if use_pixel_jitter else 0
        restore_cursor = bool(self.restore_cursor_chk.get() == 1)

        self.detector.trigger_external_cooldown(delay + 2.0)

        def step_cb(msg: str):
            self.after(0, self._log, msg)

        def complete_cb():
            self.detector.clear_buffer()
            self.detector.trigger_external_cooldown(cooldown)
            self.after(0, self._on_action_finished, cooldown)

        self.clicker.execute_action(
            action_type=action_type,
            primary_button=btn1,
            secondary_button=btn2,
            delay=delay,
            use_humanizer=use_humanizer,
            mode=click_mode,
            target_hwnd=target_hwnd,
            point1=pt1,
            point2=pt2,
            jitter_px=pixel_jitter_radius,
            restore_cursor=restore_cursor,
            on_step_callback=step_cb,
            on_complete_callback=complete_cb
        )

    def _on_action_finished(self, cooldown: float):
        if self.is_running:
            self.status_pill.configure(
                text=f"COOLDOWN ({cooldown:.1f}s)",
                fg_color="#1F242D",
                text_color="#9CA3AF"
            )

            def resume():
                if self.is_running:
                    self.detector.clear_buffer()
                    self.status_pill.configure(
                        text="ACTIVE LISTENING",
                        fg_color="#282E3B",
                        text_color="#FFFFFF"
                    )
                    self._log("Cooldown cleared. Ready.")

            self.after(int(cooldown * 1000), resume)

    def _on_detector_status(self, status: str):
        if status == "ERROR_NO_DEVICE":
            self.after(0, self._log, "Device error: Selected audio device unavailable.")

    def _log(self, message: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {message}\n"
        self.log_box.insert("end", entry)
        self.log_box.see("end")

    def _clear_log(self):
        self.log_box.delete("1.0", "end")

    def _on_close(self):
        self.is_running = False
        self.detector.stop()
        if keyboard is not None:
            try:
                keyboard.unhook_all_hotkeys()
            except Exception:
                pass
        self.destroy()

if __name__ == "__main__":
    app = SoundClickerApp()
    app.mainloop()
