# Robot Web Control

Web-based joystick controller for our servo robot using Raspberry Pi.

## What It Does

Control the robot from your phone or laptop with:
- **Joystick** - Drive the robot around
- **Sliders** - Move the head and waist
- **Voice Buttons** - Make the robot talk

## Setup

1. **Install on Raspberry Pi:**
   ```bash
   sudo apt install espeak-ng
   pip3 install flask espeaking --break-system-packages
   ```

2. **Run the server:**
   ```bash
   python3 robot_server.py
   ```

3. **Open on your phone/laptop:**
   ```
   http://[PI_IP_ADDRESS]:5000
   ```

## Controls

- **Joystick**: Up/down = forward/back, left/right = steering
- **Emergency Stop**: Red button - stops everything
- **Sliders**: Control head horizontal, head vertical, and waist
- **Voice Buttons**: 4 different voice lines
- **Home Button**: Return all servos to center

## Requirements

- Raspberry Pi
- Pololu Maestro servo controller
- Robot with servos on channels defined in `robotfuncs.py`

## Files

- `robot_server.py` - Main Flask server
- `templates/index.html` - Web interface
- `robotfuncs.py` - Robot control functions
- `maestro.py` - Maestro controller library

---

Built with Flask and espeaking TTS.
