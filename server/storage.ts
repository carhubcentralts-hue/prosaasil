/**
 * Storage Interface for Hebrew CRM System
 * ממשק אחסון למערכת CRM בעברית
 */

import {
  SelectUser, InsertUser,
  SelectBusiness, InsertBusiness,
  SelectCustomer, InsertCustomer,
  SelectTask, InsertTask,
  SelectAppointment, InsertAppointment,
  SelectWhatsappMessage, InsertWhatsappMessage,
  SelectCallLog, InsertCallLog
} from '@shared/schema';

export interface IStorage {
  // Users
  getUsers(businessId?: number): Promise<SelectUser[]>;
  getUserById(id: number): Promise<SelectUser | null>;
  getUserByUsername(username: string): Promise<SelectUser | null>;
  createUser(user: InsertUser): Promise<SelectUser>;
  updateUser(id: number, updates: Partial<InsertUser>): Promise<SelectUser | null>;
  deleteUser(id: number): Promise<boolean>;

  // Businesses
  getBusinesses(): Promise<SelectBusiness[]>;
  getBusinessById(id: number): Promise<SelectBusiness | null>;
  createBusiness(business: InsertBusiness): Promise<SelectBusiness>;
  updateBusiness(id: number, updates: Partial<InsertBusiness>): Promise<SelectBusiness | null>;
  deleteBusiness(id: number): Promise<boolean>;

  // Customers
  getCustomers(businessId: number): Promise<SelectCustomer[]>;
  getCustomerById(id: number): Promise<SelectCustomer | null>;
  getCustomerByPhone(businessId: number, phone: string): Promise<SelectCustomer | null>;
  createCustomer(customer: InsertCustomer): Promise<SelectCustomer>;
  updateCustomer(id: number, updates: Partial<InsertCustomer>): Promise<SelectCustomer | null>;
  deleteCustomer(id: number): Promise<boolean>;

  // Tasks
  getTasks(businessId: number, customerId?: number): Promise<SelectTask[]>;
  getTaskById(id: number): Promise<SelectTask | null>;
  createTask(task: InsertTask): Promise<SelectTask>;
  updateTask(id: number, updates: Partial<InsertTask>): Promise<SelectTask | null>;
  deleteTask(id: number): Promise<boolean>;

  // Appointments
  getAppointments(businessId: number, customerId?: number): Promise<SelectAppointment[]>;
  getAppointmentById(id: number): Promise<SelectAppointment | null>;
  getAppointmentsByDateRange(
    businessId: number, 
    startDate: Date, 
    endDate: Date
  ): Promise<SelectAppointment[]>;
  createAppointment(appointment: InsertAppointment): Promise<SelectAppointment>;
  updateAppointment(id: number, updates: Partial<InsertAppointment>): Promise<SelectAppointment | null>;
  deleteAppointment(id: number): Promise<boolean>;

  // WhatsApp Messages
  getWhatsappMessages(businessId: number, customerId?: number): Promise<SelectWhatsappMessage[]>;
  getWhatsappMessageById(id: number): Promise<SelectWhatsappMessage | null>;
  createWhatsappMessage(message: InsertWhatsappMessage): Promise<SelectWhatsappMessage>;
  updateWhatsappMessage(id: number, updates: Partial<InsertWhatsappMessage>): Promise<SelectWhatsappMessage | null>;

  // Call Logs
  getCallLogs(businessId: number, customerId?: number): Promise<SelectCallLog[]>;
  getCallLogById(id: number): Promise<SelectCallLog | null>;
  createCallLog(callLog: InsertCallLog): Promise<SelectCallLog>;
  updateCallLog(id: number, updates: Partial<InsertCallLog>): Promise<SelectCallLog | null>;
}

/**
 * In-Memory Storage Implementation for Development
 * מימוש אחסון בזיכרון לפיתוח
 */
export class MemStorage implements IStorage {
  private users: SelectUser[] = [];
  private businesses: SelectBusiness[] = [];
  private customers: SelectCustomer[] = [];
  private tasks: SelectTask[] = [];
  private appointments: SelectAppointment[] = [];
  private whatsappMessages: SelectWhatsappMessage[] = [];
  private callLogs: SelectCallLog[] = [];

  private nextId = {
    users: 1,
    businesses: 1,
    customers: 1,
    tasks: 1,
    appointments: 1,
    whatsappMessages: 1,
    callLogs: 1,
  };

  constructor() {
    this.initSampleData();
  }

  private initSampleData() {
    // Create sample business
    const sampleBusiness: SelectBusiness = {
      id: 1,
      name: 'עסק לדוגמה',
      phone: '03-1234567',
      email: 'info@example.co.il',
      address: 'תל אביב, ישראל',
      description: 'עסק לדוגמה למערכת CRM',
      isActive: true,
      whatsappEnabled: true,
      aiCallsEnabled: true,
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    this.businesses.push(sampleBusiness);
    this.nextId.businesses = 2;

    // Create admin user
    const adminUser: SelectUser = {
      id: 1,
      username: 'שי',
      email: 'admin@example.co.il',
      password: 'hashed_password_here',
      role: 'admin',
      businessId: 1,
      isActive: true,
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    this.users.push(adminUser);
    this.nextId.users = 2;

    // Create sample customers
    const sampleCustomers: SelectCustomer[] = [
      {
        id: 1,
        businessId: 1,
        name: 'יוסי כהן',
        phone: '050-1234567',
        email: 'yossi@example.com',
        address: 'רמת גן',
        notes: 'לקוח VIP',
        status: 'active',
        segment: 'vip',
        lastContact: new Date(),
        createdAt: new Date(),
        updatedAt: new Date(),
      },
      {
        id: 2,
        businessId: 1,
        name: 'שרה לוי',
        phone: '052-7654321',
        email: 'sara@example.com',
        address: 'תל אביב',
        notes: 'לקוחה פוטנציאלית',
        status: 'active',
        segment: 'hot',
        lastContact: new Date(),
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    ];
    this.customers.push(...sampleCustomers);
    this.nextId.customers = 3;

    // Create sample tasks
    const sampleTasks: SelectTask[] = [
      {
        id: 1,
        businessId: 1,
        customerId: 1,
        assignedToUserId: 1,
        title: 'התקשרות למעקב',
        description: 'להתקשר ללקוח לבדיקת שביעות רצון',
        priority: 'high',
        status: 'pending',
        dueDate: new Date(Date.now() + 24 * 60 * 60 * 1000), // Tomorrow
        completedAt: null,
        createdAt: new Date(),
        updatedAt: new Date(),
      }
    ];
    this.tasks.push(...sampleTasks);
    this.nextId.tasks = 2;
  }

  // Users implementation
  async getUsers(businessId?: number): Promise<SelectUser[]> {
    return businessId 
      ? this.users.filter(u => u.businessId === businessId)
      : this.users;
  }

  async getUserById(id: number): Promise<SelectUser | null> {
    return this.users.find(u => u.id === id) || null;
  }

  async getUserByUsername(username: string): Promise<SelectUser | null> {
    return this.users.find(u => u.username === username) || null;
  }

  async createUser(user: InsertUser): Promise<SelectUser> {
    const newUser: SelectUser = {
      id: this.nextId.users++,
      ...user,
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    this.users.push(newUser);
    return newUser;
  }

  async updateUser(id: number, updates: Partial<InsertUser>): Promise<SelectUser | null> {
    const userIndex = this.users.findIndex(u => u.id === id);
    if (userIndex === -1) return null;
    
    this.users[userIndex] = {
      ...this.users[userIndex],
      ...updates,
      updatedAt: new Date(),
    };
    return this.users[userIndex];
  }

  async deleteUser(id: number): Promise<boolean> {
    const userIndex = this.users.findIndex(u => u.id === id);
    if (userIndex === -1) return false;
    
    this.users.splice(userIndex, 1);
    return true;
  }

  // Businesses implementation
  async getBusinesses(): Promise<SelectBusiness[]> {
    return this.businesses;
  }

  async getBusinessById(id: number): Promise<SelectBusiness | null> {
    return this.businesses.find(b => b.id === id) || null;
  }

  async createBusiness(business: InsertBusiness): Promise<SelectBusiness> {
    const newBusiness: SelectBusiness = {
      id: this.nextId.businesses++,
      ...business,
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    this.businesses.push(newBusiness);
    return newBusiness;
  }

  async updateBusiness(id: number, updates: Partial<InsertBusiness>): Promise<SelectBusiness | null> {
    const businessIndex = this.businesses.findIndex(b => b.id === id);
    if (businessIndex === -1) return null;
    
    this.businesses[businessIndex] = {
      ...this.businesses[businessIndex],
      ...updates,
      updatedAt: new Date(),
    };
    return this.businesses[businessIndex];
  }

  async deleteBusiness(id: number): Promise<boolean> {
    const businessIndex = this.businesses.findIndex(b => b.id === id);
    if (businessIndex === -1) return false;
    
    this.businesses.splice(businessIndex, 1);
    return true;
  }

  // Customers implementation
  async getCustomers(businessId: number): Promise<SelectCustomer[]> {
    return this.customers.filter(c => c.businessId === businessId);
  }

  async getCustomerById(id: number): Promise<SelectCustomer | null> {
    return this.customers.find(c => c.id === id) || null;
  }

  async getCustomerByPhone(businessId: number, phone: string): Promise<SelectCustomer | null> {
    return this.customers.find(c => c.businessId === businessId && c.phone === phone) || null;
  }

  async createCustomer(customer: InsertCustomer): Promise<SelectCustomer> {
    const newCustomer: SelectCustomer = {
      id: this.nextId.customers++,
      ...customer,
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    this.customers.push(newCustomer);
    return newCustomer;
  }

  async updateCustomer(id: number, updates: Partial<InsertCustomer>): Promise<SelectCustomer | null> {
    const customerIndex = this.customers.findIndex(c => c.id === id);
    if (customerIndex === -1) return null;
    
    this.customers[customerIndex] = {
      ...this.customers[customerIndex],
      ...updates,
      updatedAt: new Date(),
    };
    return this.customers[customerIndex];
  }

  async deleteCustomer(id: number): Promise<boolean> {
    const customerIndex = this.customers.findIndex(c => c.id === id);
    if (customerIndex === -1) return false;
    
    this.customers.splice(customerIndex, 1);
    return true;
  }

  // Tasks implementation
  async getTasks(businessId: number, customerId?: number): Promise<SelectTask[]> {
    let tasks = this.tasks.filter(t => t.businessId === businessId);
    if (customerId) {
      tasks = tasks.filter(t => t.customerId === customerId);
    }
    return tasks;
  }

  async getTaskById(id: number): Promise<SelectTask | null> {
    return this.tasks.find(t => t.id === id) || null;
  }

  async createTask(task: InsertTask): Promise<SelectTask> {
    const newTask: SelectTask = {
      id: this.nextId.tasks++,
      ...task,
      completedAt: null,
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    this.tasks.push(newTask);
    return newTask;
  }

  async updateTask(id: number, updates: Partial<InsertTask>): Promise<SelectTask | null> {
    const taskIndex = this.tasks.findIndex(t => t.id === id);
    if (taskIndex === -1) return null;
    
    this.tasks[taskIndex] = {
      ...this.tasks[taskIndex],
      ...updates,
      updatedAt: new Date(),
    };
    return this.tasks[taskIndex];
  }

  async deleteTask(id: number): Promise<boolean> {
    const taskIndex = this.tasks.findIndex(t => t.id === id);
    if (taskIndex === -1) return false;
    
    this.tasks.splice(taskIndex, 1);
    return true;
  }

  // Appointments implementation
  async getAppointments(businessId: number, customerId?: number): Promise<SelectAppointment[]> {
    let appointments = this.appointments.filter(a => a.businessId === businessId);
    if (customerId) {
      appointments = appointments.filter(a => a.customerId === customerId);
    }
    return appointments;
  }

  async getAppointmentById(id: number): Promise<SelectAppointment | null> {
    return this.appointments.find(a => a.id === id) || null;
  }

  async getAppointmentsByDateRange(
    businessId: number, 
    startDate: Date, 
    endDate: Date
  ): Promise<SelectAppointment[]> {
    return this.appointments.filter(a => 
      a.businessId === businessId &&
      a.startTime >= startDate &&
      a.startTime <= endDate
    );
  }

  async createAppointment(appointment: InsertAppointment): Promise<SelectAppointment> {
    const newAppointment: SelectAppointment = {
      id: this.nextId.appointments++,
      ...appointment,
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    this.appointments.push(newAppointment);
    return newAppointment;
  }

  async updateAppointment(id: number, updates: Partial<InsertAppointment>): Promise<SelectAppointment | null> {
    const appointmentIndex = this.appointments.findIndex(a => a.id === id);
    if (appointmentIndex === -1) return null;
    
    this.appointments[appointmentIndex] = {
      ...this.appointments[appointmentIndex],
      ...updates,
      updatedAt: new Date(),
    };
    return this.appointments[appointmentIndex];
  }

  async deleteAppointment(id: number): Promise<boolean> {
    const appointmentIndex = this.appointments.findIndex(a => a.id === id);
    if (appointmentIndex === -1) return false;
    
    this.appointments.splice(appointmentIndex, 1);
    return true;
  }

  // WhatsApp Messages implementation
  async getWhatsappMessages(businessId: number, customerId?: number): Promise<SelectWhatsappMessage[]> {
    let messages = this.whatsappMessages.filter(m => m.businessId === businessId);
    if (customerId) {
      messages = messages.filter(m => m.customerId === customerId);
    }
    return messages;
  }

  async getWhatsappMessageById(id: number): Promise<SelectWhatsappMessage | null> {
    return this.whatsappMessages.find(m => m.id === id) || null;
  }

  async createWhatsappMessage(message: InsertWhatsappMessage): Promise<SelectWhatsappMessage> {
    const newMessage: SelectWhatsappMessage = {
      id: this.nextId.whatsappMessages++,
      ...message,
      timestamp: new Date(),
    };
    this.whatsappMessages.push(newMessage);
    return newMessage;
  }

  async updateWhatsappMessage(id: number, updates: Partial<InsertWhatsappMessage>): Promise<SelectWhatsappMessage | null> {
    const messageIndex = this.whatsappMessages.findIndex(m => m.id === id);
    if (messageIndex === -1) return null;
    
    this.whatsappMessages[messageIndex] = {
      ...this.whatsappMessages[messageIndex],
      ...updates,
    };
    return this.whatsappMessages[messageIndex];
  }

  // Call Logs implementation
  async getCallLogs(businessId: number, customerId?: number): Promise<SelectCallLog[]> {
    let callLogs = this.callLogs.filter(c => c.businessId === businessId);
    if (customerId) {
      callLogs = callLogs.filter(c => c.customerId === customerId);
    }
    return callLogs;
  }

  async getCallLogById(id: number): Promise<SelectCallLog | null> {
    return this.callLogs.find(c => c.id === id) || null;
  }

  async createCallLog(callLog: InsertCallLog): Promise<SelectCallLog> {
    const newCallLog: SelectCallLog = {
      id: this.nextId.callLogs++,
      ...callLog,
      createdAt: new Date(),
    };
    this.callLogs.push(newCallLog);
    return newCallLog;
  }

  async updateCallLog(id: number, updates: Partial<InsertCallLog>): Promise<SelectCallLog | null> {
    const callLogIndex = this.callLogs.findIndex(c => c.id === id);
    if (callLogIndex === -1) return null;
    
    this.callLogs[callLogIndex] = {
      ...this.callLogs[callLogIndex],
      ...updates,
    };
    return this.callLogs[callLogIndex];
  }
}

export const storage = new MemStorage();