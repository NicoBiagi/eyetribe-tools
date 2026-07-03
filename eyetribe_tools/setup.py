import math
from dataclasses import dataclass


@dataclass
class EyeTribeSetup:
    monitor_index: int = 0
    monitor_width_cm: float | None = None
    monitor_height_cm: float | None = None
    participant_to_monitor_cm: float | None = None
    eyetribe_to_monitor_cm: float | None = None
    eyetribe_to_participant_cm: float | None = None

    def metadata(self):
        return {
            "setup_monitor_index": self.monitor_index,
            "setup_monitor_width_cm": self.monitor_width_cm,
            "setup_monitor_height_cm": self.monitor_height_cm,
            "setup_participant_to_monitor_cm": self.participant_to_monitor_cm,
            "setup_eyetribe_to_monitor_cm": self.eyetribe_to_monitor_cm,
            "setup_eyetribe_to_participant_cm": self.eyetribe_to_participant_cm,
        }

    def has_visual_angle_info(self):
        return (
            self.monitor_width_cm is not None
            and self.monitor_height_cm is not None
            and self.participant_to_monitor_cm is not None
            and self.participant_to_monitor_cm > 0
        )

    def pixels_to_degrees(self, dx_px, dy_px, monitor_width_px, monitor_height_px):
        if not self.has_visual_angle_info():
            return None

        cm_per_px_x = self.monitor_width_cm / monitor_width_px
        cm_per_px_y = self.monitor_height_cm / monitor_height_px

        dx_cm = dx_px * cm_per_px_x
        dy_cm = dy_px * cm_per_px_y
        error_cm = math.sqrt(dx_cm ** 2 + dy_cm ** 2)

        return math.degrees(
            2 * math.atan2(error_cm, 2 * self.participant_to_monitor_cm)
        )