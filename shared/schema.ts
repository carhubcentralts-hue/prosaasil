/**
 * Database Schema for Hebrew CRM System
 * סכמת בסיס נתונים למערכת CRM בעברית
 */

import { pgTable, serial, text, timestamp, boolean, integer, uuid, varchar } from 'drizzle-orm/pg-core';
import { createInsertSchema } from 'drizzle-zod';
import { z } from 'zod';

// Users table - טבלת משתמשים
export const users = pgTable('users', {
  id: serial('id').primaryKey(),
  username: varchar('username', { length: 50 }).notNull().unique(),
  email: varchar('email', { length: 100 }).notNull().unique(),
  password: text('password').notNull(),
  role: varchar('role', { length: 20 }).notNull().default('user'), // admin, user, business_owner
  businessId: integer('business_id'),
  isActive: boolean('is_active').notNull().default(true),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});

// Businesses table - טבלת עסקים
export const businesses = pgTable('businesses', {
  id: serial('id').primaryKey(),
  name: varchar('name', { length: 200 }).notNull(),
  phone: varchar('phone', { length: 20 }),
  email: varchar('email', { length: 100 }),
  address: text('address'),
  description: text('description'),
  isActive: boolean('is_active').notNull().default(true),
  whatsappEnabled: boolean('whatsapp_enabled').notNull().default(false),
  aiCallsEnabled: boolean('ai_calls_enabled').notNull().default(false),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});

// Customers table - טבלת לקוחות
export const customers = pgTable('customers', {
  id: serial('id').primaryKey(),
  businessId: integer('business_id').notNull(),
  name: varchar('name', { length: 100 }).notNull(),
  phone: varchar('phone', { length: 20 }),
  email: varchar('email', { length: 100 }),
  address: text('address'),
  notes: text('notes'),
  status: varchar('status', { length: 20 }).notNull().default('active'), // active, inactive, blocked
  segment: varchar('segment', { length: 20 }).default('regular'), // hot, cold, vip, inactive
  lastContact: timestamp('last_contact'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});

// Tasks table - טבלת משימות
export const tasks = pgTable('tasks', {
  id: serial('id').primaryKey(),
  businessId: integer('business_id').notNull(),
  customerId: integer('customer_id'),
  assignedToUserId: integer('assigned_to_user_id'),
  title: varchar('title', { length: 200 }).notNull(),
  description: text('description'),
  priority: varchar('priority', { length: 10 }).notNull().default('medium'), // low, medium, high, urgent
  status: varchar('status', { length: 20 }).notNull().default('pending'), // pending, in_progress, completed, cancelled
  dueDate: timestamp('due_date'),
  completedAt: timestamp('completed_at'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});

// Appointments table - טבלת פגישות
export const appointments = pgTable('appointments', {
  id: serial('id').primaryKey(),
  businessId: integer('business_id').notNull(),
  customerId: integer('customer_id').notNull(),
  userId: integer('user_id'),
  title: varchar('title', { length: 200 }).notNull(),
  description: text('description'),
  startTime: timestamp('start_time').notNull(),
  endTime: timestamp('end_time').notNull(),
  status: varchar('status', { length: 20 }).notNull().default('scheduled'), // scheduled, completed, cancelled, no_show
  location: text('location'),
  reminderSent: boolean('reminder_sent').notNull().default(false),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});

// WhatsApp messages table - טבלת הודעות WhatsApp
export const whatsappMessages = pgTable('whatsapp_messages', {
  id: serial('id').primaryKey(),
  businessId: integer('business_id').notNull(),
  customerId: integer('customer_id'),
  phoneNumber: varchar('phone_number', { length: 20 }).notNull(),
  messageId: varchar('message_id', { length: 100 }),
  direction: varchar('direction', { length: 10 }).notNull(), // inbound, outbound
  messageType: varchar('message_type', { length: 20 }).notNull().default('text'), // text, image, document, voice
  content: text('content'),
  mediaUrl: text('media_url'),
  status: varchar('status', { length: 20 }).notNull().default('sent'), // sent, delivered, read, failed
  timestamp: timestamp('timestamp').defaultNow().notNull(),
});

// Call logs table - טבלת יומן שיחות
export const callLogs = pgTable('call_logs', {
  id: serial('id').primaryKey(),
  businessId: integer('business_id').notNull(),
  customerId: integer('customer_id'),
  phoneNumber: varchar('phone_number', { length: 20 }).notNull(),
  direction: varchar('direction', { length: 10 }).notNull(), // inbound, outbound
  duration: integer('duration'), // in seconds
  status: varchar('status', { length: 20 }).notNull(), // completed, missed, failed, busy
  aiGenerated: boolean('ai_generated').notNull().default(false),
  transcript: text('transcript'),
  summary: text('summary'),
  recordingUrl: text('recording_url'),
  startTime: timestamp('start_time').notNull(),
  endTime: timestamp('end_time'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
});

// Create insert schemas
export const insertUserSchema = createInsertSchema(users).omit({ 
  id: true, 
  createdAt: true, 
  updatedAt: true 
});

export const insertBusinessSchema = createInsertSchema(businesses).omit({ 
  id: true, 
  createdAt: true, 
  updatedAt: true 
});

export const insertCustomerSchema = createInsertSchema(customers).omit({ 
  id: true, 
  createdAt: true, 
  updatedAt: true 
});

export const insertTaskSchema = createInsertSchema(tasks).omit({ 
  id: true, 
  createdAt: true, 
  updatedAt: true,
  completedAt: true 
});

export const insertAppointmentSchema = createInsertSchema(appointments).omit({ 
  id: true, 
  createdAt: true, 
  updatedAt: true 
});

export const insertWhatsappMessageSchema = createInsertSchema(whatsappMessages).omit({ 
  id: true, 
  timestamp: true 
});

export const insertCallLogSchema = createInsertSchema(callLogs).omit({ 
  id: true, 
  createdAt: true 
});

// Type definitions
export type InsertUser = z.infer<typeof insertUserSchema>;
export type InsertBusiness = z.infer<typeof insertBusinessSchema>;
export type InsertCustomer = z.infer<typeof insertCustomerSchema>;
export type InsertTask = z.infer<typeof insertTaskSchema>;
export type InsertAppointment = z.infer<typeof insertAppointmentSchema>;
export type InsertWhatsappMessage = z.infer<typeof insertWhatsappMessageSchema>;
export type InsertCallLog = z.infer<typeof insertCallLogSchema>;

export type SelectUser = typeof users.$inferSelect;
export type SelectBusiness = typeof businesses.$inferSelect;
export type SelectCustomer = typeof customers.$inferSelect;
export type SelectTask = typeof tasks.$inferSelect;
export type SelectAppointment = typeof appointments.$inferSelect;
export type SelectWhatsappMessage = typeof whatsappMessages.$inferSelect;
export type SelectCallLog = typeof callLogs.$inferSelect;