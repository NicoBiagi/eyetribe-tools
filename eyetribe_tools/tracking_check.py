import time
import tkinter as tk

from .client import EyeTribeClient
from .monitors import get_monitor
from .setup import EyeTribeSetup

GOOD_TRACKING_STATES = {7}


class TrackingCheckApp:
    def __init__(
        self,
        setup=None,
        monitor_index=0,
        host="127.0.0.1",
        port=6555,
        required_stable_seconds=2.0,
    ):
        self.setup = setup or EyeTribeSetup(monitor_index=monitor_index)
        self.monitor_index = self.setup.monitor_index
        self.monitor = get_monitor(self.monitor_index)

        self.required_stable_seconds = required_stable_seconds
        self.good_since = None
        self.result = False

        self.tracker = EyeTribeClient(host=host, port=port)

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black")
        self.root.bind_all("<Escape>", lambda event: self.quit(False))
        self.root.bind_all("<space>", lambda event: self.quit(True))

        self.w = self.monitor["width"]
        self.h = self.monitor["height"]
        self.left = self.monitor["left"]
        self.top = self.monitor["top"]

        self.root.geometry(f"{self.w}x{self.h}+{self.left}+{self.top}")

        self.canvas = tk.Canvas(
            self.root,
            width=self.w,
            height=self.h,
            bg="black",
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.root.after(250, self.force_focus)

    def force_focus(self):
        try:
            self.root.lift()
            self.root.focus_force()
            self.canvas.focus_set()
        except tk.TclError:
            pass

    def run(self):
        print("Tracking check opened.")
        print("Press Space to continue once eyes are detected, or Esc to cancel.")
        self.update()
        self.root.mainloop()
        return self.result

    def update(self):
        gaze = self.tracker.get_latest_gaze()
        now = time.time()

        if gaze is None:
            good = False
            state = None
        else:
            state = gaze.get("state")
            good = state in GOOD_TRACKING_STATES

        if good:
            if self.good_since is None:
                self.good_since = now
            stable_for = now - self.good_since
        else:
            self.good_since = None
            stable_for = 0.0

        self.draw(gaze=gaze, good=good, state=state, stable_for=stable_for)
        self.root.after(33, self.update)

    def draw(self, gaze, good, state, stable_for):
        self.canvas.delete("all")

        if good:
            bg = "#143b1e"
            title = "Eyes detected"
            subtitle = "Tracking looks good. Press Space to continue."
        else:
            bg = "#3b1512"
            title = "Eyes not reliably detected"
            subtitle = (
                "Adjust distance, angle, lighting, or tracker position.\n"
                "Keep both eyes visible to the tracker."
            )

        self.canvas.configure(bg=bg)

        cx = self.w / 2
        cy = self.h / 2

        panel_w = min(760, self.w * 0.78)
        panel_h = min(430, self.h * 0.58)
        panel_x0 = cx - panel_w / 2
        panel_y0 = cy - panel_h / 2 - 30
        panel_x1 = cx + panel_w / 2
        panel_y1 = cy + panel_h / 2 - 30

        self.canvas.create_text(
            cx,
            70,
            text="Eye Tribe tracking check",
            fill="white",
            font=("Segoe UI", 34, "bold"),
        )

        self.canvas.create_rectangle(
            panel_x0,
            panel_y0,
            panel_x1,
            panel_y1,
            fill="#2e2e2e",
            outline="#888888",
            width=2,
        )

        self.draw_grid(panel_x0, panel_y0, panel_x1, panel_y1)

        glow_color = "#22cc3a" if good else "#664033"
        for i in range(9):
            margin = i * 18
            self.canvas.create_oval(
                panel_x0 + margin,
                panel_y0 + margin,
                panel_x1 - margin,
                panel_y1 - margin,
                outline=glow_color,
                width=2,
            )

        self.draw_detected_eyes(gaze, panel_x0, panel_y0, panel_x1, panel_y1)

        self.canvas.create_text(
            cx,
            panel_y1 + 45,
            text=title,
            fill="white",
            font=("Segoe UI", 28, "bold"),
        )

        self.canvas.create_text(
            cx,
            panel_y1 + 95,
            text=subtitle,
            fill="white",
            font=("Segoe UI", 18),
            justify="center",
        )

        progress = min(1.0, stable_for / self.required_stable_seconds) if good else 0.0

        bar_w = min(540, self.w * 0.55)
        bar_h = 24
        bar_x0 = cx - bar_w / 2
        bar_y0 = panel_y1 + 145

        self.canvas.create_rectangle(
            bar_x0,
            bar_y0,
            bar_x0 + bar_w,
            bar_y0 + bar_h,
            outline="white",
            width=2,
        )
        self.canvas.create_rectangle(
            bar_x0,
            bar_y0,
            bar_x0 + bar_w * progress,
            bar_y0 + bar_h,
            fill="#00ff66",
            outline="",
        )

        gaze_x = self.format_value(gaze.get("x") if gaze else None)
        gaze_y = self.format_value(gaze.get("y") if gaze else None)

        left_eye = self.eye_text(gaze, "left")
        right_eye = self.eye_text(gaze, "right")

        self.canvas.create_text(
            cx,
            bar_y0 + 58,
            text=(
                f"state={state}   gaze=({gaze_x}, {gaze_y})   "
                f"stable={stable_for:.1f}s / {self.required_stable_seconds:.1f}s\n"
                f"left eye: {left_eye}      right eye: {right_eye}"
            ),
            fill="white",
            font=("Consolas", 14),
            justify="center",
        )

        self.canvas.create_text(
            20,
            self.h - 35,
            anchor="sw",
            text="Space = continue    Esc = cancel",
            fill="white",
            font=("Segoe UI", 14),
        )

    def draw_grid(self, x0, y0, x1, y1):
        cols = 12
        rows = 8

        for i in range(1, cols):
            x = x0 + (x1 - x0) * i / cols
            self.canvas.create_line(x, y0, x, y1, fill="#444444")

        for i in range(1, rows):
            y = y0 + (y1 - y0) * i / rows
            self.canvas.create_line(x0, y, x1, y, fill="#444444")

    def draw_detected_eyes(self, gaze, x0, y0, x1, y1):
        if gaze is None:
            return

        left = self.eye_panel_position(gaze, "left", x0, y0, x1, y1)
        right = self.eye_panel_position(gaze, "right", x0, y0, x1, y1)

        if left is not None:
            self.draw_eye(left[0], left[1], scale=0.95)

        if right is not None:
            self.draw_eye(right[0], right[1], scale=0.95)

        if left is None and right is None and gaze.get("x") is not None and gaze.get("y") is not None:
            gx = (gaze["x"] - self.left) / self.w
            gy = (gaze["y"] - self.top) / self.h
            px = x0 + max(0, min(1, gx)) * (x1 - x0)
            py = y0 + max(0, min(1, gy)) * (y1 - y0)
            self.draw_crosshair(px, py)

    def eye_panel_position(self, gaze, side, x0, y0, x1, y1):
        px = gaze.get(f"{side}_pcenter_x")
        py = gaze.get(f"{side}_pcenter_y")

        if not isinstance(px, (int, float)) or not isinstance(py, (int, float)):
            return None

        nx = max(0.0, min(1.0, float(px)))
        ny = max(0.0, min(1.0, float(py)))

        x = x0 + nx * (x1 - x0)
        y = y0 + ny * (y1 - y0)

        return x, y

    def draw_eye(self, x, y, scale=1.0):
        w = 78 * scale
        h = 38 * scale
        iris = 24 * scale
        pupil = 9 * scale

        self.canvas.create_oval(
            x - w,
            y - h,
            x + w,
            y + h,
            fill="#eaf9ff",
            outline="#c5e6ef",
            width=2,
        )
        self.canvas.create_oval(
            x - iris,
            y - iris,
            x + iris,
            y + iris,
            fill="#62d5ef",
            outline="#1d6d7d",
            width=2,
        )
        self.canvas.create_oval(
            x - pupil,
            y - pupil,
            x + pupil,
            y + pupil,
            fill="#111111",
            outline="",
        )
        self.canvas.create_oval(
            x - iris / 2,
            y - iris / 2,
            x - iris / 5,
            y - iris / 5,
            fill="white",
            outline="",
        )

    def draw_crosshair(self, x, y):
        r = 18
        self.canvas.create_oval(x - r, y - r, x + r, y + r, outline="white", width=2)
        self.canvas.create_line(x - r - 8, y, x + r + 8, y, fill="white", width=1)
        self.canvas.create_line(x, y - r - 8, x, y + r + 8, fill="white", width=1)

    def eye_text(self, gaze, side):
        if gaze is None:
            return "NA"

        x = gaze.get(f"{side}_pcenter_x")
        y = gaze.get(f"{side}_pcenter_y")
        size = gaze.get(f"{side}_psize")

        return f"x={self.format_value(x)}, y={self.format_value(y)}, size={self.format_value(size)}"

    def format_value(self, value):
        if isinstance(value, (int, float)):
            return f"{value:.2f}"
        return "NA"

    def quit(self, result):
        self.result = result
        try:
            self.tracker.close()
        finally:
            self.root.destroy()


def wait_for_eyes(
    setup=None,
    monitor_index=0,
    host="127.0.0.1",
    port=6555,
    required_stable_seconds=2.0,
):
    app = TrackingCheckApp(
        setup=setup,
        monitor_index=monitor_index,
        host=host,
        port=port,
        required_stable_seconds=required_stable_seconds,
    )
    return app.run()