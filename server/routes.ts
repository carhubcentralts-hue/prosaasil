import type { Express } from "express";
import { createServer, type Server } from "http";
import { storage } from "./storage";
import { loginSchema, resetPasswordSchema, changePasswordSchema } from "../shared/schema";
import { z } from "zod";

export async function registerRoutes(app: Express): Promise<Server> {
  // Middleware to parse JSON
  app.use((req, res, next) => {
    if (req.headers['content-type']?.includes('application/json')) {
      let body = '';
      req.on('data', chunk => body += chunk);
      req.on('end', () => {
        try {
          req.body = JSON.parse(body);
        } catch (e) {
          req.body = {};
        }
        next();
      });
    } else {
      next();
    }
  });

  // Authentication routes
  app.post('/api/auth/login', async (req, res) => {
    try {
      const { email, password } = loginSchema.parse(req.body);
      
      const user = await storage.getUserByEmail(email);
      if (!user || !user.isActive) {
        return res.status(401).json({ error: 'אימייל או סיסמא שגויים' });
      }

      const isValid = await storage.verifyPassword(password, user.password);
      if (!isValid) {
        return res.status(401).json({ error: 'אימייל או סיסמא שגויים' });
      }

      const session = await storage.createSession(
        user.id,
        req.ip,
        req.headers['user-agent']
      );

      // Update last login
      await storage.updateUser(user.id, { lastLogin: new Date() });

      // Set cookie
      res.cookie('auth_token', session.token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days
        sameSite: 'strict'
      });

      const { password: _, ...userWithoutPassword } = user;
      res.json({ 
        user: userWithoutPassword,
        token: session.token
      });
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ error: error.errors[0].message });
      }
      console.error('Login error:', error);
      res.status(500).json({ error: 'שגיאה פנימית בשרת' });
    }
  });

  app.post('/api/auth/logout', async (req, res) => {
    try {
      const token = req.cookies?.auth_token || req.headers.authorization?.replace('Bearer ', '');
      if (token) {
        await storage.deleteSession(token);
      }
      res.clearCookie('auth_token');
      res.json({ message: 'התנתקת בהצלחה' });
    } catch (error) {
      console.error('Logout error:', error);
      res.status(500).json({ error: 'שגיאה פנימית בשרת' });
    }
  });

  app.get('/api/auth/me', async (req, res) => {
    try {
      const token = req.cookies?.auth_token || req.headers.authorization?.replace('Bearer ', '');
      if (!token) {
        return res.status(401).json({ error: 'לא מחובר' });
      }

      const session = await storage.getSessionByToken(token);
      if (!session) {
        return res.status(401).json({ error: 'חיבור לא תקין' });
      }

      const user = await storage.getUserById(session.userId);
      if (!user || !user.isActive) {
        return res.status(401).json({ error: 'משתמש לא קיים' });
      }

      const { password: _, ...userWithoutPassword } = user;
      res.json(userWithoutPassword);
    } catch (error) {
      console.error('Auth check error:', error);
      res.status(500).json({ error: 'שגיאה פנימית בשרת' });
    }
  });

  app.post('/api/auth/forgot-password', async (req, res) => {
    try {
      const { email } = resetPasswordSchema.parse(req.body);
      
      const token = await storage.generateResetToken(email);
      if (token) {
        // In production, send email here
        console.log(`Reset token for ${email}: ${token}`);
        // For demo, return the token
        res.json({ 
          message: 'קישור לאיפוס סיסמא נשלח לאימייל',
          resetToken: token // Remove this in production
        });
      } else {
        res.json({ message: 'אם האימייל קיים במערכת, נשלח קישור לאיפוס סיסמא' });
      }
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ error: error.errors[0].message });
      }
      console.error('Password reset error:', error);
      res.status(500).json({ error: 'שגיאה פנימית בשרת' });
    }
  });

  app.post('/api/auth/reset-password', async (req, res) => {
    try {
      const { token, newPassword } = changePasswordSchema.parse(req.body);
      
      const success = await storage.resetPassword(token, newPassword);
      if (success) {
        res.json({ message: 'סיסמא שונתה בהצלחה' });
      } else {
        res.status(400).json({ error: 'קישור לא תקין או פג תוקף' });
      }
    } catch (error) {
      if (error instanceof z.ZodError) {
        return res.status(400).json({ error: error.errors[0].message });
      }
      console.error('Password change error:', error);
      res.status(500).json({ error: 'שגיאה פנימית בשרת' });
    }
  });

  // Business routes
  app.get('/api/businesses', async (req, res) => {
    try {
      const businesses = await storage.getAllBusinesses();
      res.json(businesses);
    } catch (error) {
      console.error('Get businesses error:', error);
      res.status(500).json({ error: 'שגיאה פנימית בשרת' });
    }
  });

  // Admin routes
  app.get('/api/admin/users', async (req, res) => {
    try {
      // Check if user is admin
      const token = req.cookies?.auth_token || req.headers.authorization?.replace('Bearer ', '');
      const session = await storage.getSessionByToken(token || '');
      const user = session ? await storage.getUserById(session.userId) : null;
      
      if (!user || user.role !== 'admin') {
        return res.status(403).json({ error: 'אין הרשאה' });
      }

      const users = await storage.getAllUsers();
      const usersWithoutPasswords = users.map(({ password, ...user }) => user);
      res.json(usersWithoutPasswords);
    } catch (error) {
      console.error('Get users error:', error);
      res.status(500).json({ error: 'שגיאה פנימית בשרת' });
    }
  });

  // Serve static files for Hebrew audio
  app.get('/static/voice_responses/:filename', (req, res) => {
    const filename = req.params.filename;
    const voiceDir = './server/static/voice_responses';
    res.sendFile(filename, { root: voiceDir });
  });

  // Keep existing webhook routes for call center
  app.post("/webhook/incoming_call", (req, res) => {
    const PUBLIC_HOST = "https://ai-crmd.replit.app";
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>${PUBLIC_HOST}/static/voice_responses/greeting.mp3</Play>
  <Pause length="1"/>
  <Record action="/webhook/handle_recording"
          method="POST"
          maxLength="30"
          timeout="5"
          finishOnKey="*"
          transcribe="false"/>
</Response>`;
    res.set('Content-Type', 'text/xml');
    res.send(xml);
  });

  app.post("/webhook/handle_recording", (req, res) => {
    const PUBLIC_HOST = "https://ai-crmd.replit.app";
    const xml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>${PUBLIC_HOST}/static/voice_responses/listening.mp3</Play>
  <Hangup/>
</Response>`;
    res.set('Content-Type', 'text/xml');
    res.send(xml);
  });

  app.post("/webhook/call_status", (req, res) => {
    res.status(200).send("OK");
  });

  const httpServer = createServer(app);
  return httpServer;
}