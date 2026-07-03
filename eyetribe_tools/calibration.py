import csv
import math
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path

from .client import EyeTribeClient
from .monitors import get_monitor
from .setup import EyeTribeSetup

GOOD_TRACKING_STATES = {7}
CALIBRATION_TRACKING_STABLE_SECONDS = 0.5


class CalibrationApp:
    def __init__(
        self,
        setup=None,
        monitor_index=0,
        host="127.0.0.1",
        port=6555,
        calibration_sample_seconds=1.8,
        validation_sample_seconds=1.3,
        validation_error_threshold_px=120,
        max_validation_retries_per_point=2,
        calibration_tracking_stable_seconds=CALIBRATION_TRACKING_STABLE_SECONDS,
        show_gaze_dot_during_calibration=True,
        show_gaze_dot_during_validation=True,
        output=None,
    ):
        self.setup = setup or EyeTribeSetup(monitor_index=monitor_index)
        self.monitor_index = self.setup.monitor_index
        self.monitor = get_monitor(self.monitor_index)

        self.host = host
        self.port = port
        self.calibration_sample_seconds = calibration_sample_seconds
        self.validation_sample_seconds = validation_sample_seconds
        self.validation_error_threshold_px = validation_error_threshold_px
        self.max_validation_retries_per_point = max_validation_retries_per_point
        self.calibration_tracking_stable_seconds = calibration_tracking_stable_seconds
        self.show_gaze_dot_during_calibration = show_gaze_dot_during_calibration
        self.show_gaze_dot_during_validation = show_gaze_dot_during_validation
        self.started = False

        self.tracker = EyeTribeClient(host=host, port=port)

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black")
        self.root.config(cursor="none")
        self.root.bind_all("<Escape>", lambda event: self.quit())

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
            cursor="none",
        )
        self.canvas.pack(fill="both", expand=True)

        mx = int(self.w * 0.12)
        my = int(self.h * 0.12)
        cx = self.w // 2
        cy = self.h // 2

        self.local_points = [
            (cx, cy),
            (mx, my),
            (cx, my),
            (self.w - mx, my),
            (mx, cy),
            (self.w - mx, cy),
            (mx, self.h - my),
            (cx, self.h - my),
            (self.w - mx, self.h - my),
        ]

        self.calibration_events = []
        self.validation_events = []
        self.session_start_local = None

        if output is None:
            self.output_file = Path(
                f"eyetribe_calibration_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
        else:
            self.output_file = Path(output)

    def local_to_screen(self, x, y):
        return self.left + x, self.top + y

    def screen_to_local(self, x, y):
        return x - self.left, y - self.top

    def setup_metadata(self):
        return self.setup.metadata()

    def run(self):
        self.canvas.create_text(
            self.w / 2,
            self.h / 2,
            text=(
                f"Eye tracker calibration\n\n"
                f"Monitor {self.monitor_index}: {self.w}x{self.h} at ({self.left}, {self.top})\n\n"
                "Look at each green dot until it moves.\nPress Space to start."
            ),
            fill="white",
            font=("Segoe UI", 26),
            justify="center",
        )

        self.root.bind_all("<space>", self.start_from_key)
        self.root.after(250, self.force_focus)

        print(f"Calibration window opened on monitor {self.monitor_index}. Press Space to begin.")
        self.root.mainloop()
        return self.output_file

    def force_focus(self):
        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.focus_force()
            self.canvas.focus_set()
        except tk.TclError:
            pass

    def start_from_key(self, event=None):
        if self.started:
            return

        self.started = True
        self.root.unbind_all("<space>")
        self.start()

    def start(self):
        self.run_calibration()
        self.run_validation()
        self.save_log()
        self.show_summary()

    def draw_target(self, local_x, local_y, index, total, phase, attempt=None, status_text=None):
        self.canvas.delete("all")

        label = f"{phase} point {index} / {total}"
        if attempt is not None:
            label += f"   attempt {attempt}"

        self.canvas.create_text(
            20,
            20,
            anchor="nw",
            text=label,
            fill="white",
            font=("Segoe UI", 16),
        )
        self.canvas.create_oval(
            local_x - 28,
            local_y - 28,
            local_x + 28,
            local_y + 28,
            outline="white",
            width=3,
        )
        self.canvas.create_oval(
            local_x - 7,
            local_y - 7,
            local_x + 7,
            local_y + 7,
            fill="#00ff66",
            outline="",
        )
        if status_text:
            self.canvas.create_text(
                self.w / 2,
                self.h - 80,
                text=status_text,
                fill="white",
                font=("Segoe UI", 18),
                justify="center",
            )
        self.root.update()

    def draw_gaze_dot(self, gaze):
        if gaze is None:
            return
        if not isinstance(gaze.get("x"), (int, float)) or not isinstance(gaze.get("y"), (int, float)):
            return

        local_x, local_y = self.screen_to_local(gaze["x"], gaze["y"])
        local_x = max(0, min(self.w, local_x))
        local_y = max(0, min(self.h, local_y))
        r = 14

        self.canvas.delete("gaze")
        self.canvas.create_oval(
            local_x - r,
            local_y - r,
            local_x + r,
            local_y + r,
            fill="#ff3b30",
            outline="white",
            width=2,
            tags="gaze",
        )
        self.canvas.create_line(
            local_x - r - 8,
            local_y,
            local_x + r + 8,
            local_y,
            fill="white",
            width=1,
            tags="gaze",
        )
        self.canvas.create_line(
            local_x,
            local_y - r - 8,
            local_x,
            local_y + r + 8,
            fill="white",
            width=1,
            tags="gaze",
        )

    def wait_for_good_tracking_before_calibration_point(self, local_x, local_y, index):
        stable_since = None
        wait_start = time.time()

        while True:
            gaze = self.tracker.get_latest_gaze()
            state = gaze.get("state") if gaze is not None else None
            good = state in GOOD_TRACKING_STATES
            now = time.time()

            if good:
                if stable_since is None:
                    stable_since = now
                stable_for = now - stable_since
            else:
                stable_since = None
                stable_for = 0.0

            status = (
                f"Waiting for eyes before calibration point {index}\n"
                f"state={state}   stable={stable_for:.1f}s / {self.calibration_tracking_stable_seconds:.1f}s"
            )

            self.draw_target(
                local_x,
                local_y,
                index,
                len(self.local_points),
                "Calibration",
                status_text=status,
            )

            if self.show_gaze_dot_during_calibration and gaze is not None:
                self.draw_gaze_dot(gaze)

            self.root.update()

            if stable_for >= self.calibration_tracking_stable_seconds:
                return now - wait_start

            time.sleep(1 / 60)

    def run_calibration(self):
        print("Starting calibration...")
        self.tracker.calibration_start(len(self.local_points))

        calibration_start_time = time.time()
        self.session_start_local = datetime.fromtimestamp(
            calibration_start_time
        ).isoformat(timespec="milliseconds")

        time.sleep(0.5)

        for index, (local_x, local_y) in enumerate(self.local_points, start=1):
            screen_x, screen_y = self.local_to_screen(local_x, local_y)
            print(f"Calibration point {index}/{len(self.local_points)}: screen_x={screen_x}, screen_y={screen_y}")

            self.draw_target(
                local_x,
                local_y,
                index,
                len(self.local_points),
                "Calibration",
                status_text="Look at the green target. Waiting for eyes...",
            )
            target_shown_time = time.time()
            time.sleep(0.5)

            pre_point_tracking_wait_s = self.wait_for_good_tracking_before_calibration_point(
                local_x=local_x,
                local_y=local_y,
                index=index,
            )

            self.draw_target(
                local_x,
                local_y,
                index,
                len(self.local_points),
                "Calibration",
                status_text="Collecting calibration samples...",
            )
            self.tracker.point_start(screen_x, screen_y)
            point_start_time = time.time()
            time.sleep(self.calibration_sample_seconds)

            self.tracker.point_end()
            point_end_time = time.time()

            row = {
                "phase": "calibration",
                "point_index": index,
                "attempt": 1,
                "monitor_index": self.monitor_index,
                "monitor_left": self.left,
                "monitor_top": self.top,
                "monitor_width_px": self.w,
                "monitor_height_px": self.h,
                "target_local_x": local_x,
                "target_local_y": local_y,
                "target_screen_x": screen_x,
                "target_screen_y": screen_y,
                "session_start_local": self.session_start_local,
                "target_shown_s": target_shown_time - calibration_start_time,
                "point_start_s": point_start_time - calibration_start_time,
                "point_end_s": point_end_time - calibration_start_time,
                "sample_duration_s": point_end_time - point_start_time,
                "pre_point_tracking_wait_s": pre_point_tracking_wait_s,
                "n_validation_samples": "",
                "mean_gaze_screen_x": "",
                "mean_gaze_screen_y": "",
                "mean_gaze_local_x": "",
                "mean_gaze_local_y": "",
                "error_px": "",
                "error_deg": "",
                "passed_threshold": "",
                "state_values": "",
            }
            row.update(self.setup_metadata())
            self.calibration_events.append(row)

            time.sleep(0.3)

        print("Calibration finished.")

    def run_validation(self):
        print("Starting validation...")

        self.canvas.delete("all")
        self.canvas.create_text(
            self.w / 2,
            self.h / 2,
            text=(
                "Validation\n\n"
                "Green dot = target\n"
                "Red dot = live gaze estimate\n\n"
                f"Retry threshold: {self.validation_error_threshold_px}px"
            ),
            fill="white",
            font=("Segoe UI", 26),
            justify="center",
        )
        self.root.update()
        time.sleep(2.0)

        validation_start_time = time.time()

        for index, (local_x, local_y) in enumerate(self.local_points, start=1):
            attempt = 1

            while attempt <= self.max_validation_retries_per_point + 1:
                result = self.run_validation_attempt(
                    local_x=local_x,
                    local_y=local_y,
                    index=index,
                    attempt=attempt,
                    validation_start_time=validation_start_time,
                )

                self.validation_events.append(result)
                error_px = result["error_px"]
                passed = isinstance(error_px, (int, float)) and error_px <= self.validation_error_threshold_px

                if passed:
                    print(f"Validation point {index} passed: {error_px:.1f}px")
                    break

                if attempt <= self.max_validation_retries_per_point:
                    self.show_retry_message(index, error_px)
                    time.sleep(1.2)

                attempt += 1

            self.canvas.delete("gaze")
            time.sleep(0.3)

        print("Validation finished.")

    def run_validation_attempt(self, local_x, local_y, index, attempt, validation_start_time):
        screen_x, screen_y = self.local_to_screen(local_x, local_y)
        self.draw_target(local_x, local_y, index, len(self.local_points), "Validation", attempt=attempt)

        target_shown_time = time.time()
        time.sleep(0.5)

        samples = []
        sample_start_time = time.time()

        while time.time() - sample_start_time < self.validation_sample_seconds:
            gaze = self.tracker.get_latest_gaze()

            if gaze is not None:
                samples.append(gaze)
                if self.show_gaze_dot_during_validation:
                    self.draw_gaze_dot(gaze)

            self.root.update()
            time.sleep(1 / 60)

        sample_end_time = time.time()

        valid_samples = [
            sample for sample in samples
            if sample.get("state") in GOOD_TRACKING_STATES
            and isinstance(sample.get("x"), (int, float))
            and isinstance(sample.get("y"), (int, float))
        ]

        if valid_samples:
            mean_screen_x = sum(sample["x"] for sample in valid_samples) / len(valid_samples)
            mean_screen_y = sum(sample["y"] for sample in valid_samples) / len(valid_samples)
            mean_local_x, mean_local_y = self.screen_to_local(mean_screen_x, mean_screen_y)
            dx_px = mean_screen_x - screen_x
            dy_px = mean_screen_y - screen_y
            error_px = math.sqrt(dx_px ** 2 + dy_px ** 2)
            error_deg = self.setup.pixels_to_degrees(dx_px, dy_px, self.w, self.h)
            state_values = sorted(set(str(sample.get("state")) for sample in valid_samples))
            passed_threshold = error_px <= self.validation_error_threshold_px
        else:
            mean_screen_x = ""
            mean_screen_y = ""
            mean_local_x = ""
            mean_local_y = ""
            error_px = ""
            error_deg = ""
            state_values = []
            passed_threshold = False

        row = {
            "phase": "validation",
            "point_index": index,
            "attempt": attempt,
            "monitor_index": self.monitor_index,
            "monitor_left": self.left,
            "monitor_top": self.top,
            "monitor_width_px": self.w,
            "monitor_height_px": self.h,
            "target_local_x": local_x,
            "target_local_y": local_y,
            "target_screen_x": screen_x,
            "target_screen_y": screen_y,
            "session_start_local": self.session_start_local,
            "target_shown_s": target_shown_time - validation_start_time,
            "point_start_s": sample_start_time - validation_start_time,
            "point_end_s": sample_end_time - validation_start_time,
            "sample_duration_s": sample_end_time - sample_start_time,
            "n_validation_samples": len(valid_samples),
            "mean_gaze_screen_x": mean_screen_x,
            "mean_gaze_screen_y": mean_screen_y,
            "mean_gaze_local_x": mean_local_x,
            "mean_gaze_local_y": mean_local_y,
            "error_px": error_px,
            "error_deg": error_deg if error_deg is not None else "",
            "passed_threshold": passed_threshold,
            "state_values": ";".join(state_values),
        }
        row.update(self.setup_metadata())
        return row

    def show_retry_message(self, point_index, error_px):
        if isinstance(error_px, (int, float)):
            message = (
                f"Validation point {point_index} was above threshold.\n\n"
                f"Error: {error_px:.1f}px\n"
                f"Threshold: {self.validation_error_threshold_px}px\n\n"
                "Trying that point again..."
            )
        else:
            message = f"Validation point {point_index} had no valid samples.\n\nTrying that point again..."

        self.canvas.delete("all")
        self.canvas.create_text(
            self.w / 2,
            self.h / 2,
            text=message,
            fill="white",
            font=("Segoe UI", 24),
            justify="center",
        )
        self.root.update()

    def save_log(self):
        fieldnames = [
            "phase",
            "point_index",
            "attempt",
            "monitor_index",
            "monitor_left",
            "monitor_top",
            "monitor_width_px",
            "monitor_height_px",
            "target_local_x",
            "target_local_y",
            "target_screen_x",
            "target_screen_y",
            "session_start_local",
            "target_shown_s",
            "point_start_s",
            "point_end_s",
            "sample_duration_s",
            "pre_point_tracking_wait_s",
            "n_validation_samples",
            "mean_gaze_screen_x",
            "mean_gaze_screen_y",
            "mean_gaze_local_x",
            "mean_gaze_local_y",
            "error_px",
            "error_deg",
            "passed_threshold",
            "state_values",
            "setup_monitor_index",
            "setup_monitor_width_cm",
            "setup_monitor_height_cm",
            "setup_participant_to_monitor_cm",
            "setup_eyetribe_to_monitor_cm",
            "setup_eyetribe_to_participant_cm",
        ]

        with self.output_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.calibration_events)
            writer.writerows(self.validation_events)

        print(f"Saved calibration/validation log to {self.output_file}")

    def show_summary(self):
        final_attempts = {}

        for row in self.validation_events:
            final_attempts[row["point_index"]] = row

        final_errors_px = [
            row["error_px"]
            for row in final_attempts.values()
            if isinstance(row["error_px"], (int, float))
        ]

        final_errors_deg = [
            row["error_deg"]
            for row in final_attempts.values()
            if isinstance(row["error_deg"], (int, float))
        ]

        passed_count = sum(1 for row in final_attempts.values() if row.get("passed_threshold") is True)

        if final_errors_px:
            mean_error_px = sum(final_errors_px) / len(final_errors_px)
            max_error_px = max(final_errors_px)

            if final_errors_deg:
                mean_error_deg = sum(final_errors_deg) / len(final_errors_deg)
                deg_line = f"Mean final validation error: {mean_error_deg:.2f} deg\n"
            else:
                deg_line = ""

            summary = (
                f"Calibration + validation finished.\n\n"
                f"Monitor: {self.monitor_index}\n"
                f"Passed points: {passed_count} / {len(self.local_points)}\n"
                f"Mean final validation error: {mean_error_px:.1f}px\n"
                f"{deg_line}"
                f"Max final validation error: {max_error_px:.1f}px\n\n"
                f"Saved log:\n{self.output_file.name}\n\n"
                "Press Esc to close."
            )
        else:
            summary = (
                f"Calibration finished, but no validation gaze samples were detected.\n\n"
                f"Saved log:\n{self.output_file.name}\n\n"
                "Press Esc to close."
            )

        self.canvas.delete("all")
        self.canvas.create_text(
            self.w / 2,
            self.h / 2,
            text=summary,
            fill="white",
            font=("Segoe UI", 24),
            justify="center",
        )

    def quit(self):
        try:
            self.tracker.close()
        finally:
            self.root.destroy()


def calibrate_and_validate(
    setup=None,
    monitor_index=0,
    host="127.0.0.1",
    port=6555,
    calibration_sample_seconds=1.8,
    validation_sample_seconds=1.3,
    validation_error_threshold_px=120,
    max_validation_retries_per_point=2,
    calibration_tracking_stable_seconds=CALIBRATION_TRACKING_STABLE_SECONDS,
    show_gaze_dot_during_calibration=True,
    show_gaze_dot_during_validation=True,
    output=None,
):
    app = CalibrationApp(
        setup=setup,
        monitor_index=monitor_index,
        host=host,
        port=port,
        calibration_sample_seconds=calibration_sample_seconds,
        validation_sample_seconds=validation_sample_seconds,
        validation_error_threshold_px=validation_error_threshold_px,
        max_validation_retries_per_point=max_validation_retries_per_point,
        calibration_tracking_stable_seconds=calibration_tracking_stable_seconds,
        show_gaze_dot_during_calibration=show_gaze_dot_during_calibration,
        show_gaze_dot_during_validation=show_gaze_dot_during_validation,
        output=output,
    )
    return app.run()
