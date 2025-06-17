#!/bin/bash

# Log file for the script
LOGFILE="/home/pdilab/Desktop/TopologyBuilder/django.log"
PIDFILE="/home/pdilab/Desktop/TopologyBuilder/django.pid"

# Function to check if process is running
is_running() {
    if [ -f "$PIDFILE" ]; then
        pid=$(cat "$PIDFILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Kill existing process if running
if is_running; then
    echo "$(date): Stopping existing Django server..." >> "$LOGFILE"
    pid=$(cat "$PIDFILE")
    kill "$pid"
    rm -f "$PIDFILE"
    sleep 5
fi

# Navigate to the project directory
cd /home/pdilab/Desktop/TopologyBuilder

# Activate the virtual environment
source venv/bin/activate

# Export necessary environment variables
export DJANGO_SETTINGS_MODULE=topo_builder.settings
export PYTHONUNBUFFERED=1

echo "$(date): Starting Django server..." >> "$LOGFILE"

# Start the Django server
nohup python manage.py runserver 0.0.0.0:59001 >> "$LOGFILE" 2>&1 &

# Save the PID
echo $! > "$PIDFILE"

# Wait a few seconds to check if the process is still running
sleep 5
if is_running; then
    echo "$(date): Django server started successfully with PID $(cat $PIDFILE)" >> "$LOGFILE"
else
    echo "$(date): Failed to start Django server" >> "$LOGFILE"
    exit 1
fi
