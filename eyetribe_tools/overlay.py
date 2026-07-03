import csv
import ctypes
import queue
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path

from .client import EyeTribeClient
from .monitors import get_monitor

GOOD_TRACKING_STATES = {7}
DOT_RADIUS = 12
TRANSPARENT_COLOR = "#010203"
ESC_KEY = 0x1B


def esc_is_pressed():
    return ctypes.windll.user32.GetAsyncKeyState(ESC_KEY) & 0x8000 != 0


def make_clickthrough(window):
    hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
    ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)

    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_TOOLWINDOW = 0x00000080

    ctypes.windll.user32.SetWindowLongW(
        hwnd,
        -20,
        ex_style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW,
    )


def load_validation_offset(csv_path):
    if csv_path is None:
        return 0.0, 0.0

    path = Path(csv_path)
    if not path.exists():
        print(f"Validation CSV not found: {path}")
        return 0.0, 0.0

    dx_values = []
    dy_values = []

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            if row.get("phase") != "validation":
                continue

            passed = str(row.get("passed_threshold", "")).lower() == "true"
            if not passed:
                continue

            try:
                target_x = float(row["target_screen_x"])
                target_y = float(row["target_screen_y"])
                mean_x = float(row["mean_gaze_screen_x"])
                mean_y = float(row["mean_gaze_screen_y"])
            except (KeyError, TypeError, ValueError):
                continue

            dx_values.append(target_x - mean_x)
            dy_values.append(target_y - mean_y)

    if not dx_values:
        print("No passed validation rows found. Using no offset correction.")
        return 0.0, 0.0

    offset_x = sum(dx_values) / len(dx_values)
    offset_y = sum(dy_values) / len(dy_values)

    print(f"Loaded validation offset: x={offset_x:.1f}px, y={offset_y:.1f}px")
    return offset_x, offset_y


class DesktopOverlayLogger:
    def __init__(
        self,
        monitor_index=0,
        host="127.0.0.1",
        port=6555,
        output=None,
        validation_csv=None,
        clickthrough=True,
    ):
        self.monitor = get_monitor(monitor_index)
        self.monitor_index = monitor_index
        self.left = self.monitor["left"]
        self.top = self.monitor["top"]
        self.w = self.monitor["width"]
        self.h = self.monitor["height"]
        self.clickthrough = clickthrough

        self.samples = queue.Queue()
        self.tracker = EyeTribeClient(host=host, port=port)
        self.tracker.add_sample_callback(self.samples.put)

        self.offset_x, self.offset_y = load_validation_offset(validation_csv)

        if output is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_path = Path(f"eyetribe_desktop_gaze_{timestamp}.csv")
        else:
            self.output_path = Path(output)

        self.start_time = time.time()
        self.sample_count = 0

        self.output_file = self.output_path.open("w", newline="", encoding="utf-8")
        self.writer = csv.DictWriter(
            self.output_file,
            fieldnames=[
                "sample_index",
                "session_time_s",
                "pc_time",
                "tracker_time",
                "monitor_index",
                "monitor_left",
                "monitor_top",
                "raw_screen_x",
                "raw_screen_y",
                "corrected_screen_x",
                "corrected_screen_y",
                "corrected_local_x",
                "corrected_local_y",
                "state",
                "fix",
                "good_tracking",
                "offset_x",
                "offset_y",
            ],
        )
        self.writer.writeheader()

        self.root = tk.Tk()
        self.root.title("Eye Tribe desktop overlay logger")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        self.root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        self.root.config(cursor="none")
        self.root.geometry(f"{self.w}x{self.h}+{self.left}+{self.top}")

        self.canvas = tk.Canvas(
            self.root,
            width=self.w,
            height=self.h,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
            cursor="none",
        )
        self.canvas.pack(fill="both", expand=True)

        self.status = self.canvas.create_text(
            16,
            16,
            anchor="nw",
            fill="white",
            font=("Segoe UI", 11, "bold"),
            text="EyeTribe recording. Press Esc to stop.",
        )

        self.root.after(250, self.enable_clickthrough)

    def screen_to_local(self, x, y):
        return x - self.left, y - self.top

    def enable_clickthrough(self):
        if self.clickthrough:
            make_clickthrough(self.root)

    def run(self):
        print(f"Recording gaze to: {self.output_path}")
        print(f"Overlay on monitor {self.monitor_index}: {self.w}x{self.h} at ({self.left}, {self.top})")
        print("Press Esc to stop.")
        self.update()
        self.root.mainloop()
        return self.output_path

    def update(self):
        if esc_is_pressed():
            self.quit()
            return

        latest_sample = None

        while True:
            try:
                sample = self.samples.get_nowait()
            except queue.Empty:
                break

            latest_sample = sample
            self.write_sample(sample)

        if latest_sample is not None:
            self.draw_latest_sample(latest_sample)

        self.root.after(16, self.update)

    def write_sample(self, sample):
        corrected_screen_x = sample["x"] + self.offset_x
        corrected_screen_y = sample["y"] + self.offset_y
        corrected_local_x, corrected_local_y = self.screen_to_local(corrected_screen_x, corrected_screen_y)
        good_tracking = sample["state"] in GOOD_TRACKING_STATES

        self.writer.writerow(
            {
                "sample_index": self.sample_count,
                "session_time_s": sample["pc_time"] - self.start_time,
                "pc_time": sample["pc_time"],
                "tracker_time": sample["tracker_time"],
                "monitor_index": self.monitor_index,
                "monitor_left": self.left,
                "monitor_top": self.top,
                "raw_screen_x": sample["x"],
                "raw_screen_y": sample["y"],
                "corrected_screen_x": corrected_screen_x,
                "corrected_screen_y": corrected_screen_y,
                "corrected_local_x": corrected_local_x,
                "corrected_local_y": corrected_local_y,
                "state": sample["state"],
                "fix": sample["fix"],
                "good_tracking": good_tracking,
                "offset_x": self.offset_x,
                "offset_y": self.offset_y,
            }
        )

        self.sample_count += 1

        if self.sample_count % 120 == 0:
            self.output_file.flush()
            print(f"{self.sample_count} samples written...")

    def draw_latest_sample(self, sample):
        corrected_screen_x = sample["x"] + self.offset_x
        corrected_screen_y = sample["y"] + self.offset_y
        local_x, local_y = self.screen_to_local(corrected_screen_x, corrected_screen_y)
        good_tracking = sample["state"] in GOOD_TRACKING_STATES

        x = max(0, min(self.w, local_x))
        y = max(0, min(self.h, local_y))

        self.canvas.delete("gaze")

        color = "#ff3b30" if good_tracking else "#888888"
        outline = "white" if good_tracking else "#dddddd"
        r = DOT_RADIUS

        self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=color, outline=outline, width=2, tags="gaze")
        self.canvas.create_line(x - r - 8, y, x + r + 8, y, fill=outline, width=1, tags="gaze")
        self.canvas.create_line(x, y - r - 8, x, y + r + 8, fill=outline, width=1, tags="gaze")

        self.canvas.itemconfigure(
            self.status,
            text=(
                f"EyeTribe recording | samples={self.sample_count} | "
                f"monitor={self.monitor_index} | local=({x:.0f}, {y:.0f}) | "
                f"screen=({corrected_screen_x:.0f}, {corrected_screen_y:.0f}) | "
                f"state={sample['state']} | Esc stops"
            ),
        )

    def quit(self):
        print("Stopping...")
        try:
            self.tracker.close()
        finally:
            self.output_file.flush()
            self.output_file.close()
            print(f"Saved {self.sample_count} samples to: {self.output_path}")
            self.root.destroy()


def run_desktop_overlay_logger(
    monitor_index=0,
    host="127.0.0.1",
    port=6555,
    output=None,
    validation_csv=None,
    clickthrough=True,
):
    app = DesktopOverlayLogger(
        monitor_index=monitor_index,
        host=host,
        port=port,
        output=output,
        validation_csv=validation_csv,
        clickthrough=clickthrough,
    )
    return app.run()