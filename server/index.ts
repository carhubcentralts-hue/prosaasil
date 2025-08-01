import express from "express";
import cors from "cors";
import { 
  getStats,
  getCustomers, 
  createCustomer, 
  updateCustomer, 
  deleteCustomer,
  getWhatsappMessages,
  sendWhatsappMessage,
  getCustomerMessages,
  getAiCalls,
  startAiCall,
  endAiCall,
  getActivities
} from "./routes";
import { setupVite, serveStatic } from "./vite";

const app = express();
const PORT = 5000;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// API Routes

// Statistics
app.get("/api/stats", getStats);

// Customer routes
app.get("/api/customers", getCustomers);
app.post("/api/customers", createCustomer);
app.put("/api/customers/:id", updateCustomer);
app.delete("/api/customers/:id", deleteCustomer);

// WhatsApp routes
app.get("/api/whatsapp/messages", getWhatsappMessages);
app.get("/api/whatsapp/messages/:customerId", getCustomerMessages);
app.post("/api/whatsapp/send", sendWhatsappMessage);

// AI Call routes
app.get("/api/ai-calls", getAiCalls);
app.post("/api/ai-calls/start", startAiCall);
app.post("/api/ai-calls/:id/end", endAiCall);

// Activity routes
app.get("/api/activities", getActivities);

// Serve static files and setup Vite in development
if (process.env.NODE_ENV === "production") {
  serveStatic(app);
} else {
  setupVite(app);
}

app.listen(PORT, "0.0.0.0", () => {
  console.log(`🚀 מערכת CRM מופעלת על פורט ${PORT}`);
  console.log(`📱 ממשק משתמש: http://localhost:${PORT}`);
  console.log(`🔗 API: http://localhost:${PORT}/api`);
});
