
#!/bin/bash
# Kill old processes
pkill -9 -f 'uvicorn|honcho|baileys' 2>/dev/null
sleep 2

# Start the stack
exec honcho start -f Procfile

