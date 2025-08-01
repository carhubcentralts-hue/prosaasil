import { z } from "zod";

// Customer Schema
export const customerSchema = z.object({
  id: z.number(),
  name: z.string(),
  phone: z.string(),
  email: z.string().email().optional(),
  notes: z.string().optional(),
  status: z.enum(["active", "pending", "inactive"]).default("active"),
  createdAt: z.date(),
  updatedAt: z.date(),
});

export const insertCustomerSchema = z.object({
  name: z.string().min(2, "שם חייב להכיל לפחות 2 תווים"),
  phone: z.string().min(9, "מספר טלפון לא תקין"),
  email: z.string().email("כתובת אימייל לא תקינה").optional().or(z.literal("")),
  notes: z.string().optional(),
  status: z.enum(["active", "pending", "inactive"]).default("active"),
});

export type Customer = z.infer<typeof customerSchema>;
export type InsertCustomer = z.infer<typeof insertCustomerSchema>;

// WhatsApp Message Schema
export const whatsappMessageSchema = z.object({
  id: z.number(),
  customerId: z.number(),
  customerPhone: z.string(),
  message: z.string(),
  direction: z.enum(["inbound", "outbound"]),
  timestamp: z.date(),
  status: z.enum(["sent", "delivered", "read", "failed"]).default("sent"),
});

export const insertWhatsappMessageSchema = z.object({
  customerId: z.number(),
  customerPhone: z.string(),
  message: z.string().min(1, "הודעה לא יכולה להיות ריקה"),
  direction: z.enum(["inbound", "outbound"]),
  status: z.enum(["sent", "delivered", "read", "failed"]).default("sent"),
});

export type WhatsappMessage = z.infer<typeof whatsappMessageSchema>;
export type InsertWhatsappMessage = z.infer<typeof insertWhatsappMessageSchema>;

// AI Call Schema
export const aiCallSchema = z.object({
  id: z.number(),
  customerId: z.number(),
  customerPhone: z.string(),
  status: z.enum(["initiated", "connecting", "active", "ended", "failed"]),
  duration: z.number().optional(), // in seconds
  notes: z.string().optional(),
  timestamp: z.date(),
});

export const insertAiCallSchema = z.object({
  customerId: z.number(),
  customerPhone: z.string(),
  notes: z.string().optional(),
});

export type AiCall = z.infer<typeof aiCallSchema>;
export type InsertAiCall = z.infer<typeof insertAiCallSchema>;

// Activity Schema
export const activitySchema = z.object({
  id: z.number(),
  type: z.enum(["customer_added", "whatsapp_sent", "ai_call_started", "ai_call_ended"]),
  description: z.string(),
  customerId: z.number().optional(),
  customerName: z.string().optional(),
  timestamp: z.date(),
});

export type Activity = z.infer<typeof activitySchema>;

// Statistics Schema
export const statsSchema = z.object({
  totalCustomers: z.number(),
  todayMessages: z.number(),
  aiCalls: z.number(),
  activeCustomers: z.number(),
});

export type Stats = z.infer<typeof statsSchema>;
