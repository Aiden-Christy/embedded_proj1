import robotfuncs
import time

def nod_yes(servo, nods=2, offset=1000, step=50, delay=0.02):
    low = robotfuncs.CENTER - offset   # 5000
    high = robotfuncs.CENTER + offset  # 7000

    for _ in range(nods):
        # Nod down
        for pos in range(robotfuncs.CENTER, high, step):
            robotfuncs.moveHeadV(servo, pos)
            time.sleep(delay)
        # Nod up (same distance as down)
        for pos in range(high, robotfuncs.CENTER, -step):
            robotfuncs.moveHeadV(servo, pos)
            time.sleep(delay)

    # Return to center (already there, but just in case)
    robotfuncs.moveHeadV(servo, robotfuncs.CENTER)

def shake_no(servo, shakes=2, offset=1000, step=50, delay=0.01):
    left = robotfuncs.CENTER - offset
    right = robotfuncs.CENTER + offset

    for _ in range(shakes):
        # Shake right
        for pos in range(robotfuncs.CENTER, right, step):
            robotfuncs.moveHeadH(servo, pos)
            time.sleep(delay)
        # Shake left (full sweep, right→left)
        for pos in range(right, left, -step):
            robotfuncs.moveHeadH(servo, pos)
            time.sleep(delay)
        # Return to center
        for pos in range(left, robotfuncs.CENTER, step):
            robotfuncs.moveHeadH(servo, pos)
            time.sleep(delay)

    robotfuncs.moveHeadH(servo, robotfuncs.CENTER)

def raise_arm(servo):
    robotfuncs.move(servo, rShouldV, 8000)


if __name__ == "__main__":
    servo = robotfuncs.connect()
    shake_no(servo)
