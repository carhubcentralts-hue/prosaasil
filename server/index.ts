import express from "express";
import cors from "cors";
import { registerRoutes } from "./routes";
import { setupVite } from "./vite";

const app = express();
const PORT = 5000;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Health check endpoint
app.get("/api/health", (req, res) => {
  res.json({ status: "OK", message: "Hebrew CRM API is running" });
});

// Initialize database tables and start server
async function startServer() {
  try {
    // Push database schema
    console.log("📦 Pushing database schema...");
    
    // Register all API routes
    const server = await registerRoutes(app);
    
    // Setup Vite for development
    await setupVite(app, server);
    
    server.listen(PORT, "0.0.0.0", () => {
      console.log(`🚀 מערכת CRM מופעלת על פורט ${PORT}`);
      console.log(`📱 ממשק משתמש: http://localhost:${PORT}`);
      console.log(`🔗 API: http://localhost:${PORT}/api`);
      console.log(`🏥 Health Check: http://localhost:${PORT}/api/health`);
    });
  } catch (error) {
    console.error("❌ Failed to start server:", error);
    process.exit(1);
  }
}

startServer();
