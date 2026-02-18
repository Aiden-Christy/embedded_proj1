import maestro as ms
import time
from tango_class import Tango


try:
    servo = ms.Controller()
except Exception as e:
    print(f"Error establishing controller: {e}")
    exit

print("Maestro Controller Connected...")

#positions = servo.get_positions()
#print("Active Servo Channels:")
#for channel, position in enumerate(positions):
   # print(f" Channel: {channel} at position {position}")
#servo.setSpeed(10,10)
#servo.setAccel(10,5)
#servo.setTarget(10, 3000)

headHorz = 3
headVert = 4

rightShoulderVert = 5
rightShoulderHorz = 6
rightElbow = 7
rightWristSwing = 8
rightWristTwist = 9
rightGripper = 10

leftShoulderVert = 11
leftShoulderHorz = 12
leftElbow = 13
leftWristSwing = 14
leftWristTwist = 15
leftGripper = 16



head = 1
servo.setAccel(head, 5)
servo.setSpeed(head, 25)
servo.setTarget(head, 5000)
servo.setTarget(head, 6000)
servo.setTarget(head, 8000)
time.sleep(2)

#for i in range(0,24):
   # servo.setSpeed(i, 10)
   # servo.setAccel(i,7)
   # servo.setTarget(i, 6000)
   # print(f"Servo num {i} moved")
   # time.sleep(2)
    

time.sleep(3)

x = servo.getPosition(head)

print(f"Servo {head} is at position {x}")


servo.close()

