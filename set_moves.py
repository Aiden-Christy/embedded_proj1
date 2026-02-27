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


if __name__ == "__main__":
    servo = robotfuncs.connect()
    nod_yes(servo)
