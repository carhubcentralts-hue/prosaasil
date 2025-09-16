import os, subprocess, time, threading, requests, fcntl, shutil
from datetime import datetime

BAILEYS_PORT = int(os.getenv("BAILEYS_PORT", "3300"))
ROOT = os.path.dirname(os.path.dirname(__file__))
LOCK_FILE = os.path.join(ROOT, "baileys.pid")

def _find_node_executable():
    """Find node executable with proper validation"""
    # Try common paths and PATH
    node_paths = [
        shutil.which("node"),  # From PATH
        "/usr/bin/node",
        "/usr/local/bin/node",
        "/opt/homebrew/bin/node",  # macOS ARM
        "/nix/store/*/bin/node"    # Nix environments
    ]
    
    for path in node_paths:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            try:
                # Test node version
                result = subprocess.run([path, "--version"], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.startswith('v'):
                    print(f"✅ Found Node.js {result.stdout.strip()} at {path}")
                    return path
            except Exception as e:
                print(f"⚠️ Node test failed for {path}: {e}")
                continue
    
    # Fallback to system node
    print("⚠️ Using fallback 'node' command")
    return "node"

def _setup_node_environment():
    """Setup NODE_PATH and environment for Baileys"""
    env = os.environ.copy()
    
    # Set PORT for Baileys
    env["PORT"] = str(BAILEYS_PORT)
    
    # Setup NODE_PATH dynamically using npm
    node_paths = []
    
    try:
        # Get npm local root (project dependencies)
        result = subprocess.run(['npm', 'root'], cwd=ROOT, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            local_root = result.stdout.strip()
            if os.path.isdir(local_root):
                node_paths.append(local_root)
                print(f"✅ Added npm local root: {local_root}")
    except Exception as e:
        print(f"⚠️ Could not get npm local root: {e}")
    
    try:
        # Get npm global root
        result = subprocess.run(['npm', 'root', '-g'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            global_root = result.stdout.strip() 
            if os.path.isdir(global_root):
                node_paths.append(global_root)
                print(f"✅ Added npm global root: {global_root}")
    except Exception as e:
        print(f"⚠️ Could not get npm global root: {e}")
    
    # Add fallback paths
    fallback_paths = [
        "/home/runner/workspace/node_modules",  # Replit workspace
        os.path.join(ROOT, "node_modules"),  # Local modules
        os.path.join(ROOT, "services", "baileys", "node_modules"),  # Baileys modules
        "/usr/lib/node_modules",
        "/usr/local/lib/node_modules",
        "/opt/homebrew/lib/node_modules",  # macOS ARM
    ]
    
    for path in fallback_paths:
        if os.path.isdir(path) and path not in node_paths:
            node_paths.append(path)
    
    if node_paths:
        env["NODE_PATH"] = ":".join(node_paths)
        print(f"✅ NODE_PATH set: {env['NODE_PATH']}")
    
    # Set memory limits for stability
    env["NODE_OPTIONS"] = "--max-old-space-size=512 --max-semi-space-size=64"
    
    return env

def _healthy():
    """Check if Baileys is healthy with better error reporting"""
    try:
        r = requests.get(f"http://127.0.0.1:{BAILEYS_PORT}/health", timeout=3)
        if r.status_code == 200:
            data = r.json()
            ready = data.get('ready', False)
            print(f"🔍 Baileys health: status={r.status_code}, ready={ready}")
            return True
        else:
            print(f"🔍 Baileys health: status={r.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        # Connection refused - service not running
        return False
    except requests.exceptions.Timeout:
        print("⚠️ Baileys health check timeout")
        return False
    except Exception as e:
        print(f"⚠️ Baileys health check error: {e}")
        return False

def _acquire_lock():
    """Acquire file lock to prevent duplicate Baileys spawns"""
    try:
        lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        
        # Write PID to lock file
        os.write(lock_fd, f"{os.getpid()}\n".encode())
        os.fsync(lock_fd)
        
        print(f"✅ Acquired Baileys lock (PID: {os.getpid()})")
        return lock_fd
    except (OSError, IOError) as e:
        print(f"⚠️ Could not acquire Baileys lock: {e}")
        return None

def _start_once():
    """Start Baileys with comprehensive validation and error handling"""
    baileys_path = os.path.join(ROOT, "services", "baileys")
    server_js = os.path.join(baileys_path, "server.js")
    
    # Validate Baileys directory
    if not os.path.exists(server_js):
        print(f"❌ Baileys server.js not found at: {server_js}")
        return None
    
    # Find and validate node executable
    node_executable = _find_node_executable()
    
    # Setup environment
    env = _setup_node_environment()
    
    # Setup logging
    log_file = os.path.join(ROOT, "server", "baileys.log")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    print(f"🔄 Starting Baileys:")
    print(f"   Node: {node_executable}")
    print(f"   Port: {BAILEYS_PORT}")
    print(f"   Path: {baileys_path}")
    print(f"   Log: {log_file}")
    
    try:
        with open(log_file, "a") as f:
            f.write(f"\n=== Baileys start at {datetime.now()} (PID: {os.getpid()}) ===\n")
            f.write(f"Node: {node_executable}\n")
            f.write(f"Port: {BAILEYS_PORT}\n")
            f.write(f"NODE_PATH: {env.get('NODE_PATH', 'not_set')}\n")
            f.write(f"Working Dir: {baileys_path}\n")
            f.flush()
            
            proc = subprocess.Popen(
                [node_executable, "server.js"],
                cwd=baileys_path,
                env=env,
                stdout=f, 
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid  # Create new process group
            )
            
            print(f"✅ Baileys process started (PID: {proc.pid})")
            return proc
            
    except Exception as e:
        print(f"❌ Failed to start Baileys: {e}")
        import traceback
        traceback.print_exc()
        return None

def ensure_baileys_worker():
    """Ensure Baileys runs in worker process with file locking"""
    # Try to acquire lock first
    lock_fd = _acquire_lock()
    if lock_fd is None:
        print("⚠️ Another process is managing Baileys, skipping...")
        return
    
    def supervisor_loop():
        """Supervisor loop with proper cleanup"""
        proc = None
        consecutive_failures = 0
        max_failures = 5
        
        try:
            while True:
                try:
                    if not _healthy():
                        consecutive_failures += 1
                        print(f"❌ Baileys unhealthy (failures: {consecutive_failures}/{max_failures})")
                        
                        # Clean up existing process
                        if proc and proc.poll() is None:
                            try:
                                print("🔄 Terminating existing Baileys process...")
                                os.killpg(os.getpgid(proc.pid), 15)  # SIGTERM to process group
                                proc.wait(timeout=10)
                            except Exception as e:
                                print(f"⚠️ Process cleanup error: {e}")
                                try:
                                    os.killpg(os.getpgid(proc.pid), 9)  # SIGKILL
                                except:
                                    pass
                        
                        # Start new process
                        proc = _start_once()
                        if proc is None:
                            if consecutive_failures >= max_failures:
                                print(f"❌ Max failures reached ({max_failures}), backing off...")
                                time.sleep(60)  # Longer delay after max failures
                                consecutive_failures = 0
                            else:
                                time.sleep(10)
                            continue
                        
                        # Wait for startup
                        time.sleep(5)
                    else:
                        consecutive_failures = 0  # Reset failure counter
                        time.sleep(5)  # Health check interval
                        
                except KeyboardInterrupt:
                    print("🔄 Baileys supervisor shutting down...")
                    break
                except Exception as e:
                    print(f"❌ Supervisor loop error: {e}")
                    time.sleep(10)
                    
        finally:
            # Cleanup on exit
            if proc and proc.poll() is None:
                try:
                    print("🔄 Cleaning up Baileys process...")
                    os.killpg(os.getpgid(proc.pid), 15)
                    proc.wait(timeout=10)
                except:
                    try:
                        os.killpg(os.getpgid(proc.pid), 9)
                    except:
                        pass
            
            # Release lock
            try:
                os.close(lock_fd)
                os.unlink(LOCK_FILE)
                print("✅ Released Baileys lock")
            except:
                pass
    
    # Start supervisor in daemon thread
    supervisor_thread = threading.Thread(target=supervisor_loop, daemon=True)
    supervisor_thread.start()
    print("✅ Baileys worker supervisor started")

# Legacy function for compatibility
def ensure_baileys():
    """Legacy function - redirects to worker version"""
    print("⚠️ Using legacy ensure_baileys() - prefer ensure_baileys_worker()")
    ensure_baileys_worker()