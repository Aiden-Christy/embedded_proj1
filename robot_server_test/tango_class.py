import maestro as ms
import time

"""
Tango — High-level controller for a Pololu Maestro-powered robot.
(original file — only two LIDAR changes added)
"""


class ObstacleError(RuntimeError):
    """Raised when a forward-movement command is blocked by the LIDAR guard."""


class Tango:

    # Channel Mapping
    MOVE_LIST = {
        "waist": 2,
        "lWheel": 1,
        "rWheel": 0,
        "headH": 3,
        "headV": 4,
        "rShoulderV": 5,
        "rShoulderH": 6,
        "rElbow": 7,
        "rWristSwing": 8,
        "rWristTwist": 9,
        "rGripper": 10,
        "lShoulderV": 11,
        "lShoulderH": 12,
        "lElbow": 13,
        "lWristSwing": 14,
        "lWristTwist": 15,
        "lGripper": 16,
    }

    CENTER = 6000

    # Optional safety limits (need to edit)
    LIMITS = {
        # "headH": (4500, 7500),
        # "rElbow": (4000, 8000),
    }

    # ── CHANGE 1 of 2: accept lidar_guard parameter ──────────────────
    def __init__(self, lidar_guard=None):
        try:
            self.servo = ms.Controller()
            print("Connected to Maestro.")
        except Exception as e:
            print(f"Failed to connect: {e}")
            exit(1)
        self._lidar_guard = lidar_guard
    # ─────────────────────────────────────────────────────────────────


    # Utilities
    def _clamp(self, joint, target):
        if joint in self.LIMITS:
            lo, hi = self.LIMITS[joint]
            return max(lo, min(hi, target))
        return target

    def set_servo(self, joint, speed=0, accel=0, minrange=3968, maxrange=8000):
        ch = self.MOVE_LIST[joint]
        self.servo.setSpeed(ch, speed)
        self.servo.setAccel(ch, accel)
        self.servo.setRange(ch, minrange, maxrange)


    # Core Movement
    def move(self, joint, target):
        if joint not in self.MOVE_LIST:
            raise ValueError(f"Unknown joint: {joint}")

        target = self._clamp(joint, target)
        ch = self.MOVE_LIST[joint]
        self.servo.setTarget(ch, target)

    def smooth_move(self, joint, target, step=50, delay=0.02):
        ch = self.MOVE_LIST[joint]
        target = self._clamp(joint, target)

        pos = self.servo.getPosition(ch)

        if pos < target:
            rng = range(pos, target, step)
        else:
            rng = range(pos, target, -step)

        for p in rng:
            self.servo.setTarget(ch, p)
            time.sleep(delay)

        self.servo.setTarget(ch, target)


    # Waiting
    def wait_joint(self, joint):
        ch = self.MOVE_LIST[joint]
        while self.servo.isMoving(ch):
            time.sleep(0.01)

    def wait_all(self):
        while self.servo.getMovingState():
            time.sleep(0.01)


    # Head
    def head_h(self, target):
        self.move("headH", target)

    def head_v(self, target):
        self.move("headV", target)

    def center_head(self):
        self.head_h(self.CENTER)
        self.head_v(self.CENTER)


    # Grippers
    def open_gripper(self, side="r"):
        joint = "rGripper" if side == "r" else "lGripper"
        self.move(joint, 7000)

    def close_gripper(self, side="r"):
        joint = "rGripper" if side == "r" else "lGripper"
        self.move(joint, 5000)


    # Arms
    def arm_neutral(self, side="r"):
        p = "r" if side == "r" else "l"
        for j in ["ShoulderV", "Elbow", "WristSwing", "WristTwist"]:
            self.move(p + j, self.CENTER)
        self.move("rShoulderH", 6500)
        self.move("lShoulderH", 5500)


    # Wheels
    def drive(self, left, right):
        self.move("lWheel", left)
        self.move("rWheel", right)

    def stop(self):
        self.drive(self.CENTER, self.CENTER)

    # ── CHANGE 2 of 2: guard forward() against obstacles ─────────────
    def forward(self, speed=6500):
        if self._lidar_guard is not None and self._lidar_guard.is_blocked():
            raise ObstacleError("forward() refused: obstacle detected by LIDAR.")
        self.drive(speed, 5500)
    # ─────────────────────────────────────────────────────────────────

    def backward(self, speed=5500):
        self.drive(speed, 6500)

    def turn_left(self):
        self.drive(5500, 5500)

    def turn_right(self):
        self.drive(6500, 6500)


    # Poses
    def home(self):
        for joint in self.MOVE_LIST:
            self.move(joint, self.CENTER)
        time.sleep(1)


    # Gestures
    def wave(self, side="r"):
        p = "r" if side == "r" else "l"

        self.arm_neutral(side)
        time.sleep(0.5)

        for _ in range(3):
            self.move(p + "Elbow", 5000)
            time.sleep(0.3)
            self.move(p + "Elbow", 7000)
            time.sleep(0.3)

        self.arm_neutral(side)


    # Demo
    def demo(self):
        print("Running demo...")

        self.home()
        self.center_head()

        self.open_gripper()
        time.sleep(1)
        self.close_gripper()

        self.forward()
        time.sleep(2)
        self.stop()

        self.turn_left()
        time.sleep(1)
        self.stop()

        self.wave()

        print("Demo complete.")
