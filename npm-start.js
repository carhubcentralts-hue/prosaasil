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

// Start Flask server from server directory
const flaskProcess = exec("cd server && python3 main.py", (err, stdout, stderr) => {
  if (err) {
    console.error(colors.red("❌ FLASK FAILED:"), stderr);
    process.exit(1);
  }
  , stdout);
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