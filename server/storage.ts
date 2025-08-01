import {
  users,
  businesses,
  businessUsers,
  customers,
  whatsappMessages,
  aiCalls,
  invoices,
  digitalSignatures,
  activities,
  type User,
  type UpsertUser,
  type Business,
  type InsertBusiness,
  type Customer,
  type InsertCustomer,
  type WhatsappMessage,
  type InsertWhatsappMessage,
  type AiCall,
  type InsertAiCall,
  type Invoice,
  type InsertInvoice,
  type DigitalSignature,
  type InsertDigitalSignature,
  type Activity,
} from "../shared/schema";
import { db } from "./db";
import { eq, desc, and, sql } from "drizzle-orm";

// Interface for storage operations
export interface IStorage {
  // User operations
  getUser(id: string): Promise<User | undefined>;
  upsertUser(user: UpsertUser): Promise<User>;
  
  // Business operations
  getBusinesses(): Promise<Business[]>;
  getBusiness(id: number): Promise<Business | undefined>;
  createBusiness(business: InsertBusiness): Promise<Business>;
  updateBusiness(id: number, updates: Partial<InsertBusiness>): Promise<Business>;
  
  // Customer operations
  getCustomers(businessId: number): Promise<Customer[]>;
  getCustomer(id: number): Promise<Customer | undefined>;
  createCustomer(customer: InsertCustomer): Promise<Customer>;
  updateCustomer(id: number, updates: Partial<InsertCustomer>): Promise<Customer>;
  
  // WhatsApp message operations
  getWhatsappMessages(businessId: number): Promise<WhatsappMessage[]>;
  createWhatsappMessage(message: InsertWhatsappMessage): Promise<WhatsappMessage>;
  
  // AI call operations
  getAiCalls(businessId: number): Promise<AiCall[]>;
  createAiCall(call: InsertAiCall): Promise<AiCall>;
  updateAiCall(id: number, updates: Partial<InsertAiCall>): Promise<AiCall>;
  
  // Invoice operations
  getInvoices(businessId: number): Promise<Invoice[]>;
  createInvoice(invoice: InsertInvoice): Promise<Invoice>;
  updateInvoice(id: number, updates: Partial<InsertInvoice>): Promise<Invoice>;
  
  // Digital signature operations
  getDigitalSignatures(businessId: number): Promise<DigitalSignature[]>;
  createDigitalSignature(signature: InsertDigitalSignature): Promise<DigitalSignature>;
  updateDigitalSignature(id: number, updates: Partial<InsertDigitalSignature>): Promise<DigitalSignature>;
  
  // Activity operations
  getActivities(businessId: number, limit?: number): Promise<Activity[]>;
  createActivity(activity: Omit<Activity, 'id' | 'timestamp'>): Promise<Activity>;
  
  // Statistics
  getStats(businessId: number): Promise<{
    totalCustomers: number;
    todayMessages: number;
    aiCalls: number;
    activeCustomers: number;
    totalInvoices: number;
    pendingSignatures: number;
  }>;
}

export class DatabaseStorage implements IStorage {
  // User operations
  async getUser(id: string): Promise<User | undefined> {
    const [user] = await db.select().from(users).where(eq(users.id, id));
    return user;
  }

  async upsertUser(userData: UpsertUser): Promise<User> {
    const [user] = await db
      .insert(users)
      .values(userData)
      .onConflictDoUpdate({
        target: users.id,
        set: {
          ...userData,
          updatedAt: new Date(),
        },
      })
      .returning();
    return user;
  }

  // Business operations
  async getBusinesses(): Promise<Business[]> {
    return await db.select().from(businesses).orderBy(desc(businesses.createdAt));
  }

  async getBusiness(id: number): Promise<Business | undefined> {
    const [business] = await db.select().from(businesses).where(eq(businesses.id, id));
    return business;
  }

  async createBusiness(businessData: InsertBusiness): Promise<Business> {
    const [business] = await db.insert(businesses).values(businessData).returning();
    return business;
  }

  async updateBusiness(id: number, updates: Partial<InsertBusiness>): Promise<Business> {
    const [business] = await db
      .update(businesses)
      .set({ ...updates, updatedAt: new Date() })
      .where(eq(businesses.id, id))
      .returning();
    return business;
  }

  // Customer operations
  async getCustomers(businessId: number): Promise<Customer[]> {
    return await db
      .select()
      .from(customers)
      .where(eq(customers.businessId, businessId))
      .orderBy(desc(customers.createdAt));
  }

  async getCustomer(id: number): Promise<Customer | undefined> {
    const [customer] = await db.select().from(customers).where(eq(customers.id, id));
    return customer;
  }

  async createCustomer(customerData: InsertCustomer): Promise<Customer> {
    const [customer] = await db.insert(customers).values(customerData).returning();
    return customer;
  }

  async updateCustomer(id: number, updates: Partial<InsertCustomer>): Promise<Customer> {
    const [customer] = await db
      .update(customers)
      .set({ ...updates, updatedAt: new Date() })
      .where(eq(customers.id, id))
      .returning();
    return customer;
  }

  // WhatsApp message operations
  async getWhatsappMessages(businessId: number): Promise<WhatsappMessage[]> {
    return await db
      .select()
      .from(whatsappMessages)
      .where(eq(whatsappMessages.businessId, businessId))
      .orderBy(desc(whatsappMessages.timestamp))
      .limit(100);
  }

  async createWhatsappMessage(messageData: InsertWhatsappMessage): Promise<WhatsappMessage> {
    const [message] = await db.insert(whatsappMessages).values(messageData).returning();
    return message;
  }

  // AI call operations
  async getAiCalls(businessId: number): Promise<AiCall[]> {
    return await db
      .select()
      .from(aiCalls)
      .where(eq(aiCalls.businessId, businessId))
      .orderBy(desc(aiCalls.timestamp))
      .limit(50);
  }

  async createAiCall(callData: InsertAiCall): Promise<AiCall> {
    const [call] = await db.insert(aiCalls).values(callData).returning();
    return call;
  }

  async updateAiCall(id: number, updates: Partial<InsertAiCall>): Promise<AiCall> {
    const [call] = await db
      .update(aiCalls)
      .set(updates)
      .where(eq(aiCalls.id, id))
      .returning();
    return call;
  }

  // Invoice operations
  async getInvoices(businessId: number): Promise<Invoice[]> {
    return await db
      .select()
      .from(invoices)
      .where(eq(invoices.businessId, businessId))
      .orderBy(desc(invoices.createdAt));
  }

  async createInvoice(invoiceData: InsertInvoice): Promise<Invoice> {
    const [invoice] = await db.insert(invoices).values(invoiceData).returning();
    return invoice;
  }

  async updateInvoice(id: number, updates: Partial<InsertInvoice>): Promise<Invoice> {
    const [invoice] = await db
      .update(invoices)
      .set(updates)
      .where(eq(invoices.id, id))
      .returning();
    return invoice;
  }

  // Digital signature operations
  async getDigitalSignatures(businessId: number): Promise<DigitalSignature[]> {
    return await db
      .select()
      .from(digitalSignatures)
      .where(eq(digitalSignatures.businessId, businessId))
      .orderBy(desc(digitalSignatures.createdAt));
  }

  async createDigitalSignature(signatureData: InsertDigitalSignature): Promise<DigitalSignature> {
    const [signature] = await db.insert(digitalSignatures).values(signatureData).returning();
    return signature;
  }

  async updateDigitalSignature(id: number, updates: Partial<InsertDigitalSignature>): Promise<DigitalSignature> {
    const [signature] = await db
      .update(digitalSignatures)
      .set(updates)
      .where(eq(digitalSignatures.id, id))
      .returning();
    return signature;
  }

  // Activity operations
  async getActivities(businessId: number, limit: number = 10): Promise<Activity[]> {
    return await db
      .select()
      .from(activities)
      .where(eq(activities.businessId, businessId))
      .orderBy(desc(activities.timestamp))
      .limit(limit);
  }

  async createActivity(activityData: Omit<Activity, 'id' | 'timestamp'>): Promise<Activity> {
    const [activity] = await db.insert(activities).values(activityData).returning();
    return activity;
  }

  // Statistics
  async getStats(businessId: number): Promise<{
    totalCustomers: number;
    todayMessages: number;
    aiCalls: number;
    activeCustomers: number;
    totalInvoices: number;
    pendingSignatures: number;
  }> {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const [stats] = await db
      .select({
        totalCustomers: sql<number>`COUNT(DISTINCT ${customers.id})`,
        todayMessages: sql<number>`COUNT(CASE WHEN ${whatsappMessages.timestamp} >= ${today} THEN 1 END)`,
        aiCalls: sql<number>`COUNT(DISTINCT ${aiCalls.id})`,
        activeCustomers: sql<number>`COUNT(DISTINCT CASE WHEN ${customers.status} = 'active' THEN ${customers.id} END)`,
        totalInvoices: sql<number>`COUNT(DISTINCT ${invoices.id})`,
        pendingSignatures: sql<number>`COUNT(DISTINCT CASE WHEN ${digitalSignatures.status} = 'pending' THEN ${digitalSignatures.id} END)`,
      })
      .from(customers)
      .leftJoin(whatsappMessages, eq(customers.businessId, whatsappMessages.businessId))
      .leftJoin(aiCalls, eq(customers.businessId, aiCalls.businessId))
      .leftJoin(invoices, eq(customers.businessId, invoices.businessId))
      .leftJoin(digitalSignatures, eq(customers.businessId, digitalSignatures.businessId))
      .where(eq(customers.businessId, businessId));

    return {
      totalCustomers: stats.totalCustomers || 0,
      todayMessages: stats.todayMessages || 0,
      aiCalls: stats.aiCalls || 0,
      activeCustomers: stats.activeCustomers || 0,
      totalInvoices: stats.totalInvoices || 0,
      pendingSignatures: stats.pendingSignatures || 0,
    };
  }
}

export const storage = new DatabaseStorage();