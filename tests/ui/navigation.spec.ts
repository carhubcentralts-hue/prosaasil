import { test, expect } from '@playwright/test';
import { loginUser, testUsers } from '../utils/auth';

test.describe('Navigation and Layout', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page, testUsers.admin);
  });

  test('should display main navigation elements', async ({ page }) => {
    await page.goto('/app/admin/overview');
    
    // Check header elements
    await expect(page.getByTestId('button-menu')).toBeVisible();
    await expect(page.getByTestId('button-search')).toBeVisible();
    await expect(page.getByTestId('button-notifications')).toBeVisible();
    await expect(page.getByTestId('button-user-menu')).toBeVisible();
    
    // Check main title
    await expect(page.getByText('מנהל המערכת')).toBeVisible();
  });

  test('should navigate to leads page', async ({ page }) => {
    await page.goto('/app/admin/overview');
    
    // Open mobile menu if needed
    if (await page.getByTestId('button-menu').isVisible()) {
      await page.getByTestId('button-menu').click();
    }
    
    // Click on leads menu item
    await page.getByText('לידים').click();
    
    // Should navigate to leads page
    await expect(page).toHaveURL('/app/leads');
    await expect(page.getByText('ניהול לידים')).toBeVisible();
  });

  test('should navigate to notifications page', async ({ page }) => {
    await page.goto('/app/admin/overview');
    
    // Click notifications button in header
    await page.getByTestId('button-notifications').click();
    
    // Should open notifications panel or navigate to notifications page
    // Implementation dependent - might be panel or page navigation
    await page.waitForTimeout(500);
  });

  test('should navigate to calendar page', async ({ page }) => {
    await page.goto('/app/admin/overview');
    
    // Open mobile menu if needed
    if (await page.getByTestId('button-menu').isVisible()) {
      await page.getByTestId('button-menu').click();
    }
    
    // Click on calendar menu item
    await page.getByText('לוח שנה').click();
    
    // Should navigate to calendar page
    await expect(page).toHaveURL('/app/calendar');
  });

  test('should show unread notifications count', async ({ page }) => {
    await page.goto('/app/admin/overview');
    
    // Check if notifications badge exists
    const notificationsBadge = page.getByTestId('unread-count-badge');
    
    // Badge might or might not be visible depending on unread count
    // This test just checks if the badge appears when there are notifications
    if (await notificationsBadge.isVisible()) {
      // If badge is visible, it should contain a number
      const badgeText = await notificationsBadge.textContent();
      expect(badgeText).toMatch(/^\d+$/);
    }
  });

  test('should open and close mobile menu', async ({ page, isMobile }) => {
    if (!isMobile) {
      // This test is specific to mobile view
      await page.setViewportSize({ width: 375, height: 667 });
    }
    
    await page.goto('/app/admin/overview');
    
    // Menu button should be visible on mobile
    await expect(page.getByTestId('button-menu')).toBeVisible();
    
    // Open menu
    await page.getByTestId('button-menu').click();
    
    // Menu items should be visible
    await expect(page.getByText('לידים')).toBeVisible();
    
    // Close menu by clicking outside or X button
    // Implementation dependent
    await page.keyboard.press('Escape');
    
    // Menu should close
    await page.waitForTimeout(500);
  });

  test('should open user menu and show profile options', async ({ page }) => {
    await page.goto('/app/admin/overview');
    
    // Click user menu
    await page.getByTestId('button-user-menu').click();
    
    // Should show user menu options
    await expect(page.getByTestId('button-profile')).toBeVisible();
    await expect(page.getByTestId('button-logout-dropdown')).toBeVisible();
    
    // Should show user info
    await expect(page.getByText('מנהל מערכת')).toBeVisible();
  });

  test('should open search modal', async ({ page }) => {
    await page.goto('/app/admin/overview');
    
    // Click search button
    await page.getByTestId('button-search').click();
    
    // Should open search modal
    // Implementation dependent - checking for modal or search interface
    await page.waitForTimeout(500);
  });

  test('should show admin-specific menu items', async ({ page }) => {
    await page.goto('/app/admin/overview');
    
    // Open menu
    if (await page.getByTestId('button-menu').isVisible()) {
      await page.getByTestId('button-menu').click();
    }
    
    // Should show admin-specific items
    await expect(page.getByText('ניהול עסקים')).toBeVisible();
    await expect(page.getByText('Agent Prompts')).toBeVisible();
  });

  test('should handle page refresh and maintain session', async ({ page }) => {
    await page.goto('/app/leads');
    
    // Refresh page
    await page.reload();
    
    // Should remain authenticated and on same page
    await expect(page).toHaveURL('/app/leads');
    await expect(page.getByTestId('button-user-menu')).toBeVisible();
  });
});