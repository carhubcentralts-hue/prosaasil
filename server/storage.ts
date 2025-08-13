import { type User, type InsertUser, type Business, type Session } from '../shared/schema';
import bcrypt from 'bcrypt';
import crypto from 'crypto';

export interface IStorage {
  // User management
  createUser(user: InsertUser): Promise<User>;
  getUserByEmail(email: string): Promise<User | undefined>;
  getUserById(id: string): Promise<User | undefined>;
  updateUser(id: string, updates: Partial<User>): Promise<User>;
  verifyPassword(password: string, hashedPassword: string): Promise<boolean>;
  
  // Session management
  createSession(userId: string, ipAddress?: string, userAgent?: string): Promise<Session>;
  getSessionByToken(token: string): Promise<Session | undefined>;
  deleteSession(token: string): Promise<void>;
  
  // Password reset
  generateResetToken(email: string): Promise<string | null>;
  resetPassword(token: string, newPassword: string): Promise<boolean>;
  
  // Business management
  getBusinessById(id: string): Promise<Business | undefined>;
  getAllBusinesses(): Promise<Business[]>;
  
  // Admin functions
  getAllUsers(): Promise<User[]>;
  updateUserRole(userId: string, role: string): Promise<User>;
}

export class MemStorage implements IStorage {
  private users: User[] = [];
  private businesses: Business[] = [
    {
      id: 'shai-offices',
      name: 'Shai Real Estate Ltd.',
      nameHebrew: 'שי דירות ומשרדים בע״מ',
      description: 'מתמחים במכירת דירות ומשרדים באזור המרכז',
      phone: '+972-50-123-4567',
      email: 'info@shai-realestate.co.il',
      address: 'רחוב הרצל 45, תל אביב',
      industry: 'real_estate',
      isActive: true,
      createdAt: new Date(),
      updatedAt: new Date(),
    }
  ];
  private sessions: Session[] = [];
  private resetTokens = new Map<string, { email: string; expires: Date }>();

  async createUser(user: InsertUser): Promise<User> {
    const hashedPassword = await bcrypt.hash(user.password, 10);
    const newUser: User = {
      id: crypto.randomUUID(),
      ...user,
      password: hashedPassword,
      isActive: true,
      lastLogin: null,
      resetToken: null,
      resetTokenExpiry: null,
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    this.users.push(newUser);
    return newUser;
  }

  async getUserByEmail(email: string): Promise<User | undefined> {
    return this.users.find(user => user.email === email);
  }

  async getUserById(id: string): Promise<User | undefined> {
    return this.users.find(user => user.id === id);
  }

  async updateUser(id: string, updates: Partial<User>): Promise<User> {
    const userIndex = this.users.findIndex(user => user.id === id);
    if (userIndex === -1) throw new Error('User not found');
    
    this.users[userIndex] = { ...this.users[userIndex], ...updates, updatedAt: new Date() };
    return this.users[userIndex];
  }

  async verifyPassword(password: string, hashedPassword: string): Promise<boolean> {
    return bcrypt.compare(password, hashedPassword);
  }

  async createSession(userId: string, ipAddress?: string, userAgent?: string): Promise<Session> {
    const token = crypto.randomBytes(32).toString('hex');
    const session: Session = {
      id: crypto.randomUUID(),
      userId,
      token,
      expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000), // 7 days
      ipAddress: ipAddress || null,
      userAgent: userAgent || null,
      createdAt: new Date(),
    };
    this.sessions.push(session);
    return session;
  }

  async getSessionByToken(token: string): Promise<Session | undefined> {
    const session = this.sessions.find(s => s.token === token && s.expiresAt > new Date());
    return session;
  }

  async deleteSession(token: string): Promise<void> {
    this.sessions = this.sessions.filter(s => s.token !== token);
  }

  async generateResetToken(email: string): Promise<string | null> {
    const user = await this.getUserByEmail(email);
    if (!user) return null;

    const token = crypto.randomBytes(32).toString('hex');
    const expires = new Date(Date.now() + 60 * 60 * 1000); // 1 hour
    
    this.resetTokens.set(token, { email, expires });
    return token;
  }

  async resetPassword(token: string, newPassword: string): Promise<boolean> {
    const resetData = this.resetTokens.get(token);
    if (!resetData || resetData.expires < new Date()) {
      this.resetTokens.delete(token);
      return false;
    }

    const user = await this.getUserByEmail(resetData.email);
    if (!user) return false;

    const hashedPassword = await bcrypt.hash(newPassword, 10);
    await this.updateUser(user.id, { password: hashedPassword });
    
    this.resetTokens.delete(token);
    return true;
  }

  async getBusinessById(id: string): Promise<Business | undefined> {
    return this.businesses.find(b => b.id === id);
  }

  async getAllBusinesses(): Promise<Business[]> {
    return this.businesses.filter(b => b.isActive);
  }

  async getAllUsers(): Promise<User[]> {
    return this.users;
  }

  async updateUserRole(userId: string, role: string): Promise<User> {
    return this.updateUser(userId, { role });
  }

  // Initialize with default admin user
  async initializeDefaultUsers(): Promise<void> {
    const adminExists = await this.getUserByEmail('admin@shai-realestate.co.il');
    if (!adminExists) {
      await this.createUser({
        email: 'admin@shai-realestate.co.il',
        password: 'admin123456',
        firstName: 'מנהל',
        lastName: 'ראשי',
        role: 'admin',
        businessId: null,
      });
    }

    const businessExists = await this.getUserByEmail('manager@shai-realestate.co.il');
    if (!businessExists) {
      await this.createUser({
        email: 'manager@shai-realestate.co.il',
        password: 'business123456',
        firstName: 'שי',
        lastName: 'כהן',
        role: 'business',
        businessId: 'shai-offices',
      });
    }
  }
}

export const storage = new MemStorage();
// Initialize default users on startup
storage.initializeDefaultUsers();