import robotfuncs
import time

def nod_yes(servo):
    robotfuncs.moveHeadV(servo, 7000)
    time.sleep(.5)
    robotfuncs.moveHeadV(servo, 5000)
    time.sleep(.5)
    robotfuncs.moveHeadV(servo, 7000)
    time.sleep(.5)
    robotfuncs.moveHeadV(servo, 5000)
    time.sleep(.5)
    robotfuncs.moveHeadV(servo, 6000)  # return to center

if __name__ == "__main__":
    servo = robotfuncs.connect()
    nod_yes(servo)