const { exec } = require("child_process");

// Simple color functions without chalk dependency
const colors = {
  blue: (str) => `\x1b[34m${str}\x1b[0m`,
  green: (str) => `\x1b[32m${str}\x1b[0m`, 
  red: (str) => `\x1b[31m${str}\x1b[0m`,
  yellow: (str) => `\x1b[33m${str}\x1b[0m`,
  cyan: (str) => `\x1b[36m${str}\x1b[0m`
};

console.log(colors.blue("🚀 Hebrew AI Call Center CRM - Starting Flask Backend"));
console.log(colors.green("=".repeat(50)));

// Start Flask server from server directory
const flaskProcess = exec("cd server && python3 main.py", (err, stdout, stderr) => {
  if (err) {
    console.error(colors.red("❌ FLASK FAILED:"), stderr);
    process.exit(1);
  }
  console.log(colors.green("✅ FLASK STARTED:"), stdout);
});

// Forward Flask output to console
flaskProcess.stdout.on('data', (data) => {
  console.log(colors.cyan("[FLASK]"), data.toString().trim());
});

flaskProcess.stderr.on('data', (data) => {
  console.error(colors.yellow("[FLASK WARN]"), data.toString().trim());
});

// Handle process termination
process.on('SIGINT', () => {
  console.log(colors.yellow("\n👋 Shutting down Flask server..."));
  flaskProcess.kill();
  process.exit(0);
});

console.log(colors.green("✅ Flask backend is starting on http://localhost:5000"));
console.log(colors.blue("📱 React frontend available at http://localhost:3000"));