import type { Express, Request, Response } from "express";
import { createServer, type Server } from "http";
import { storage } from "./storage";
import { 
  insertCustomerSchema, 
  insertWhatsappMessageSchema, 
  insertAiCallSchema 
} from "../shared/schema";
import { z } from "zod";

// Mock business ID for now - in production this would come from auth
const MOCK_BUSINESS_ID = 1;

export async function registerRoutes(app: Express): Promise<Server> {
  // Statistics endpoint
  app.get('/api/stats', async (req: Request, res: Response) => {
    try {
      const stats = await storage.getStats(MOCK_BUSINESS_ID);
      res.json(stats);
    } catch (error) {
      console.error("Error fetching stats:", error);
      res.status(500).json({ message: "Failed to fetch statistics" });
    }
  });

  // Customer endpoints
  app.get('/api/customers', async (req: Request, res: Response) => {
    try {
      const customers = await storage.getCustomers(MOCK_BUSINESS_ID);
      res.json(customers);
    } catch (error) {
      console.error("Error fetching customers:", error);
      res.status(500).json({ message: "Failed to fetch customers" });
    }
  });

  app.post('/api/customers', async (req: Request, res: Response) => {
    try {
      const customerData = insertCustomerSchema.parse({
        ...req.body,
        businessId: MOCK_BUSINESS_ID
      });
      const customer = await storage.createCustomer(customerData);
      
      // Create activity
      await storage.createActivity({
        businessId: MOCK_BUSINESS_ID,
        type: 'customer_added',
        description: `נוסף לקוח חדש: ${customer.name}`,
        customerId: customer.id,
        customerName: customer.name,
        metadata: null
      });
      
      res.status(201).json(customer);
    } catch (error) {
      console.error("Error creating customer:", error);
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid customer data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to create customer" });
    }
  });

  app.put('/api/customers/:id', async (req: Request, res: Response) => {
    try {
      const customerId = parseInt(req.params.id);
      const updates = req.body;
      const customer = await storage.updateCustomer(customerId, updates);
      res.json(customer);
    } catch (error) {
      console.error("Error updating customer:", error);
      res.status(500).json({ message: "Failed to update customer" });
    }
  });

  // WhatsApp endpoints
  app.get('/api/whatsapp/messages', async (req: Request, res: Response) => {
    try {
      const messages = await storage.getWhatsappMessages(MOCK_BUSINESS_ID);
      res.json(messages);
    } catch (error) {
      console.error("Error fetching WhatsApp messages:", error);
      res.status(500).json({ message: "Failed to fetch messages" });
    }
  });

  app.post('/api/whatsapp/send', async (req: Request, res: Response) => {
    try {
      const messageData = insertWhatsappMessageSchema.parse({
        ...req.body,
        businessId: MOCK_BUSINESS_ID,
        direction: 'outbound'
      });
      
      const message = await storage.createWhatsappMessage(messageData);
      
      // Create activity
      await storage.createActivity({
        businessId: MOCK_BUSINESS_ID,
        type: 'whatsapp_sent',
        description: `נשלחה הודעת WhatsApp ל-${messageData.customerPhone}`,
        customerId: messageData.customerId,
        customerName: null,
        metadata: { messageId: message.id }
      });
      
      res.status(201).json(message);
    } catch (error) {
      console.error("Error sending WhatsApp message:", error);
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid message data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to send message" });
    }
  });

  // AI Call endpoints
  app.get('/api/ai-calls', async (req: Request, res: Response) => {
    try {
      const calls = await storage.getAiCalls(MOCK_BUSINESS_ID);
      res.json(calls);
    } catch (error) {
      console.error("Error fetching AI calls:", error);
      res.status(500).json({ message: "Failed to fetch AI calls" });
    }
  });

  app.post('/api/ai-calls/start', async (req: Request, res: Response) => {
    try {
      const callData = insertAiCallSchema.parse({
        ...req.body,
        businessId: MOCK_BUSINESS_ID,
        status: 'initiated'
      });
      
      const call = await storage.createAiCall(callData);
      
      // Create activity
      await storage.createActivity({
        businessId: MOCK_BUSINESS_ID,
        type: 'ai_call_started',
        description: `התחילה שיחת AI ל-${callData.customerPhone}`,
        customerId: callData.customerId,
        customerName: null,
        metadata: { callId: call.id }
      });
      
      res.status(201).json(call);
    } catch (error) {
      console.error("Error starting AI call:", error);
      if (error instanceof z.ZodError) {
        return res.status(400).json({ message: "Invalid call data", errors: error.errors });
      }
      res.status(500).json({ message: "Failed to start AI call" });
    }
  });

  app.put('/api/ai-calls/:id/end', async (req: Request, res: Response) => {
    try {
      const callId = parseInt(req.params.id);
      const { duration, notes, callSummary } = req.body;
      
      const call = await storage.updateAiCall(callId, {
        status: 'ended',
        duration,
        notes,
        callSummary
      });
      
      res.json(call);
    } catch (error) {
      console.error("Error ending AI call:", error);
      res.status(500).json({ message: "Failed to end AI call" });
    }
  });

  // Activity endpoints
  app.get('/api/activities', async (req: Request, res: Response) => {
    try {
      const limit = req.query.limit ? parseInt(req.query.limit as string) : 10;
      const activities = await storage.getActivities(MOCK_BUSINESS_ID, limit);
      res.json(activities);
    } catch (error) {
      console.error("Error fetching activities:", error);
      res.status(500).json({ message: "Failed to fetch activities" });
    }
  });

  // Business management endpoints (for admin)
  app.get('/api/businesses', async (req: Request, res: Response) => {
    try {
      const businesses = await storage.getBusinesses();
      res.json(businesses);
    } catch (error) {
      console.error("Error fetching businesses:", error);
      res.status(500).json({ message: "Failed to fetch businesses" });
    }
  });

  app.post('/api/businesses', async (req: Request, res: Response) => {
    try {
      const business = await storage.createBusiness(req.body);
      res.status(201).json(business);
    } catch (error) {
      console.error("Error creating business:", error);
      res.status(500).json({ message: "Failed to create business" });
    }
  });

  // Invoice endpoints
  app.get('/api/invoices', async (req: Request, res: Response) => {
    try {
      const invoices = await storage.getInvoices(MOCK_BUSINESS_ID);
      res.json(invoices);
    } catch (error) {
      console.error("Error fetching invoices:", error);
      res.status(500).json({ message: "Failed to fetch invoices" });
    }
  });

  app.post('/api/invoices', async (req: Request, res: Response) => {
    try {
      const invoice = await storage.createInvoice({
        ...req.body,
        businessId: MOCK_BUSINESS_ID
      });
      res.status(201).json(invoice);
    } catch (error) {
      console.error("Error creating invoice:", error);
      res.status(500).json({ message: "Failed to create invoice" });
    }
  });

  // Digital signature endpoints
  app.get('/api/signatures', async (req: Request, res: Response) => {
    try {
      const signatures = await storage.getDigitalSignatures(MOCK_BUSINESS_ID);
      res.json(signatures);
    } catch (error) {
      console.error("Error fetching signatures:", error);
      res.status(500).json({ message: "Failed to fetch signatures" });
    }
  });

  app.post('/api/signatures', async (req: Request, res: Response) => {
    try {
      const signature = await storage.createDigitalSignature({
        ...req.body,
        businessId: MOCK_BUSINESS_ID
      });
      res.status(201).json(signature);
    } catch (error) {
      console.error("Error creating signature:", error);
      res.status(500).json({ message: "Failed to create signature" });
    }
  });

  const httpServer = createServer(app);
  return httpServer;
}

// Legacy exports for backwards compatibility
export const getStats = async (req: Request, res: Response) => {
  try {
    const stats = await storage.getStats(MOCK_BUSINESS_ID);
    res.json(stats);
  } catch (error) {
    console.error("Error fetching stats:", error);
    res.status(500).json({ message: "Failed to fetch statistics" });
  }
};

export const getCustomers = async (req: Request, res: Response) => {
  try {
    const customers = await storage.getCustomers(MOCK_BUSINESS_ID);
    res.json(customers);
  } catch (error) {
    console.error("Error fetching customers:", error);
    res.status(500).json({ message: "Failed to fetch customers" });
  }
};

export const createCustomer = async (req: Request, res: Response) => {
  try {
    const customerData = insertCustomerSchema.parse({
      ...req.body,
      businessId: MOCK_BUSINESS_ID
    });
    const customer = await storage.createCustomer(customerData);
    res.status(201).json(customer);
  } catch (error) {
    console.error("Error creating customer:", error);
    res.status(500).json({ message: "Failed to create customer" });
  }
};

export const updateCustomer = async (req: Request, res: Response) => {
  try {
    const customerId = parseInt(req.params.id);
    const customer = await storage.updateCustomer(customerId, req.body);
    res.json(customer);
  } catch (error) {
    console.error("Error updating customer:", error);
    res.status(500).json({ message: "Failed to update customer" });
  }
};

export const deleteCustomer = async (req: Request, res: Response) => {
  // Implement if needed
  res.status(501).json({ message: "Delete customer not implemented" });
};

export const getWhatsappMessages = async (req: Request, res: Response) => {
  try {
    const messages = await storage.getWhatsappMessages(MOCK_BUSINESS_ID);
    res.json(messages);
  } catch (error) {
    console.error("Error fetching messages:", error);
    res.status(500).json({ message: "Failed to fetch messages" });
  }
};

export const sendWhatsappMessage = async (req: Request, res: Response) => {
  try {
    const message = await storage.createWhatsappMessage({
      ...req.body,
      businessId: MOCK_BUSINESS_ID,
      direction: 'outbound'
    });
    res.status(201).json(message);
  } catch (error) {
    console.error("Error sending message:", error);
    res.status(500).json({ message: "Failed to send message" });
  }
};

export const getCustomerMessages = async (req: Request, res: Response) => {
  // Implement if needed
  res.status(501).json({ message: "Get customer messages not implemented" });
};

export const getAiCalls = async (req: Request, res: Response) => {
  try {
    const calls = await storage.getAiCalls(MOCK_BUSINESS_ID);
    res.json(calls);
  } catch (error) {
    console.error("Error fetching calls:", error);
    res.status(500).json({ message: "Failed to fetch calls" });
  }
};

export const startAiCall = async (req: Request, res: Response) => {
  try {
    const call = await storage.createAiCall({
      ...req.body,
      businessId: MOCK_BUSINESS_ID,
      status: 'initiated'
    });
    res.status(201).json(call);
  } catch (error) {
    console.error("Error starting call:", error);
    res.status(500).json({ message: "Failed to start call" });
  }
};

export const endAiCall = async (req: Request, res: Response) => {
  try {
    const callId = parseInt(req.params.id);
    const call = await storage.updateAiCall(callId, {
      status: 'ended',
      ...req.body
    });
    res.json(call);
  } catch (error) {
    console.error("Error ending call:", error);
    res.status(500).json({ message: "Failed to end call" });
  }
};

export const getActivities = async (req: Request, res: Response) => {
  try {
    const limit = req.query.limit ? parseInt(req.query.limit as string) : 10;
    const activities = await storage.getActivities(MOCK_BUSINESS_ID, limit);
    res.json(activities);
  } catch (error) {
    console.error("Error fetching activities:", error);
    res.status(500).json({ message: "Failed to fetch activities" });
  }
};