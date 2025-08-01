import {
  Customer,
  InsertCustomer,
  WhatsappMessage,
  InsertWhatsappMessage,
  AiCall,
  InsertAiCall,
  Activity
} from "../shared/schema";

// In-memory storage for the CRM system
class MemStorage {
  private customers: Customer[] = [];
  private whatsappMessages: WhatsappMessage[] = [];
  private aiCalls: AiCall[] = [];
  private activities: Activity[] = [];
  
  private nextCustomerId = 1;
  private nextMessageId = 1;
  private nextCallId = 1;
  private nextActivityId = 1;

  constructor() {
    // Initialize with some sample data for demonstration
    this.initializeSampleData();
  }

  private initializeSampleData() {
    // Add some initial customers
    const sampleCustomers: InsertCustomer[] = [
      {
        name: "דוד לוי",
        phone: "050-1234567",
        email: "david@example.com",
        status: "active",
        notes: "לקוח VIP - מעוניין במוצרים חדשים"
      },
      {
        name: "שרה כהן",
        phone: "052-9876543",
        email: "sarah@example.com",
        status: "pending",
        notes: "ממתינה להצעת מחיר"
      },
      {
        name: "מיכאל רוזן",
        phone: "054-5555555",
        email: "michael@example.com",
        status: "active",
        notes: "לקוח קבוע - רוכש מדי חודש"
      }
    ];

    sampleCustomers.forEach(customer => {
      this.createCustomer(customer);
    });
  }

  // Customer methods
  async getCustomers(): Promise<Customer[]> {
    return [...this.customers];
  }

  async getCustomerById(id: number): Promise<Customer | null> {
    return this.customers.find(c => c.id === id) || null;
  }

  async createCustomer(data: InsertCustomer): Promise<Customer> {
    const customer: Customer = {
      id: this.nextCustomerId++,
      ...data,
      createdAt: new Date(),
      updatedAt: new Date()
    };
    
    this.customers.push(customer);
    return customer;
  }

  async updateCustomer(id: number, data: Partial<InsertCustomer>): Promise<Customer | null> {
    const index = this.customers.findIndex(c => c.id === id);
    if (index === -1) return null;

    this.customers[index] = {
      ...this.customers[index],
      ...data,
      updatedAt: new Date()
    };

    return this.customers[index];
  }

  async deleteCustomer(id: number): Promise<boolean> {
    const index = this.customers.findIndex(c => c.id === id);
    if (index === -1) return false;

    this.customers.splice(index, 1);
    
    // Also delete related messages and calls
    this.whatsappMessages = this.whatsappMessages.filter(m => m.customerId !== id);
    this.aiCalls = this.aiCalls.filter(c => c.customerId !== id);
    this.activities = this.activities.filter(a => a.customerId !== id);
    
    return true;
  }

  // WhatsApp methods
  async getWhatsappMessages(): Promise<WhatsappMessage[]> {
    return [...this.whatsappMessages].sort((a, b) => 
      new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  }

  async getCustomerWhatsappMessages(customerId: number): Promise<WhatsappMessage[]> {
    return this.whatsappMessages
      .filter(m => m.customerId === customerId)
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
  }

  async createWhatsappMessage(data: InsertWhatsappMessage): Promise<WhatsappMessage> {
    const message: WhatsappMessage = {
      id: this.nextMessageId++,
      ...data,
      timestamp: new Date()
    };

    this.whatsappMessages.push(message);
    return message;
  }

  // AI Call methods
  async getAiCalls(): Promise<AiCall[]> {
    return [...this.aiCalls].sort((a, b) => 
      new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  }

  async getCustomerAiCalls(customerId: number): Promise<AiCall[]> {
    return this.aiCalls
      .filter(c => c.customerId === customerId)
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  }

  async createAiCall(data: Omit<AiCall, 'id'>): Promise<AiCall> {
    const call: AiCall = {
      id: this.nextCallId++,
      ...data
    };

    this.aiCalls.push(call);
    return call;
  }

  async updateAiCall(id: number, data: Partial<Omit<AiCall, 'id' | 'customerId' | 'customerPhone' | 'timestamp'>>): Promise<AiCall | null> {
    const index = this.aiCalls.findIndex(c => c.id === id);
    if (index === -1) return null;

    this.aiCalls[index] = {
      ...this.aiCalls[index],
      ...data
    };

    return this.aiCalls[index];
  }

  // Activity methods
  async getActivities(): Promise<Activity[]> {
    return [...this.activities].sort((a, b) => 
      new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  }

  async addActivity(data: Omit<Activity, 'id'>): Promise<Activity> {
    const activity: Activity = {
      id: this.nextActivityId++,
      ...data
    };

    this.activities.push(activity);
    return activity;
  }

  // Statistics methods
  async getStats() {
    const totalCustomers = this.customers.length;
    const activeCustomers = this.customers.filter(c => c.status === "active").length;
    
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    const todayMessages = this.whatsappMessages.filter(m => 
      new Date(m.timestamp) >= today
    ).length;
    
    const aiCallsToday = this.aiCalls.filter(c => 
      new Date(c.timestamp) >= today
    ).length;

    return {
      totalCustomers,
      activeCustomers,
      todayMessages,
      aiCalls: aiCallsToday
    };
  }
}

// Storage interface
export interface IStorage {
  // Customer operations
  getCustomers(): Promise<Customer[]>;
  getCustomerById(id: number): Promise<Customer | null>;
  createCustomer(data: InsertCustomer): Promise<Customer>;
  updateCustomer(id: number, data: Partial<InsertCustomer>): Promise<Customer | null>;
  deleteCustomer(id: number): Promise<boolean>;

  // WhatsApp operations
  getWhatsappMessages(): Promise<WhatsappMessage[]>;
  getCustomerWhatsappMessages(customerId: number): Promise<WhatsappMessage[]>;
  createWhatsappMessage(data: InsertWhatsappMessage): Promise<WhatsappMessage>;

  // AI Call operations
  getAiCalls(): Promise<AiCall[]>;
  getCustomerAiCalls(customerId: number): Promise<AiCall[]>;
  createAiCall(data: Omit<AiCall, 'id'>): Promise<AiCall>;
  updateAiCall(id: number, data: Partial<Omit<AiCall, 'id' | 'customerId' | 'customerPhone' | 'timestamp'>>): Promise<AiCall | null>;

  // Activity operations
  getActivities(): Promise<Activity[]>;
  addActivity(data: Omit<Activity, 'id'>): Promise<Activity>;

  // Statistics
  getStats(): Promise<{
    totalCustomers: number;
    activeCustomers: number;
    todayMessages: number;
    aiCalls: number;
  }>;
}

// Export singleton instance
export const storage: IStorage = new MemStorage();
