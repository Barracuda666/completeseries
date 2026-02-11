#!/bin/bash
# start.sh - Launch CompleteSeries with Python HTTP Server

# Check if Python is installed
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
  # check version
  VER=$(python -V 2>&1 | sed 's/.* \([0-9]\).\([0-9]\).*/\1\2/')
  if [ "$VER" -ge "30" ]; then
      PYTHON_CMD="python"
  fi
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "Error: Python 3 is required but not found."
    exit 1
fi

PORT=8000

# Get local IP
if command -v ip &> /dev/null; then
    IP_ADDR=$(ip route get 1 | awk '{print $7;exit}')
elif command -v ifconfig &> /dev/null; then
    IP_ADDR=$(ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1' |  awk '{print $2}' | head -n 1)
else
    IP_ADDR="localhost"
fi

echo "----------------------------------------------------------------"
echo "Starting Complete Your Series on http://localhost:$PORT"
if [ "$IP_ADDR" != "localhost" ]; then
    echo "                     OR  http://$IP_ADDR:$PORT"
fi
echo "----------------------------------------------------------------"
echo "IMPORTANT: Ensure your Audiobookshelf server allows CORS from:"
echo "           http://localhost:$PORT"
if [ "$IP_ADDR" != "localhost" ]; then
    echo "       AND http://$IP_ADDR:$PORT"
fi
echo "----------------------------------------------------------------"
echo "Press Ctrl+C to stop the server."
echo ""

# Try to open the browser
if command -v xdg-open &> /dev/null; then
    xdg-open "http://localhost:$PORT"
elif command -v open &> /dev/null; then
    open "http://localhost:$PORT"
fi

$PYTHON_CMD server.py $PORT
