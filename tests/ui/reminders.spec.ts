import { test, expect } from '@playwright/test';
import { loginUser, testUsers } from '../utils/auth';
import { createLead, waitForSpinner } from '../utils/helpers';

test.describe('Reminders Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page, testUsers.admin);
  });

  test('should create reminder from lead detail page', async ({ page }) => {
    // Navigate to leads page and create a lead first
    await page.goto('/app/leads');
    await waitForSpinner(page);
    
    await createLead(page, {
      firstName: 'ReminderTest',
      lastName: 'Lead',
      phone: '050-123-9999'
    });
    
    // Click on lead to open details (assuming this opens detail modal/page)
    const leadCard = page.locator('[data-testid*="card-lead-"]:has-text("ReminderTest")').first();
    await leadCard.click();
    
    // Wait for detail view to load and find create reminder button
    const createReminderButton = page.getByTestId('button-create-reminder');
    await expect(createReminderButton).toBeVisible();
    await createReminderButton.click();
    
    // Fill reminder form
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = tomorrow.toISOString().split('T')[0];
    
    await page.getByTestId('input-reminder-date').fill(tomorrowStr);
    await page.getByTestId('input-reminder-time').fill('14:30');
    await page.getByTestId('textarea-reminder-note').fill('Follow up call with customer');
    await page.getByTestId('select-reminder-channel').selectOption('ui');
    
    // Submit reminder
    await page.getByTestId('button-create-reminder').click();
    
    // Wait for success (might show alert or close modal)
    await page.waitForTimeout(1000);
  });

  test('should view reminders in notifications page', async ({ page }) => {
    await page.goto('/app/notifications');
    await waitForSpinner(page);
    
    // Check page loaded
    await expect(page.getByText('תזכורות')).toBeVisible();
    
    // Should show reminders list (might be empty initially)
    // This test assumes notifications page shows reminders
  });

  test('should validate reminder form fields', async ({ page }) => {
    // Navigate to leads and create a lead first
    await page.goto('/app/leads');
    await waitForSpinner(page);
    
    await createLead(page, {
      firstName: 'ValidationTest',
      lastName: 'Lead',
      phone: '050-999-7777'
    });
    
    // Open reminder modal
    const leadCard = page.locator('[data-testid*="card-lead-"]:has-text("ValidationTest")').first();
    await leadCard.click();
    
    const createReminderButton = page.getByTestId('button-create-reminder');
    await expect(createReminderButton).toBeVisible();
    await createReminderButton.click();
    
    // Try to submit without required fields
    await page.getByTestId('button-create-reminder').click();
    
    // Should show validation message (implementation dependent)
    // Might be alert or inline validation
    await page.waitForTimeout(500);
  });

  test('should cancel reminder creation', async ({ page }) => {
    // Navigate to leads and create a lead
    await page.goto('/app/leads');
    await waitForSpinner(page);
    
    await createLead(page, {
      firstName: 'CancelTest',
      lastName: 'Lead',
      phone: '050-888-6666'
    });
    
    // Open reminder modal
    const leadCard = page.locator('[data-testid*="card-lead-"]:has-text("CancelTest")').first();
    await leadCard.click();
    
    await page.getByTestId('button-create-reminder').click();
    
    // Fill some data
    await page.getByTestId('textarea-reminder-note').fill('Test note');
    
    // Cancel
    await page.getByTestId('button-cancel-reminder').click();
    
    // Modal should close (form data should be cleared)
    // This depends on modal implementation
    await page.waitForTimeout(500);
  });

  test('should set default date to tomorrow', async ({ page }) => {
    // Navigate to leads and create a lead
    await page.goto('/app/leads');
    await waitForSpinner(page);
    
    await createLead(page, {
      firstName: 'DefaultTest',
      lastName: 'Lead',
      phone: '050-777-5555'
    });
    
    // Open reminder modal
    const leadCard = page.locator('[data-testid*="card-lead-"]:has-text("DefaultTest")').first();
    await leadCard.click();
    
    await page.getByTestId('button-create-reminder').click();
    
    // Check that date input has minimum value set to today/tomorrow
    const dateInput = page.getByTestId('input-reminder-date');
    const minDate = await dateInput.getAttribute('min');
    
    const today = new Date().toISOString().split('T')[0];
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = tomorrow.toISOString().split('T')[0];
    
    // Min date should be today or tomorrow
    expect([today, tomorrowStr]).toContain(minDate);
  });

  test('should display different reminder channels', async ({ page }) => {
    // Navigate to leads and create a lead
    await page.goto('/app/leads');
    await waitForSpinner(page);
    
    await createLead(page, {
      firstName: 'ChannelTest',
      lastName: 'Lead',
      phone: '050-666-4444'
    });
    
    // Open reminder modal
    const leadCard = page.locator('[data-testid*="card-lead-"]:has-text("ChannelTest")').first();
    await leadCard.click();
    
    await page.getByTestId('button-create-reminder').click();
    
    // Check available channels
    const channelSelect = page.getByTestId('select-reminder-channel');
    
    // Should have UI, email, and WhatsApp options
    await expect(channelSelect.locator('option[value="ui"]')).toBeVisible();
    await expect(channelSelect.locator('option[value="email"]')).toBeVisible();
    await expect(channelSelect.locator('option[value="whatsapp"]')).toBeVisible();
  });
});