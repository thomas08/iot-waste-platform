#!/bin/bash

# Script to start IoT Waste Platform Dashboard
# Starts both API backend and serves frontend

echo "========================================="
echo "IoT Waste Platform - Dashboard Launcher"
echo "========================================="
echo ""

# Check if in correct directory
if [ ! -f "api/main.py" ]; then
    echo "❌ Error: Please run this script from the dashboard directory"
    echo "   cd dashboard && ./start_dashboard.sh"
    exit 1
fi

# Check if Python dependencies are installed
echo "📦 Checking dependencies..."
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "⚠️  FastAPI not found. Installing dependencies..."
    pip install -r ../requirements.txt
fi

echo "✅ Dependencies OK"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping dashboard..."
    kill $API_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "✅ Dashboard stopped"
    exit 0
}

# Set trap to cleanup on Ctrl+C
trap cleanup SIGINT SIGTERM

# Start API backend
echo "🚀 Starting API backend on http://localhost:8000..."
cd api
python3 main.py &
API_PID=$!
cd ..

# Wait a bit for API to start
sleep 2

# Check if API is running
if ! ps -p $API_PID > /dev/null; then
    echo "❌ Failed to start API backend"
    exit 1
fi

echo "✅ API backend started (PID: $API_PID)"
echo ""

# Start frontend server
echo "🌐 Starting frontend server on http://localhost:8080..."
cd frontend
python3 -m http.server 8080 &
FRONTEND_PID=$!
cd ..

# Wait a bit for frontend to start
sleep 1

# Check if frontend is running
if ! ps -p $FRONTEND_PID > /dev/null; then
    echo "❌ Failed to start frontend server"
    kill $API_PID 2>/dev/null
    exit 1
fi

echo "✅ Frontend server started (PID: $FRONTEND_PID)"
echo ""

echo "========================================="
echo "✅ Dashboard is running!"
echo "========================================="
echo ""
echo "🌐 Open your browser and navigate to:"
echo "   👉 http://localhost:8080"
echo ""
echo "📡 API Documentation available at:"
echo "   👉 http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the dashboard"
echo ""

# Wait for processes
wait
