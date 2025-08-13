import { z } from 'zod';

// Types for our entities
export interface User {
  id: string;
  email: string;
  password: string;
  firstName: string;
  lastName: string;
  role: string; // 'admin', 'business', 'user'
  businessId: string | null;
  isActive: boolean;
  lastLogin: Date | null;
  resetToken: string | null;
  resetTokenExpiry: Date | null;
  createdAt: Date;
  updatedAt: Date;
}

export interface Business {
  id: string;
  name: string;
  nameHebrew: string;
  description: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  industry: string | null;
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
}

export interface Session {
  id: string;
  userId: string;
  token: string;
  expiresAt: Date;
  ipAddress: string | null;
  userAgent: string | null;
  createdAt: Date;
}

// Zod schemas for validation
export const insertUserSchema = z.object({
  email: z.string().email('כתובת אימייל לא תקינה'),
  password: z.string().min(6, 'סיסמא חייבת להיות באורך של לפחות 6 תווים'),
  firstName: z.string().min(1, 'שם פרטי נדרש'),
  lastName: z.string().min(1, 'שם משפחה נדרש'),
  role: z.string(),
  businessId: z.string().nullable().optional(),
});

export const loginSchema = z.object({
  email: z.string().email('כתובת אימייל לא תקינה'),
  password: z.string().min(6, 'סיסמא חייבת להיות באורך של לפחות 6 תווים'),
});

export const resetPasswordSchema = z.object({
  email: z.string().email('כתובת אימייל לא תקינה'),
});

export const changePasswordSchema = z.object({
  token: z.string(),
  newPassword: z.string().min(6, 'סיסמא חייבת להיות באורך של לפחות 6 תווים'),
});

// Types
export type InsertUser = z.infer<typeof insertUserSchema>;
export type LoginRequest = z.infer<typeof loginSchema>;
export type ResetPasswordRequest = z.infer<typeof resetPasswordSchema>;
export type ChangePasswordRequest = z.infer<typeof changePasswordSchema>;