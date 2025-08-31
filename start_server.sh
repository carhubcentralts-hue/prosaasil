#!/bin/bash
echo "🚀 Starting Hebrew AI Call Center CRM with Gunicorn"
cd /home/runner/workspace
python3 -m gunicorn -k eventlet -w 1 -b 0.0.0.0:5000 main:app --timeout 60
