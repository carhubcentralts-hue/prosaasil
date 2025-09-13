import { Page, expect } from '@playwright/test';

export interface TestUser {
  email: string;
  password: string;
  role: 'admin' | 'manager' | 'business';
}

export const testUsers: Record<string, TestUser> = {
  admin: {
    email: 'admin@shai-realestate.co.il',
    password: 'admin123',
    role: 'admin'
  },
  // Add more test users as needed
};

export async function loginUser(page: Page, user: TestUser) {
  console.log(`🔐 Logging in as ${user.role}: ${user.email}`);
  
  // Navigate to login page
  await page.goto('/login');
  
  // Fill login form
  await page.getByTestId('input-email').fill(user.email);
  await page.getByTestId('input-password').fill(user.password);
  
  // Submit form
  await page.getByTestId('button-login').click();
  
  // Wait for navigation to dashboard
  await page.waitForURL(/\/app\//);
  
  // Verify we're logged in by checking for user menu
  await expect(page.getByTestId('button-user-menu')).toBeVisible();
  
  console.log('✅ Login successful');
}

export async function logoutUser(page: Page) {
  console.log('🚪 Logging out user');
  
  // Open user menu
  await page.getByTestId('button-user-menu').click();
  
  // Click logout
  await page.getByTestId('button-logout-dropdown').click();
  
  // Wait for redirect to login page
  await page.waitForURL('/login');
  
  console.log('✅ Logout successful');
}