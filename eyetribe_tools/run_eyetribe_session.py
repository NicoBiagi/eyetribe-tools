import tkinter as tk
from tkinter import ttk, messagebox

from eyetribe_tools import (
    EyeTribeSetup,
    get_monitors,
    start_eyetribe_server,
    wait_for_eyes,
    calibrate_and_validate,
    run_desktop_overlay_logger,
)

FRAMERATE = 60
VALIDATION_ERROR_THRESHOLD_PX = 120
CALIBRATION_SAMPLE_SECONDS = 1.8
REQUIRED_STABLE_EYES_SECONDS = 2.0


def ask_session_setup():
    monitors = get_monitors()

    if not monitors:
        raise RuntimeError("No monitors detected.")

    result = {"ok": False}

    root = tk.Tk()
    root.title("Eye Tribe session setup")
    root.geometry("560x430")
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=18)
    frame.pack(fill="both", expand=True)

    ttk.Label(
        frame,
        text="Eye Tribe Session Setup",
        font=("Segoe UI", 16, "bold"),
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 18))

    monitor_labels = []
    for monitor in monitors:
        primary = " primary" if monitor["is_primary"] else ""
        label = (
            f'{monitor["index"]}: '
            f'{monitor["width"]}x{monitor["height"]} '
            f'at ({monitor["left"]}, {monitor["top"]})'
            f'{primary}'
        )
        monitor_labels.append(label)

    resolution_options = sorted(
        set(
            [f'{m["width"]}x{m["height"]}' for m in monitors]
            + ["1280x720", "1600x900", "1920x1080", "2560x1440"]
        )
    )

    monitor_var = tk.StringVar(value=monitor_labels[0])
    resolution_var = tk.StringVar(value=f'{monitors[0]["width"]}x{monitors[0]["height"]}')

    monitor_width_cm_var = tk.StringVar(value="53.1")
    monitor_height_cm_var = tk.StringVar(value="29.9")
    participant_to_monitor_cm_var = tk.StringVar(value="60.0")
    eyetribe_to_monitor_cm_var = tk.StringVar(value="2.0")
    eyetribe_to_participant_cm_var = tk.StringVar(value="58.0")

    def selected_monitor():
        selected = monitor_var.get()
        index = int(selected.split(":", 1)[0])
        return monitors[index]

    def on_monitor_changed(*args):
        monitor = selected_monitor()
        resolution_var.set(f'{monitor["width"]}x{monitor["height"]}')

    monitor_var.trace_add("write", on_monitor_changed)

    row = 1

    ttk.Label(frame, text="Monitor").grid(row=row, column=0, sticky="w", pady=6)
    ttk.OptionMenu(frame, monitor_var, monitor_var.get(), *monitor_labels).grid(
        row=row, column=1, sticky="ew", pady=6
    )

    row += 1
    ttk.Label(frame, text="Resolution").grid(row=row, column=0, sticky="w", pady=6)
    ttk.OptionMenu(frame, resolution_var, resolution_var.get(), *resolution_options).grid(
        row=row, column=1, sticky="ew", pady=6
    )

    row += 1
    ttk.Separator(frame).grid(row=row, column=0, columnspan=2, sticky="ew", pady=14)

    row += 1
    ttk.Label(frame, text="Monitor width (cm)").grid(row=row, column=0, sticky="w", pady=6)
    ttk.Entry(frame, textvariable=monitor_width_cm_var).grid(row=row, column=1, sticky="ew", pady=6)

    row += 1
    ttk.Label(frame, text="Monitor height (cm)").grid(row=row, column=0, sticky="w", pady=6)
    ttk.Entry(frame, textvariable=monitor_height_cm_var).grid(row=row, column=1, sticky="ew", pady=6)

    row += 1
    ttk.Label(frame, text="Participant to monitor (cm)").grid(row=row, column=0, sticky="w", pady=6)
    ttk.Entry(frame, textvariable=participant_to_monitor_cm_var).grid(row=row, column=1, sticky="ew", pady=6)

    row += 1
    ttk.Label(frame, text="EyeTribe to monitor (cm)").grid(row=row, column=0, sticky="w", pady=6)
    ttk.Entry(frame, textvariable=eyetribe_to_monitor_cm_var).grid(row=row, column=1, sticky="ew", pady=6)

    row += 1
    ttk.Label(frame, text="EyeTribe to participant (cm)").grid(row=row, column=0, sticky="w", pady=6)
    ttk.Entry(frame, textvariable=eyetribe_to_participant_cm_var).grid(row=row, column=1, sticky="ew", pady=6)

    def parse_float(name, value):
        try:
            return float(value)
        except ValueError:
            raise ValueError(f"{name} must be a number.")

    def on_ok():
        try:
            monitor = selected_monitor()
            detected_resolution = f'{monitor["width"]}x{monitor["height"]}'
            chosen_resolution = resolution_var.get()

            if chosen_resolution != detected_resolution:
                messagebox.showwarning(
                    "Resolution mismatch",
                    (
                        f"You selected {chosen_resolution}, but Windows reports "
                        f"{detected_resolution} for this monitor.\n\n"
                        "The calibration window will use the Windows-detected resolution."
                    ),
                )

            result["setup"] = EyeTribeSetup(
                monitor_index=monitor["index"],
                monitor_width_cm=parse_float("Monitor width", monitor_width_cm_var.get()),
                monitor_height_cm=parse_float("Monitor height", monitor_height_cm_var.get()),
                participant_to_monitor_cm=parse_float(
                    "Participant to monitor distance",
                    participant_to_monitor_cm_var.get(),
                ),
                eyetribe_to_monitor_cm=parse_float(
                    "EyeTribe to monitor distance",
                    eyetribe_to_monitor_cm_var.get(),
                ),
                eyetribe_to_participant_cm=parse_float(
                    "EyeTribe to participant distance",
                    eyetribe_to_participant_cm_var.get(),
                ),
            )
            result["ok"] = True
            root.destroy()

        except ValueError as exc:
            messagebox.showerror("Invalid setup value", str(exc))

    def on_cancel():
        result["ok"] = False
        root.destroy()

    buttons = ttk.Frame(frame)
    buttons.grid(row=row + 1, column=0, columnspan=2, sticky="e", pady=(22, 0))

    ttk.Button(buttons, text="Cancel", command=on_cancel).pack(side="right", padx=(8, 0))
    ttk.Button(buttons, text="OK", command=on_ok).pack(side="right")

    frame.columnconfigure(1, weight=1)

    root.bind("<Return>", lambda event: on_ok())
    root.bind("<Escape>", lambda event: on_cancel())

    root.mainloop()

    if not result["ok"]:
        return None

    return result["setup"]


def main():
    setup = ask_session_setup()

    if setup is None:
        print("Session cancelled.")
        return

    print("Selected setup:")
    print(setup.metadata())

    print("Starting Eye Tribe server...")
    start_eyetribe_server(
        framerate=FRAMERATE,
        restart_existing=True,
    )

    print("Checking whether eyes are detected...")
    eyes_ok = wait_for_eyes(
        setup=setup,
        required_stable_seconds=REQUIRED_STABLE_EYES_SECONDS,
    )

    if not eyes_ok:
        print("Tracking check cancelled. Session stopped.")
        return

    print("Running calibration and validation...")
    validation_csv = calibrate_and_validate(
        setup=setup,
        calibration_sample_seconds=CALIBRATION_SAMPLE_SECONDS,
        validation_error_threshold_px=VALIDATION_ERROR_THRESHOLD_PX,
    )

    print(f"Calibration/validation saved to: {validation_csv}")

    print("Starting transparent desktop gaze overlay/logger...")
    gaze_csv = run_desktop_overlay_logger(
        monitor_index=setup.monitor_index,
        validation_csv=validation_csv,
    )

    print(f"Gaze data saved to: {gaze_csv}")
    print("Session complete.")


if __name__ == "__main__":
    main()