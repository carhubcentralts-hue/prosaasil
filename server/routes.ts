import { Request, Response } from "express";
import { z } from "zod";
import { storage } from "./storage";
import { insertCustomerSchema, insertWhatsappMessageSchema, insertAiCallSchema } from "../shared/schema";

// Get dashboard statistics
export async function getStats(req: Request, res: Response) {
  try {
    const customers = await storage.getCustomers();
    const messages = await storage.getWhatsappMessages();
    const calls = await storage.getAiCalls();
    
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    const todayMessages = messages.filter(m => m.timestamp >= today).length;
    const aiCallsToday = calls.filter(c => c.timestamp >= today).length;
    const activeCustomers = customers.filter(c => c.status === "active").length;
    
    const stats = {
      totalCustomers: customers.length,
      todayMessages,
      aiCalls: aiCallsToday,
      activeCustomers
    };
    
    res.json(stats);
  } catch (error) {
    console.error("Error getting stats:", error);
    res.status(500).json({ error: "שגיאה בקבלת נתונים סטטיסטיים" });
  }
}

// Customer routes
export async function getCustomers(req: Request, res: Response) {
  try {
    const customers = await storage.getCustomers();
    res.json(customers);
  } catch (error) {
    console.error("Error getting customers:", error);
    res.status(500).json({ error: "שגיאה בקבלת רשימת לקוחות" });
  }
}

export async function createCustomer(req: Request, res: Response) {
  try {
    const validatedData = insertCustomerSchema.parse(req.body);
    const customer = await storage.createCustomer(validatedData);
    
    // Add activity
    await storage.addActivity({
      type: "customer_added",
      description: `לקוח חדש נוסף: ${customer.name}`,
      customerId: customer.id,
      customerName: customer.name,
      timestamp: new Date()
    });
    
    res.status(201).json(customer);
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: "נתונים לא תקינים", details: error.errors });
    } else {
      console.error("Error creating customer:", error);
      res.status(500).json({ error: "שגיאה ביצירת לקוח" });
    }
  }
}

export async function updateCustomer(req: Request, res: Response) {
  try {
    const id = parseInt(req.params.id);
    const validatedData = insertCustomerSchema.parse(req.body);
    const customer = await storage.updateCustomer(id, validatedData);
    
    if (!customer) {
      return res.status(404).json({ error: "לקוח לא נמצא" });
    }
    
    res.json(customer);
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: "נתונים לא תקינים", details: error.errors });
    } else {
      console.error("Error updating customer:", error);
      res.status(500).json({ error: "שגיאה בעדכון לקוח" });
    }
  }
}

export async function deleteCustomer(req: Request, res: Response) {
  try {
    const id = parseInt(req.params.id);
    const success = await storage.deleteCustomer(id);
    
    if (!success) {
      return res.status(404).json({ error: "לקוח לא נמצא" });
    }
    
    res.json({ success: true });
  } catch (error) {
    console.error("Error deleting customer:", error);
    res.status(500).json({ error: "שגיאה במחיקת לקוח" });
  }
}

// WhatsApp routes
export async function getWhatsappMessages(req: Request, res: Response) {
  try {
    const messages = await storage.getWhatsappMessages();
    res.json(messages);
  } catch (error) {
    console.error("Error getting WhatsApp messages:", error);
    res.status(500).json({ error: "שגיאה בקבלת הודעות WhatsApp" });
  }
}

export async function sendWhatsappMessage(req: Request, res: Response) {
  try {
    const validatedData = insertWhatsappMessageSchema.parse(req.body);
    const message = await storage.createWhatsappMessage(validatedData);
    
    // Add activity
    const customer = await storage.getCustomerById(validatedData.customerId);
    if (customer) {
      await storage.addActivity({
        type: "whatsapp_sent",
        description: `הודעה נשלחה ל${customer.name}`,
        customerId: customer.id,
        customerName: customer.name,
        timestamp: new Date()
      });
    }
    
    res.status(201).json(message);
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: "נתונים לא תקינים", details: error.errors });
    } else {
      console.error("Error sending WhatsApp message:", error);
      res.status(500).json({ error: "שגיאה בשליחת הודעה" });
    }
  }
}

export async function getCustomerMessages(req: Request, res: Response) {
  try {
    const customerId = parseInt(req.params.customerId);
    const messages = await storage.getCustomerWhatsappMessages(customerId);
    res.json(messages);
  } catch (error) {
    console.error("Error getting customer messages:", error);
    res.status(500).json({ error: "שגיאה בקבלת הודעות לקוח" });
  }
}

// AI Call routes
export async function getAiCalls(req: Request, res: Response) {
  try {
    const calls = await storage.getAiCalls();
    res.json(calls);
  } catch (error) {
    console.error("Error getting AI calls:", error);
    res.status(500).json({ error: "שגיאה בקבלת שיחות AI" });
  }
}

export async function startAiCall(req: Request, res: Response) {
  try {
    const validatedData = insertAiCallSchema.parse(req.body);
    const call = await storage.createAiCall({
      ...validatedData,
      status: "initiated",
      timestamp: new Date()
    });
    
    // Add activity
    const customer = await storage.getCustomerById(validatedData.customerId);
    if (customer) {
      await storage.addActivity({
        type: "ai_call_started",
        description: `שיחת AI החלה עם ${customer.name}`,
        customerId: customer.id,
        customerName: customer.name,
        timestamp: new Date()
      });
    }
    
    // Simulate call progression
    setTimeout(async () => {
      await storage.updateAiCall(call.id, { status: "connecting" });
    }, 1000);
    
    setTimeout(async () => {
      await storage.updateAiCall(call.id, { status: "active" });
    }, 3000);
    
    res.status(201).json(call);
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: "נתונים לא תקינים", details: error.errors });
    } else {
      console.error("Error starting AI call:", error);
      res.status(500).json({ error: "שגיאה בהתחלת שיחה" });
    }
  }
}

export async function endAiCall(req: Request, res: Response) {
  try {
    const id = parseInt(req.params.id);
    const { notes } = req.body;
    
    const call = await storage.updateAiCall(id, { 
      status: "ended",
      notes,
      duration: Math.floor(Math.random() * 300) + 60 // Mock duration 1-6 minutes
    });
    
    if (!call) {
      return res.status(404).json({ error: "שיחה לא נמצאה" });
    }
    
    // Add activity
    const customer = await storage.getCustomerById(call.customerId);
    if (customer) {
      await storage.addActivity({
        type: "ai_call_ended",
        description: `שיחת AI הסתיימה עם ${customer.name}`,
        customerId: customer.id,
        customerName: customer.name,
        timestamp: new Date()
      });
    }
    
    res.json(call);
  } catch (error) {
    console.error("Error ending AI call:", error);
    res.status(500).json({ error: "שגיאה בסיום שיחה" });
  }
}

// Activity routes
export async function getActivities(req: Request, res: Response) {
  try {
    const activities = await storage.getActivities();
    res.json(activities);
  } catch (error) {
    console.error("Error getting activities:", error);
    res.status(500).json({ error: "שגיאה בקבלת פעילויות" });
  }
}
