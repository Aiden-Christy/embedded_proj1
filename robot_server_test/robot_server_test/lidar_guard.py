"""
lidar_guard.py
==============
Background RPLIDAR scanner using the `pyrplidar` package.
Continuously monitors a forward-facing arc and exposes a simple
is_blocked() check for the robot's motion logic.

Install:
    pip install pyrplidar --break-system-packages

Usage:
    from lidar_guard import LidarGuard

    guard = LidarGuard(port="/dev/ttyUSB0", min_dist_mm=500, arc_deg=30)
    guard.start()

    if guard.is_blocked():
        print("Obstacle ahead!")

    guard.stop()
"""

import threading
import logging
import time

logger = logging.getLogger(__name__)

try:
    from pyrplidar import PyRPlidar
    PYRPLIDAR_AVAILABLE = True
except ImportError:
    PYRPLIDAR_AVAILABLE = False
    logger.warning(
        "pyrplidar package not found.\n"
        "Install with: pip install pyrplidar --break-system-packages\n"
        "LidarGuard will run in DISABLED mode (is_blocked() always returns False)."
    )


class LidarGuard:
    """
    Runs a PyRPlidar scan loop in a daemon thread.

    Collects individual measurement points and checks whether any fall
    within `arc_deg` degrees of dead-ahead AND closer than `min_dist_mm`.

    pyrplidar's start_scan() yields one PyRPlidarMeasurement at a time.
    Each measurement has:
        .angle    – degrees (0.0–360.0)
        .distance – millimetres (0 = invalid)
        .quality  – signal strength (0 = invalid)

    The sensor's 0° faces "forward" when mounted normally.  If the sensor
    is rotated, pass heading_offset_deg to compensate (e.g. 180 if mounted
    backwards).
    """

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 115200,
        timeout: int = 3,
        min_dist_mm: float = 500.0,      # block forward if obstacle within this range
        arc_deg: float = 30.0,           # check ±arc_deg either side of heading
        heading_offset_deg: float = 0.0, # rotate if sensor isn't facing forward
        scan_timeout: float = 3.0,       # seconds before scan data is considered stale
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.min_dist_mm = min_dist_mm
        self.arc_deg = arc_deg
        self.heading_offset = heading_offset_deg
        self.scan_timeout = scan_timeout

        self._blocked = False
        self._last_scan_time: float = 0.0
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._lidar = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Start the background scanning thread."""
        if not PYRPLIDAR_AVAILABLE:
            logger.warning("LidarGuard: pyrplidar not installed — guard is disabled.")
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._scan_loop, daemon=True, name="LidarGuard"
        )
        self._thread.start()
        logger.info(
            "LidarGuard started on %s  (min_dist=%dmm, arc=±%d°)",
            self.port, self.min_dist_mm, self.arc_deg,
        )

    def stop(self):
        """Cleanly stop scanning and disconnect the sensor."""
        self._running = False
        if self._lidar:
            try:
                self._lidar.stop()
                self._lidar.set_motor_pwm(0)
                self._lidar.disconnect()
            except Exception:
                pass
            self._lidar = None
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("LidarGuard stopped.")

    def is_blocked(self) -> bool:
        """
        Returns True if an obstacle was detected in the forward arc AND
        the scan data is recent (within scan_timeout seconds).

        If the sensor disconnects or goes stale the method returns False
        so the robot is not permanently frozen — warnings will be logged.
        """
        if not PYRPLIDAR_AVAILABLE:
            return False

        with self._lock:
            data_age = time.time() - self._last_scan_time
            if data_age > self.scan_timeout:
                if self._last_scan_time > 0:
                    logger.warning(
                        "LidarGuard: scan data is %.1fs old (timeout=%.1fs) — "
                        "treating as unblocked so robot isn't frozen.",
                        data_age, self.scan_timeout,
                    )
                return False
            return self._blocked

    @property
    def last_scan_age(self) -> float:
        """Seconds since the last successful measurement update."""
        return time.time() - self._last_scan_time

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _angle_in_arc(self, angle_deg: float) -> bool:
        """Return True if angle_deg is within the forward detection arc."""
        a = (angle_deg - self.heading_offset) % 360
        if a > 180:
            a -= 360   # convert to signed range (-180, 180]
        return abs(a) <= self.arc_deg

    def _scan_loop(self):
        """Main loop: connect, stream measurements, reconnect on errors."""
        while self._running:
            try:
                logger.info("LidarGuard: connecting to %s ...", self.port)
                self._lidar = PyRPlidar()
                self._lidar.connect(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                )

                logger.info("LidarGuard: info   — %s", self._lidar.get_info())
                logger.info("LidarGuard: health — %s", self._lidar.get_health())

                # Spin up the motor and give it a moment to reach speed
                self._lidar.set_motor_pwm(660)
                time.sleep(1)

                scan_generator = self._lidar.start_scan()()

                for measurement in scan_generator:
                    if not self._running:
                        break

                    # Skip invalid readings
                    if measurement.distance <= 0 or measurement.quality <= 0:
                        continue

                    in_arc = self._angle_in_arc(measurement.angle)
                    close  = measurement.distance <= self.min_dist_mm

                    with self._lock:
                        if in_arc:
                            self._blocked = close
                        self._last_scan_time = time.time()

            except Exception as exc:
                logger.error("LidarGuard error: %s — retrying in 2s", exc)
            finally:
                if self._lidar:
                    try:
                        self._lidar.stop()
                        self._lidar.set_motor_pwm(0)
                        self._lidar.disconnect()
                    except Exception:
                        pass
                    self._lidar = None

            if self._running:
                time.sleep(2)
