# Connor Munson & Aiden Christy
# Basic robot functions


import maestro as ms
import time

# Channel Mapping
move_list = {
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


# Connection
def connect():
    try:
        servo = ms.Controller()
        return servo
    except Exception as e:
        print(f"uh oh, no servo: {e}")
        exit(1)


# Servo Configuration
def setServo(servo, channel, speed, acc, minrange, maxrange):
    servo.setAccel(channel, acc)
    servo.setSpeed(channel, speed)
    servo.setRange(channel, minrange, maxrange)


# Core Movement
def move(servo, joint, target):
    if joint not in move_list:
        raise ValueError(f"Unknown joint: {joint}")
    servo.setTarget(move_list[joint], target)


def smoothMove(servo, joint, target, step=50, delay=0.02):
    ch = move_list[joint]
    pos = servo.getPosition(ch)

    if pos < target:
        rng = range(pos, target, step)
    else:
        rng = range(pos, target, -step)

    for p in rng:
        servo.setTarget(ch, p)
        time.sleep(delay)

    servo.setTarget(ch, target)


# Wait Helpers
def wait(servo, joint):
    ch = move_list[joint]
    while servo.isMoving(ch):
        time.sleep(0.01)


def waitAll(servo):
    while servo.getMovingState():
        time.sleep(0.01)


# Head Control
def moveHeadH(servo, target):
    move(servo, "headH", target)


def moveHeadV(servo, target):
    move(servo, "headV", target)


def centerHead(servo):
    moveHeadH(servo, CENTER)
    moveHeadV(servo, CENTER)


# Grippers
def openGripper(servo, side="r"):
    joint = "rGripper" if side == "r" else "lGripper"
    move(servo, joint, 7000)


def closeGripper(servo, side="r"):
    joint = "rGripper" if side == "r" else "lGripper"
    move(servo, joint, 5000)


# Arm Poses
def armNeutral(servo, side="r"):
    prefix = "r" if side == "r" else "l"

    move(servo, f"{prefix}ShoulderV", CENTER)
    move(servo, f"{prefix}ShoulderH", CENTER)
    move(servo, f"{prefix}Elbow", CENTER)
    move(servo, f"{prefix}WristSwing", CENTER)
    move(servo, f"{prefix}WristTwist", CENTER)


# Wheels (continuous servos)
def drive(servo, left, right):
    move(servo, "rWheel", left)
    move(servo, "lWheel", right)


def stop(servo):
    drive(servo, CENTER, CENTER)


def backward(servo, speed=6500):
    drive(servo, 7000, 5000)


def forward(servo, speed=5500):
    drive(servo, 5000, 7000)


def turnLeft(servo):
    drive(servo, 5500, 5500)


def turnRight(servo):
    drive(servo, 6500, 6500)


# Full Body Helpers
def home(servo):
    for joint in move_list:
        move(servo, joint, CENTER)
    time.sleep(1)


# Demo Sequence
def demo(servo):
    print("Running demo...")

    home(servo)
    centerHead(servo)

    openGripper(servo, "r")
    time.sleep(1)
    closeGripper(servo, "r")

    print("Driving forward...")
    forward(servo)
    time.sleep(2)
    stop(servo)

    print("Turning...")
    turnLeft(servo)
    time.sleep(1)
    stop(servo)

    print("Demo complete.")

# Main
if __name__ == "__main__":
    servo = connect()
    demo(servo)
