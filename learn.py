import maestro as ms 
import time

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

servo.setAccel(0,240)


servo.setSpeed(0, 6)
servo.setSpeed(1, 20)

#for i in range(4000, 8000):
#    servo.setTarget(10, i)
#    time.sleep(.001)


servo.setTarget(0, 5000)

servo.setTarget(1, 7000)

time.sleep(1)

servo.setTarget(0, 6000)
servo.setTarget(1, 6000)

x = servo.getPosition(0)

print(f"Servo on channel 0 is at position {x}")


servo.close()

