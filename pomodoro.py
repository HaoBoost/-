import tkinter as tk
from tkinter import ttk
import subprocess
import sys
import json
import os


import math

# ====================================================================== #
#  Pill-shaped rounded button (Canvas-based, polygon-drawn smooth edges)
# ====================================================================== #
class PillButton(tk.Canvas):
    def __init__(self, parent, text, command, bg_color, fg_color,
                 width=110, height=40, font_size=11, **kw):
        parent_bg = parent.cget("bg") if parent.cget("bg") != "SystemButtonFace" else "#FFFFFF"
        super().__init__(parent, width=width, height=height,
                         bg=parent_bg, highlightthickness=0, borderwidth=0, **kw)
        self._bg = bg_color
        self._fg = fg_color
        self._command = command
        self._text = text
        self._width = width
        self._height = height
        self._font_size = font_size
        self._disabled = False
        self._hovered = False
        self._draw()

        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _rounded_rect_coords(self, w, h, r, steps=36):
        """Generate smooth polygon points for a pill (rounded rect with
        semicircular ends)."""
        pts = []
        # right semi-circle (top to bottom)
        cx = w - r
        cy = h / 2
        for i in range(steps + 1):
            angle = math.pi / 2 - math.pi * i / steps  # +90 to -90 deg
            pts.append((cx + r * math.cos(angle), cy - r * math.sin(angle)))
        # left semi-circle (bottom to top)
        cx = r
        for i in range(steps + 1):
            angle = -math.pi / 2 - math.pi * i / steps  # -90 to -270 deg
            pts.append((cx + r * math.cos(angle), cy - r * math.sin(angle)))
        return pts

    def _draw(self):
        self.delete("all")
        w, h = float(self._width), float(self._height)
        r = h / 2 - 0.5  # slight inset to avoid clipping

        if self._disabled:
            color = self._mute(self._bg)
            text_color = "#C4BCB5"
        elif self._hovered:
            color = self._brighten(self._bg)
            text_color = self._fg
        else:
            color = self._bg
            text_color = self._fg

        # pill body — smooth polygon
        pts = self._rounded_rect_coords(w, h, r)
        self.create_polygon(pts, fill=color, outline=color, smooth=False,
                            joinstyle=tk.ROUND)

        # text
        self.create_text(w // 2, h // 2, text=self._text,
                         fill=text_color, anchor="center",
                         font=("Microsoft YaHei UI", self._font_size, "bold"))

    def _on_click(self, event):
        if not self._disabled:
            self._command()

    def _on_enter(self, event):
        if not self._disabled:
            self._hovered = True
            self._draw()

    def _on_leave(self, event):
        self._hovered = False
        self._draw()

    def set_disabled(self, flag):
        self._disabled = flag
        self._hovered = False
        self._draw()

    def is_disabled(self):
        return self._disabled

    @staticmethod
    def _mute(hex_color):
        rgb = hex_color.lstrip("#")
        r, g, b = int(rgb[0:2], 16), int(rgb[2:4], 16), int(rgb[4:6], 16)
        avg = (r + g + b) // 3
        r = (r + avg * 3) // 4
        g = (g + avg * 3) // 4
        b = (b + avg * 3) // 4
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _brighten(hex_color):
        rgb = hex_color.lstrip("#")
        r, g, b = int(rgb[0:2], 16), int(rgb[2:4], 16), int(rgb[4:6], 16)
        r = min(255, r + 18)
        g = min(255, g + 18)
        b = min(255, b + 18)
        return f"#{r:02x}{g:02x}{b:02x}"


# ====================================================================== #
#  Pomodoro App
# ====================================================================== #
class PomodoroApp:
    DEFAULT_WORK = 25
    DEFAULT_SHORT = 5
    DEFAULT_LONG = 15
    DEFAULT_BEFORE_LONG = 4

    # Warm earthy palette (from screenshot)
    C = {
        "bg":        "#F8F1EE",
        "card":      "#FFFDFB",
        "text":      "#766C65",
        "sub":       "#B0A89F",
        "work":      "#C75B49",
        "short":     "#A3AE9A",
        "long":      "#9FA6B8",
        "btn_start": "#C75B49",
        "btn_pause": "#E8DED5",
        "btn_reset": "#E7DEDB",
        "btn_skip":  "#DDD4CE",
        "trough":    "#EAE4E0",
    }

    MODE_LABELS = {
        "work": "专注中",
        "short_break": "小憩一下",
        "long_break": "放松时刻",
    }
    MODE_ICONS = {
        "work": "\U0001F4AA",
        "short_break": "\U0001F338",
        "long_break": "\U0001F3B5",
    }
    MODE_MSGS = {
        "work": "加油！你可以的 ~",
        "short_break": "休息一下，喝口水吧 ~",
        "long_break": "辛苦了，好好放松吧 ~",
    }

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("  番茄钟")
        self.root.configure(bg=self.C["bg"])
        self.root.resizable(False, False)

        window_width = 420
        window_height = 540
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - window_width) // 2
        y = (screen_h - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # --- config file ---
        self._config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "pomodoro_config.json"
        )

        # --- custom durations: load saved or use defaults ---
        saved = self._load_config()
        self.work_min = saved.get("work", self.DEFAULT_WORK)
        self.short_min = saved.get("short", self.DEFAULT_SHORT)
        self.long_min = saved.get("long", self.DEFAULT_LONG)
        self.before_long = saved.get("before", self.DEFAULT_BEFORE_LONG)

        # --- state ---
        self.remaining = self._sec(self.work_min)
        self.running = False
        self.mode = "work"
        self.pomodoro_count = 0
        self.always_on_top = tk.BooleanVar(value=False)
        self._after_id = None

        self._build_ui()
        self._update_display()

    def _sec(self, minutes):
        return minutes * 60

    def _load_config(self):
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_config(self):
        data = {
            "work": self.work_min,
            "short": self.short_min,
            "long": self.long_min,
            "before": self.before_long,
        }
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ================================================================== #
    #  UI
    # ================================================================== #
    def _build_ui(self):
        C = self.C

        # -- title bar --
        title_bar = tk.Frame(self.root, bg=C["card"], height=36)
        title_bar.pack(fill=tk.X)
        title_bar.pack_propagate(False)

        tk.Label(
            title_bar, text="  番茄钟", font=("Microsoft YaHei UI", 11, "bold"),
            bg=C["card"], fg=C["text"]
        ).pack(side=tk.LEFT, pady=4)

        settings_lbl = tk.Label(
            title_bar, text="⚙ 设置 ", font=("Microsoft YaHei UI", 10),
            bg=C["card"], fg=C["sub"], cursor="hand2"
        )
        settings_lbl.pack(side=tk.RIGHT, pady=4, padx=4)
        settings_lbl.bind("<Button-1>", lambda e: self._open_settings())

        self._pin_lbl = tk.Label(
            title_bar, text="  📌  ", font=("Microsoft YaHei UI", 10),
            bg=C["card"], fg=C["sub"], cursor="hand2"
        )
        self._pin_lbl.pack(side=tk.RIGHT, pady=4)
        self._pin_lbl.bind("<Button-1>", lambda e: self._toggle_top())
        self._update_pin_label()

        # -- main card --
        outer = tk.Frame(self.root, bg=C["bg"], padx=20, pady=12)
        outer.pack(fill=tk.BOTH, expand=True)

        card = tk.Frame(outer, bg=C["card"], padx=24, pady=20)
        card.pack(fill=tk.BOTH, expand=True)

        # mode label
        self.mode_label = tk.Label(
            card, text="", font=("Microsoft YaHei UI", 22, "bold"),
            bg=C["card"], fg=C["text"]
        )
        self.mode_label.pack(pady=(4, 2))

        # encouragement
        self.msg_label = tk.Label(
            card, text="", font=("Microsoft YaHei UI", 10),
            bg=C["card"], fg=C["sub"]
        )
        self.msg_label.pack(pady=(0, 12))

        # timer
        self.timer_label = tk.Label(
            card, text="", font=("Consolas", 64, "bold"),
            bg=C["card"], fg=C["work"]
        )
        self.timer_label.pack(pady=(0, 12))

        # progress bar
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TProgressbar", troughcolor=C["trough"],
            background=C["work"], thickness=8, borderwidth=0,
        )
        self.progress = ttk.Progressbar(
            card, style="TProgressbar", length=330, mode="determinate"
        )
        self.progress.pack(pady=(0, 14))

        # pomodoro dots
        dots_frame = tk.Frame(card, bg=C["card"])
        dots_frame.pack(pady=(0, 16))
        self.dots_label = tk.Label(
            dots_frame, text="", font=("Microsoft YaHei UI", 11),
            bg=C["card"], fg=C["sub"]
        )
        self.dots_label.pack()

        # -- pill buttons --
        btn_area = tk.Frame(card, bg=C["card"])
        btn_area.pack()

        row1 = tk.Frame(btn_area, bg=C["card"])
        row1.pack(pady=(0, 8))
        row2 = tk.Frame(btn_area, bg=C["card"])
        row2.pack()

        self.start_btn = PillButton(row1, "开始", self.start, C["btn_start"], "#FFFDFB")
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.pause_btn = PillButton(row1, "暂停", self.pause, C["btn_pause"], C["text"])
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        self.pause_btn.set_disabled(True)

        self.reset_btn = PillButton(row2, "重置", self.reset, C["btn_reset"], C["text"])
        self.reset_btn.pack(side=tk.LEFT, padx=5)

        self.skip_btn = PillButton(row2, "跳过", self.skip, C["btn_skip"], C["text"])
        self.skip_btn.pack(side=tk.LEFT, padx=5)

    def _update_pin_label(self):
        if self.always_on_top.get():
            self._pin_lbl.config(fg=self.C["work"])
        else:
            self._pin_lbl.config(fg=self.C["sub"])

    # ================================================================== #
    #  Settings dialog
    # ================================================================== #
    def _reset_settings(self, vars_):
        vars_["work"].set(self.DEFAULT_WORK)
        vars_["short"].set(self.DEFAULT_SHORT)
        vars_["long"].set(self.DEFAULT_LONG)
        vars_["before"].set(self.DEFAULT_BEFORE_LONG)

    def _open_settings(self):
        C = self.C
        dlg = tk.Toplevel(self.root)
        dlg.title("设置")
        dlg.configure(bg=C["bg"])
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        w, h = 330, 300
        px = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{px}+{py}")

        frm = tk.Frame(dlg, bg=C["card"], padx=24, pady=20)
        frm.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        tk.Label(frm, text="自定义时长（分钟）", font=("Microsoft YaHei UI", 13, "bold"),
                 bg=C["card"], fg=C["text"]).pack(pady=(0, 16))

        vars_ = {}
        rows = [
            ("  专注", "work", self.work_min, 1, 120),
            ("  短休息", "short", self.short_min, 1, 60),
            ("  长休息", "long", self.long_min, 1, 60),
            ("  长休息间隔（个番茄）", "before", self.before_long, 1, 10),
        ]
        for label, key, val, vmin, vmax in rows:
            row = tk.Frame(frm, bg=C["card"])
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=label, font=("Microsoft YaHei UI", 10),
                     bg=C["card"], fg=C["text"], width=18, anchor="w").pack(side=tk.LEFT)
            var = tk.IntVar(value=val)
            vars_[key] = var
            sb = tk.Spinbox(
                row, textvariable=var, from_=vmin, to=vmax, width=5,
                font=("Consolas", 11), justify="center",
                bg="white", fg=C["text"], relief=tk.FLAT,
                buttonbackground=C["btn_reset"],
            )
            sb.pack(side=tk.RIGHT, padx=4)

        def _do_save():
            self.work_min = vars_["work"].get()
            self.short_min = vars_["short"].get()
            self.long_min = vars_["long"].get()
            self.before_long = vars_["before"].get()
            self.running = False
            if self._after_id:
                self.root.after_cancel(self._after_id)
                self._after_id = None
            self.pomodoro_count = 0
            self.mode = "work"
            self.remaining = self._sec(self.work_min)
            self.start_btn.set_disabled(False)
            self.pause_btn.set_disabled(True)
            self._save_config()
            self._update_display()
            dlg.destroy()

        btn_row = tk.Frame(frm, bg=C["card"])
        btn_row.pack(pady=(16, 0))

        cancel_btn = PillButton(btn_row, "取消", dlg.destroy,
                                C["btn_reset"], C["text"], width=64, height=36)
        cancel_btn.pack(side=tk.LEFT, padx=5)

        reset_cfg_btn = PillButton(btn_row, "重置设置",
                                   lambda: self._reset_settings(vars_),
                                   C["btn_skip"], C["text"], width=74, height=36)
        reset_cfg_btn.pack(side=tk.LEFT, padx=5)

        save_btn = PillButton(btn_row, "保存", _do_save,
                              C["btn_start"], "#FFFDFB", width=64, height=36)
        save_btn.pack(side=tk.LEFT, padx=5)

    # ================================================================== #
    #  Timer engine
    # ================================================================== #
    def _get_total_time(self):
        if self.mode == "work":
            return self._sec(self.work_min)
        elif self.mode == "short_break":
            return self._sec(self.short_min)
        return self._sec(self.long_min)

    def _toggle_top(self):
        new_val = not self.always_on_top.get()
        self.always_on_top.set(new_val)
        self.root.attributes("-topmost", new_val)
        self._update_pin_label()

    def start(self):
        if self.running:
            return
        self.running = True
        self.start_btn.set_disabled(True)
        self.pause_btn.set_disabled(False)
        self._tick()

    def pause(self):
        self.running = False
        self.start_btn.set_disabled(False)
        self.pause_btn.set_disabled(True)
        if self._after_id:
            self.root.after_cancel(self._after_id)
            self._after_id = None

    def reset(self):
        self.running = False
        if self._after_id:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self.remaining = self._get_total_time()
        self.start_btn.set_disabled(False)
        self.pause_btn.set_disabled(True)
        self._update_display()

    def skip(self):
        self.running = False
        if self._after_id:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self._switch_mode()

    def _tick(self):
        if not self.running:
            return
        if self.remaining > 0:
            self.remaining -= 1
            self._update_display()
            self._after_id = self.root.after(1000, self._tick)
        else:
            self.running = False
            self._after_id = None
            self._on_timeout()

    def _on_timeout(self):
        if self.mode == "work":
            self.pomodoro_count += 1
        self._notify()
        self._switch_mode()

    def _switch_mode(self):
        if self.mode == "work":
            if self.pomodoro_count > 0 and self.pomodoro_count % self.before_long == 0:
                self.mode = "long_break"
            else:
                self.mode = "short_break"
        else:
            self.mode = "work"

        self.remaining = self._get_total_time()
        self.start_btn.set_disabled(False)
        self.pause_btn.set_disabled(True)
        self._update_display()

    # ================================================================== #
    #  Display
    # ================================================================== #
    def _update_display(self):
        C = self.C
        minutes = self.remaining // 60
        seconds = self.remaining % 60
        self.timer_label.config(text=f"{minutes:02d}:{seconds:02d}")

        color = C[self.mode]
        self.timer_label.config(fg=color)
        self.mode_label.config(
            text=f"{self.MODE_ICONS[self.mode]}  {self.MODE_LABELS[self.mode]}",
            fg=color
        )
        self.msg_label.config(text=self.MODE_MSGS[self.mode])

        total = self._get_total_time()
        elapsed = total - self.remaining
        self.progress.config(maximum=total, value=elapsed)
        style = ttk.Style()
        style.configure("TProgressbar", background=color, troughcolor=C["trough"])

        self.root.title(
            f"{self.MODE_LABELS[self.mode]} - {minutes:02d}:{seconds:02d}  番茄钟"
        )

        # dots
        cycle = self.pomodoro_count % self.before_long
        if self.pomodoro_count > 0 and cycle == 0:
            cycle = self.before_long
        filled = "\U0001F345 " * cycle
        empty = "  ◦  " * (self.before_long - cycle)
        self.dots_label.config(
            text=f"已完成 {self.pomodoro_count} 个番茄  |  {filled}{empty}",
        )

    # ================================================================== #
    #  Notification
    # ================================================================== #
    def _notify(self):
        if self.mode == "work":
            title = " 番茄时间到！"
            msg = "专注时间结束，休息一下吧 ~"
        elif self.mode == "short_break":
            title = " 休息结束"
            msg = "准备好开始下一个番茄了吗？"
        else:
            title = " 长休息结束"
            msg = "充满能量，开始新的循环吧！✨"

        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self._toast(title, msg)

    def _toast(self, title, message):
        try:
            script = f'''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$textNodes = $template.GetElementsByTagName("text")
$textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) > $null
$textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) > $null
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("PomodoroApp").Show($toast)
'''
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
        except Exception:
            pass

    def _on_close(self):
        self.running = False
        if self._after_id:
            self.root.after_cancel(self._after_id)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    app = PomodoroApp()
    app.run()
