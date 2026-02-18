#!/usr/bin/env python3
"""
Flask Server for Robot Control via Web Joystick
Designed for Raspberry Pi with Maestro servo controller
"""

from flask import Flask, render_template, request, jsonify
import robotfuncs as rf
import threading
import time
import espeaking

app = Flask(__name__)

# Initialize TTS engine
tts_engine = None
tts_lock = threading.Lock()

def init_tts():
    """Initialize text-to-speech engine"""
    global tts_engine
    try:
        tts_engine = espeaking.Speaker()
        tts_engine.voice = 'en-gb'
        tts_engine.speed = 150
        print("TTS engine initialized with espeakng")
    except Exception as e:
        print(f"Warning: Could not initialize TTS: {e}")

def speak_async(text):
    """Speak text in a separate thread to not block"""
    def _speak():
        with tts_lock:
            if tts_engine:
                try:
                    tts_engine.say(text)
                except Exception as e:
                    print(f"TTS error: {e}")
    
    thread = threading.Thread(target=_speak, daemon=True)
    thread.start()

# Global variables
servo = None
current_x = 0.0  # -1.0 to 1.0 (left to right)
current_y = 0.0  # -1.0 to 1.0 (down to up)
head_h = 6000    # Head horizontal position (4000-8000)
head_v = 6000    # Head vertical position (4000-8000)
waist = 6000     # Waist position (4000-8000)
control_thread = None
running = False

# Deadzone to prevent drift when joystick is near center
DEADZONE = 0.1


def map_joystick_to_servo(value, reversed_dir=False):
    """
    Map joystick value (-1.0 to 1.0) to servo value (5000 to 7000)
    Center (0.0) maps to 6000
    
    Args:
        value: Joystick input from -1.0 to 1.0
        reversed_dir: If True, reverses the mapping direction
    
    Returns:
        Servo position value between 5000 and 7000
    """
    if reversed_dir:
        value = -value
    
    # Map from [-1, 1] to [5000, 7000]
    # -1 -> 5000, 0 -> 6000, 1 -> 7000
    servo_value = int(6000 + (value * 1000))
    
    # Clamp to valid range
    return max(5000, min(7000, servo_value))


def calculate_arcade_drive(x, y):
    """
    Calculate left and right wheel speeds for arcade drive
    
    Args:
        x: Joystick X (-1.0 left to 1.0 right)
        y: Joystick Y (-1.0 down to 1.0 up)
    
    Returns:
        tuple: (left_speed, right_speed) as servo values
    """
    # Apply deadzone
    if abs(x) < DEADZONE:
        x = 0.0
    if abs(y) < DEADZONE:
        y = 0.0
    
    # If joystick is centered, stop
    if x == 0.0 and y == 0.0:
        return (6000, 6000)  # CENTER position
    
    # Arcade drive algorithm
    # Forward/backward: y axis
    # Turn: x axis
    
    # Base speed from Y axis
    forward = y  # Positive y = forward
    turn = x     # Positive x = turn right
    
    # Calculate differential steering
    left = forward - turn  # Swapped to fix backwards steering
    right = forward + turn  # Swapped to fix backwards steering
    
    # Normalize if values exceed range
    max_val = max(abs(left), abs(right))
    if max_val > 1.0:
        left = left / max_val
        right = right / max_val
    
    # Convert to servo values
    left_servo = map_joystick_to_servo(left, reversed_dir=False)
    right_servo = map_joystick_to_servo(right, reversed_dir=True)
    
    return (left_servo, right_servo)


def control_loop():
    """Background thread that continuously updates robot based on joystick position"""
    global running, current_x, current_y, head_h, head_v, waist, servo
    
    print("Control loop started")
    
    while running:
        try:
            # Calculate wheel speeds from joystick position
            left_speed, right_speed = calculate_arcade_drive(current_x, current_y)
            
            # Update robot wheels
            rf.move(servo, "lWheel", left_speed)
            rf.move(servo, "rWheel", right_speed)
            
            # Update head and waist positions
            rf.move(servo, "headH", head_h)
            rf.move(servo, "headV", head_v)
            rf.move(servo, "waist", waist)
            
            # Small delay to prevent overwhelming the servo controller
            time.sleep(0.05)  # 20Hz update rate
            
        except Exception as e:
            print(f"Error in control loop: {e}")
            time.sleep(0.1)
    
    # Stop the robot when loop exits
    print("Control loop stopped - stopping robot")
    rf.stop(servo)


@app.route('/')
def index():
    """Serve the main joystick control page"""
    return render_template('index.html')


@app.route('/api/joystick', methods=['POST'])
def update_joystick():
    """Receive joystick position updates from the web interface"""
    global current_x, current_y
    
    try:
        data = request.get_json()
        current_x = float(data.get('x', 0))
        current_y = float(data.get('y', 0))
        
        # Clamp values to valid range
        current_x = max(-1.0, min(1.0, current_x))
        current_y = max(-1.0, min(1.0, current_y))
        
        return jsonify({
            'status': 'success',
            'x': current_x,
            'y': current_y
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@app.route('/api/sliders', methods=['POST'])
def update_sliders():
    """Receive slider position updates from the web interface"""
    global head_h, head_v, waist
    
    try:
        data = request.get_json()
        
        if 'headH' in data:
            head_h = int(data['headH'])
            head_h = max(4000, min(8000, head_h))
        
        if 'headV' in data:
            head_v = int(data['headV'])
            head_v = max(4000, min(8000, head_v))
        
        if 'waist' in data:
            waist = int(data['waist'])
            waist = max(4000, min(8000, waist))
        
        return jsonify({
            'status': 'success',
            'headH': head_h,
            'headV': head_v,
            'waist': waist
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current robot status"""
    return jsonify({
        'connected': servo is not None,
        'x': current_x,
        'y': current_y,
        'headH': head_h,
        'headV': head_v,
        'waist': waist,
        'running': running
    })


@app.route('/api/stop', methods=['POST'])
def emergency_stop():
    """Emergency stop - center the joystick and stop the robot"""
    global current_x, current_y, head_h, head_v, waist
    
    current_x = 0.0
    current_y = 0.0
    head_h = 6000
    head_v = 6000
    waist = 6000
    
    if servo:
        rf.stop(servo)
        rf.move(servo, "headH", 6000)
        rf.move(servo, "headV", 6000)
        rf.move(servo, "waist", 6000)
    
    return jsonify({'status': 'stopped'})


@app.route('/api/home', methods=['POST'])
def home_robot():
    """Move all servos to center position"""
    if servo:
        rf.home(servo)
        return jsonify({'status': 'homed'})
    
    return jsonify({'status': 'error', 'message': 'Not connected'}), 400


@app.route('/api/voice/<int:line_id>', methods=['POST'])
def play_voice_line(line_id):
    """Play one of four voice lines"""
    voice_lines = {
        1: "Beep boop! I'm not just a robot, I'm a lifestyle.",
        2: "Warning: Cuteness overload detected. Initiating charm protocol.",
        3: "Does this unit have a soul? Because I'm feeling pretty soulful right now.",
        4: "I was told there would be cookies. My sensors detect a distinct lack of cookies."
    }
    
    if line_id in voice_lines:
        speak_async(voice_lines[line_id])
        return jsonify({'status': 'speaking', 'line': voice_lines[line_id]})
    
    return jsonify({'status': 'error', 'message': 'Invalid voice line'}), 400


def initialize_robot():
    """Initialize the robot connection and setup"""
    global servo, running, control_thread
    
    print("Connecting to Maestro controller...")
    servo = rf.connect()
    print("Connected successfully!")
    
    # Set up wheel servos with appropriate speeds
    # Wheels are continuous rotation servos
    rf.setServo(servo, rf.move_list["lWheel"], 0, 0, 4000, 8000)
    rf.setServo(servo, rf.move_list["rWheel"], 0, 0, 4000, 8000)
    
    # Start with robot stopped
    rf.stop(servo)
    
    # Start control loop in background thread
    running = True
    control_thread = threading.Thread(target=control_loop, daemon=True)
    control_thread.start()
    
    print("Robot initialized and ready!")


def shutdown_robot():
    """Clean shutdown of robot"""
    global running, servo, control_thread
    
    print("Shutting down robot...")
    running = False
    
    if control_thread:
        control_thread.join(timeout=2.0)
    
    if servo:
        rf.stop(servo)
        servo.close()
    
    print("Robot shutdown complete")


if __name__ == '__main__':
    try:
        # Initialize TTS
        init_tts()
        
        # Initialize robot
        initialize_robot()
        
        # Start Flask server
        # Use 0.0.0.0 to allow access from other devices on network
        print("\n" + "="*50)
        print("Robot Control Server Starting")
        print("Access from this device: http://localhost:5000")
        print("Access from phone/laptop: http://[PI_IP_ADDRESS]:5000")
        print("="*50 + "\n")
        
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
        
    except KeyboardInterrupt:
        print("\nShutdown requested...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        shutdown_robot()
