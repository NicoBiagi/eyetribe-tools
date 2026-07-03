import json
import socket
import threading
import time


def get_nested(mapping, *keys, default=None):
    value = mapping
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


class EyeTribeClient:
    def __init__(self, host="127.0.0.1", port=6555):
        print(f"Connecting to Eye Tribe at {host}:{port} ...")
        self.sock = socket.create_connection((host, port), timeout=5)
        self.sock.settimeout(0.5)

        self.buffer = ""
        self.latest_gaze = None
        self.running = True
        self.lock = threading.Lock()
        self.callbacks = []

        self.send("tracker", "set", {"push": True, "version": 1})

        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()

        print("Connected.")

    def send(self, category, request, values=None):
        msg = {"category": category, "request": request}
        if values is not None:
            msg["values"] = values
        self.sock.sendall(json.dumps(msg, separators=(",", ":")).encode("utf-8"))

    def add_sample_callback(self, callback):
        self.callbacks.append(callback)

    def get_latest_gaze(self):
        with self.lock:
            if self.latest_gaze is None:
                return None
            return dict(self.latest_gaze)

    def calibration_start(self, point_count):
        self.send("calibration", "start", {"pointcount": point_count})

    def point_start(self, x, y):
        self.send("calibration", "pointstart", {"x": int(x), "y": int(y)})

    def point_end(self):
        self.send("calibration", "pointend")

    def close(self):
        self.running = False
        try:
            self.send("tracker", "set", {"push": False})
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass

    def _read_loop(self):
        decoder = json.JSONDecoder()

        while self.running:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break

            if not chunk:
                break

            self.buffer += chunk.decode("utf-8", errors="replace")

            while self.buffer.strip():
                stripped = self.buffer.lstrip()

                try:
                    msg, end = decoder.raw_decode(stripped)
                except json.JSONDecodeError:
                    self.buffer = stripped
                    break

                self.buffer = stripped[end:]
                sample = self._extract_sample(msg)

                if sample is not None:
                    with self.lock:
                        self.latest_gaze = sample

                    for callback in self.callbacks:
                        callback(sample)

    def _extract_sample(self, msg):
        frame = msg.get("values", {}).get("frame")
        if not isinstance(frame, dict):
            return None

        avg = frame.get("avg")
        left = frame.get("lefteye") or {}
        right = frame.get("righteye") or {}

        if not isinstance(avg, dict):
            avg = {}

        x = avg.get("x")
        y = avg.get("y")

        return {
            "pc_time": time.time(),
            "tracker_time": frame.get("time"),
            "x": float(x) if isinstance(x, (int, float)) else None,
            "y": float(y) if isinstance(y, (int, float)) else None,
            "state": frame.get("state"),
            "fix": frame.get("fix"),

            # Eye position inside the tracker/camera coordinate space.
            # These are useful for a pre-calibration "are the eyes visible?" view.
            "left_pcenter_x": get_nested(left, "pcenter", "x"),
            "left_pcenter_y": get_nested(left, "pcenter", "y"),
            "right_pcenter_x": get_nested(right, "pcenter", "x"),
            "right_pcenter_y": get_nested(right, "pcenter", "y"),

            "left_psize": left.get("psize"),
            "right_psize": right.get("psize"),
        }