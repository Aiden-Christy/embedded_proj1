#!/bin/bash
# Quick start script for robot server

echo "=================================="
echo "  Robot Joystick Server Startup"
echo "=================================="
echo ""

# Check if Flask is installed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "⚠️  Flask is not installed!"
    echo "Installing Flask..."
    pip3 install flask
    echo ""
fi

# Check if maestro module exists
if [ ! -f "maestro.py" ]; then
    echo "⚠️  Warning: maestro.py not found in current directory"
    echo "Make sure maestro.py is in the same folder as robot_server.py"
    echo ""
fi

# Check if robotfuncs exists
if [ ! -f "robotfuncs.py" ]; then
    echo "⚠️  Warning: robotfuncs.py not found"
    echo "Make sure robotfuncs.py is in the same folder as robot_server.py"
    echo ""
fi

# Get IP address
IP=$(hostname -I | awk '{print $1}')

echo "🤖 Starting robot server..."
echo ""
echo "Access URLs:"
echo "  Local:   http://localhost:5000"
echo "  Network: http://$IP:5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""
echo "=================================="
echo ""

# Run the server
python3 robot_server.py
