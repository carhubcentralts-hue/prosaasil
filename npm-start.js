const { exec } = require("child_process");

// Simple color functions without chalk dependency
const colors = {
  blue: (str) => `\x1b[34m${str}\x1b[0m`,
  green: (str) => `\x1b[32m${str}\x1b[0m`, 
  red: (str) => `\x1b[31m${str}\x1b[0m`,
  yellow: (str) => `\x1b[33m${str}\x1b[0m`,
  cyan: (str) => `\x1b[36m${str}\x1b[0m`
};

);
));

// Start Flask server with fallback options
let startCommand = "cd server && python3 main.py";

// Fallback to root directory if server/main.py doesn't exist
const fs = require('fs');
if (!fs.existsSync('server/main.py')) {
  console.log(colors.yellow("⚠️  server/main.py not found, using root main.py"));
  startCommand = "python3 main.py";
}

const flaskProcess = exec(startCommand, (err, stdout, stderr) => {
  if (err) {
    console.error(colors.red("❌ FLASK FAILED:"), stderr);
    console.log(colors.blue("💡 Trying alternative startup method..."));
    
    // Try the universal startup script as fallback
    const fallbackProcess = exec("python3 start.py", (fallbackErr, fallbackStdout, fallbackStderr) => {
      if (fallbackErr) {
        console.error(colors.red("❌ FALLBACK FAILED:"), fallbackStderr);
        process.exit(1);
      }
      console.log(colors.green("✅ Started with fallback method:"), fallbackStdout);
    });
    
    return;
  }
  console.log(colors.green("✅ Flask started successfully:"), stdout);
});

// Forward Flask output to console
flaskProcess.stdout.on('data', (data) => {
  , data.toString().trim());
});

flaskProcess.stderr.on('data', (data) => {
  console.error(colors.yellow("[FLASK WARN]"), data.toString().trim());
});

// Handle process termination
process.on('SIGINT', () => {
  );
  flaskProcess.kill();
  process.exit(0);
});

);
);