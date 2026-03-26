"""
action_runner.py
================
Maps dialog action tag names → Tango robot method calls.
Executes actions from a thread-safe queue so Flask routes never block.

LIDAR INTEGRATION
-----------------
Pass a LidarGuard instance to the constructor.  The "forward" action will
refuse to execute (and optionally speak a warning) if an obstacle is detected.
All other movement actions are unaffected — add them to GUARDED_ACTIONS below
if you want the same treatment for backward/turns in the future.
"""

import queue
import threading
import logging
import subprocess
import time

logger = logging.getLogger(__name__)

# Actions that should be blocked when an obstacle is detected ahead.
# Extend this tuple if you want e.g. diagonal moves guarded too.
GUARDED_ACTIONS = ("forward",)


class ActionRunner:

    ACTION_MAP = {
        "head_yes": lambda r, ka: ActionRunner._head_yes(r),
        "head_no":  lambda r, ka: ActionRunner._head_no(r),
        "arm_raise": lambda r, ka: ActionRunner._arm_raise(r),
        "wave":      lambda r, ka: r.wave(side="r"),
        "dance90": lambda r, ka: ActionRunner._dance(r, ka),
        "home":        lambda r, ka: r.home(),
        "center_head": lambda r, ka: r.center_head(),
        "stop":       lambda r, ka: r.stop(),
        "forward":    lambda r, ka: (r.forward(), time.sleep(1), r.stop()),
        "backward":   lambda r, ka: (r.backward(), time.sleep(1), r.stop()),
        "turn_left":  lambda r, ka: (r.turn_left(),  time.sleep(0.6), r.stop()),
        "turn_right": lambda r, ka: (r.turn_right(), time.sleep(0.6), r.stop()),
        "open_gripper":  lambda r, ka: r.open_gripper(),
        "close_gripper": lambda r, ka: r.close_gripper(),
    }

    @staticmethod
    def _head_yes(robot, nods=2, offset=1000, step=50, delay=0.02):
        CENTER = robot.CENTER
        high = CENTER + offset
        for _ in range(nods):
            for pos in range(CENTER, high, step):
                robot.head_v(pos)
                time.sleep(delay)
            for pos in range(high, CENTER, -step):
                robot.head_v(pos)
                time.sleep(delay)
        robot.head_v(CENTER)

    @staticmethod
    def _head_no(robot, shakes=2, offset=1000, step=50, delay=0.01):
        CENTER = robot.CENTER
        left  = CENTER - offset
        right = CENTER + offset
        for _ in range(shakes):
            for pos in range(CENTER, right, step):
                robot.head_h(pos)
                time.sleep(delay)
            for pos in range(right, left, -step):
                robot.head_h(pos)
                time.sleep(delay)
            for pos in range(left, CENTER, step):
                robot.head_h(pos)
                time.sleep(delay)
        robot.head_h(CENTER)

    @staticmethod
    def _arm_raise(robot):
        robot.move("rShoulderV", 8000)
        robot.move("rShoulderH", 8000)
        time.sleep(2)
        robot.arm_neutral(side="r")

    @staticmethod
    def _dance(robot, keep_alive):
        """
        Two spins with arms and head.
        Drive values hardcoded from app.py: RANGE=800, throttle=0, turn=±1
          CW  spin: left=5200, right=6800
          CCW spin: left=6800, right=5200
        """
        # Arms up
        robot.move("rShoulderV", 8000)
        robot.move("lShoulderV", 4000)
        time.sleep(0.5)

        # Spin CW — rotation 1 (2 seconds)
        for _ in range(200):
            robot.drive(5000, 5000)
            if keep_alive:
                keep_alive()
            time.sleep(0.01)
        robot.stop()
        time.sleep(0.3)

        # Head shake
        ActionRunner._head_no(robot, shakes=2)

        # Spin CCW — rotation 2 (2 seconds)
        for _ in range(200):
            robot.drive(7000, 7000)
            if keep_alive:
                keep_alive()
            time.sleep(0.01)
        robot.stop()
        time.sleep(0.3)

        # Head nod
        ActionRunner._head_yes(robot, nods=2)

        # Arms back down
        robot.arm_neutral(side="r")
        robot.arm_neutral(side="l")

    # ------------------------------------------------------------------

    def __init__(self, robot, keep_alive_fn=None, lidar_guard=None):
        """
        Parameters
        ----------
        robot : Tango
            The robot instance.
        keep_alive_fn : callable, optional
            Called periodically during long actions to reset watchdog timers.
        lidar_guard : LidarGuard, optional
            If provided, guarded movement actions are skipped when an
            obstacle is detected.  Pass None to disable LIDAR checking.
        """
        self.robot        = robot
        self._keep_alive  = keep_alive_fn
        self._lidar_guard = lidar_guard
        self._q           = queue.Queue()
        self._thread      = threading.Thread(target=self._worker, daemon=True)
        self._running     = False

    def start(self):
        self._running = True
        self._thread.start()
        logger.info("ActionRunner started.")

    def stop(self):
        self._running = False
        self._q.put(None)
        self._thread.join(timeout=3)
        logger.info("ActionRunner stopped.")

    def enqueue(self, actions: list[str]):
        for action in actions:
            self._q.put(("action", action))

    def enqueue_speak(self, text: str):
        self._q.put(("speak", text))

    def _worker(self):
        while self._running:
            item = self._q.get()
            if item is None:
                break
            kind, payload = item
            if kind == "speak":
                self._do_speak(payload)
            elif kind == "action":
                self._do_action(payload)
            self._q.task_done()

    def _do_speak(self, text: str):
        try:
            subprocess.run(
                ["espeak-ng", "-v", "en", "-s", "150", "-p", "60", text],
                check=True,
                timeout=30,
            )
        except FileNotFoundError:
            logger.error("espeak-ng not found. Install with: sudo apt install espeak-ng")
            print(f"[ROBOT SAYS]: {text}")
        except subprocess.TimeoutExpired:
            logger.warning("espeak-ng timed out for text: %s", text)
        except subprocess.CalledProcessError as exc:
            logger.error("espeak-ng error (return code %d): %s", exc.returncode, text)

    def _do_action(self, name: str):
        # ── LIDAR obstacle check ────────────────────────────────────────
        if name in GUARDED_ACTIONS and self._lidar_guard is not None:
            if self._lidar_guard.is_blocked():
                logger.warning(
                    "ActionRunner: '%s' BLOCKED — obstacle detected by LIDAR.", name
                )
                self._do_speak("I cannot move forward, there is something in the way.")
                return          # ← skip the action entirely
        # ────────────────────────────────────────────────────────────────

        fn = self.ACTION_MAP.get(name)
        if fn is None:
            logger.warning("ActionRunner: no mapping for action '%s', skipped", name)
            return
        try:
            logger.debug("Executing action: %s", name)
            fn(self.robot, self._keep_alive)
        except Exception as exc:
            logger.error("Action '%s' raised: %s", name, exc)
