#!/bin/bash
# Hebrew AI Call Center Production Start Script
# סקריפט הפעלה לייצור

echo "🚀 Starting Hebrew AI Call Center in Production Mode..."

# Set production environment
export FLASK_ENV=production
export FLASK_DEBUG=false
export PYTHONPATH="${PYTHONPATH}:./server"

# Start the Flask server
echo "🌐 Starting Flask server on port 5000..."
cd server
python3 main.py