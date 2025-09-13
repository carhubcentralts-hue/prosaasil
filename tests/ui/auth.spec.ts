import { test, expect } from '@playwright/test';
import { loginUser, logoutUser, testUsers } from '../utils/auth';

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Start from a clean state
    await page.goto('/');
  });

  test('should redirect to login page when not authenticated', async ({ page }) => {
    await page.goto('/app/admin/overview');
    await expect(page).toHaveURL('/login');
  });

  test('should login successfully with valid admin credentials', async ({ page }) => {
    await loginUser(page, testUsers.admin);
    
    // Should navigate to admin overview
    await expect(page).toHaveURL(/\/app\/(admin\/overview|admin)/);
    
    // Verify admin interface elements
    await expect(page.getByTestId('button-user-menu')).toBeVisible();
    await expect(page.getByText('מנהל המערכת')).toBeVisible();
  });

  test('should show error for invalid credentials', async ({ page }) => {
    await page.goto('/login');
    
    await page.getByTestId('input-email').fill('invalid@example.com');
    await page.getByTestId('input-password').fill('wrongpassword');
    await page.getByTestId('button-login').click();
    
    await expect(page.getByTestId('error-message')).toBeVisible();
    await expect(page.getByTestId('error-message')).toContainText('אימייל או סיסמה שגויים');
  });

  test('should toggle password visibility', async ({ page }) => {
    await page.goto('/login');
    
    const passwordInput = page.getByTestId('input-password');
    const toggleButton = page.getByTestId('button-toggle-password');
    
    // Initially password should be hidden
    await expect(passwordInput).toHaveAttribute('type', 'password');
    
    // Click toggle to show password
    await toggleButton.click();
    await expect(passwordInput).toHaveAttribute('type', 'text');
    
    // Click toggle to hide password again
    await toggleButton.click();
    await expect(passwordInput).toHaveAttribute('type', 'password');
  });

  test('should logout successfully', async ({ page }) => {
    // Login first
    await loginUser(page, testUsers.admin);
    
    // Logout
    await logoutUser(page);
    
    // Should be redirected to login page
    await expect(page).toHaveURL('/login');
  });

  test('should remember form data before submit', async ({ page }) => {
    await page.goto('/login');
    
    const email = 'test@example.com';
    const password = 'testpassword';
    
    await page.getByTestId('input-email').fill(email);
    await page.getByTestId('input-password').fill(password);
    
    // Verify values are retained
    await expect(page.getByTestId('input-email')).toHaveValue(email);
    await expect(page.getByTestId('input-password')).toHaveValue(password);
  });
});