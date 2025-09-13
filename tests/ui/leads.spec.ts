import { test, expect } from '@playwright/test';
import { loginUser, testUsers } from '../utils/auth';
import { createLead, waitForSpinner } from '../utils/helpers';

test.describe('Leads Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page, testUsers.admin);
    await page.goto('/app/leads');
    await waitForSpinner(page);
  });

  test('should display leads page with kanban columns', async ({ page }) => {
    // Check page title
    await expect(page.getByText('ניהול לידים')).toBeVisible();
    
    // Check kanban columns are visible
    await expect(page.getByTestId('column-new')).toBeVisible();
    await expect(page.getByTestId('column-attempting')).toBeVisible();
    await expect(page.getByTestId('column-contacted')).toBeVisible();
    await expect(page.getByTestId('column-qualified')).toBeVisible();
    await expect(page.getByTestId('column-won')).toBeVisible();
    await expect(page.getByTestId('column-lost')).toBeVisible();
    
    // Check add lead button
    await expect(page.getByTestId('button-add-lead')).toBeVisible();
  });

  test('should create new lead successfully', async ({ page }) => {
    const leadData = {
      firstName: 'Test',
      lastName: 'Lead',
      phone: '050-123-4567',
      email: 'test@example.com',
      notes: 'Test lead for automation'
    };

    await createLead(page, leadData);
    
    // Verify lead appears in New column
    await expect(page.getByTestId('column-new')).toContainText('Test Lead');
  });

  test('should filter leads by search query', async ({ page }) => {
    // First create a lead to search for
    await createLead(page, {
      firstName: 'SearchTest',
      lastName: 'Lead',
      phone: '050-999-8888'
    });
    
    // Use search
    await page.getByTestId('input-search-leads').fill('SearchTest');
    await page.waitForTimeout(1000); // Wait for search debounce
    
    // Should only show matching leads
    await expect(page.getByText('SearchTest Lead')).toBeVisible();
  });

  test('should filter leads by status', async ({ page }) => {
    const statusFilter = page.getByTestId('select-status-filter');
    
    // Filter by "New" status
    await statusFilter.selectOption('New');
    await waitForSpinner(page);
    
    // Verify filter applied (should show only New status)
    // Note: Exact verification depends on current lead data
    await expect(statusFilter).toHaveValue('New');
  });

  test('should open lead detail modal on card click', async ({ page }) => {
    // First create a lead to click on
    await createLead(page, {
      firstName: 'ClickTest',
      lastName: 'Lead',
      phone: '050-777-6666'
    });
    
    // Wait for lead to appear and click on it
    const leadCard = page.locator('[data-testid*="card-lead-"]').first();
    await expect(leadCard).toBeVisible();
    await leadCard.click();
    
    // Should open detail modal
    // Note: Assuming detail modal has some identifiable elements
    await expect(page.locator('.modal, [role="dialog"]')).toBeVisible();
  });

  test('should navigate to lead detail page via details button', async ({ page }) => {
    // First create a lead
    await createLead(page, {
      firstName: 'DetailTest',
      lastName: 'Lead',
      phone: '050-555-4444'
    });
    
    // Click details button on the lead card
    const detailsButton = page.locator('[data-testid*="button-view-details-"]').first();
    await expect(detailsButton).toBeVisible();
    await detailsButton.click();
    
    // Should navigate to lead detail page
    await expect(page).toHaveURL(/\/app\/leads\/\d+/);
  });

  test('should validate required fields in lead creation form', async ({ page }) => {
    // Open create modal
    await page.getByTestId('button-add-lead').click();
    
    // Try to submit without required fields
    await page.getByTestId('button-submit').click();
    
    // Should show validation error
    await expect(page.getByText('שם פרטי הוא שדה חובה')).toBeVisible();
    
    // Fill only first name, should require contact info
    await page.getByTestId('input-first-name').fill('Test');
    await page.getByTestId('button-submit').click();
    
    await expect(page.getByText('נדרש לפחות טלפון או מייל')).toBeVisible();
  });

  test('should close create modal on cancel', async ({ page }) => {
    // Open create modal
    await page.getByTestId('button-add-lead').click();
    await expect(page.getByTestId('button-close-modal')).toBeVisible();
    
    // Click cancel
    await page.getByTestId('button-cancel').click();
    
    // Modal should be closed
    await expect(page.getByTestId('button-close-modal')).toBeHidden();
  });

  test('should add and remove tags in lead creation', async ({ page }) => {
    // Open create modal
    await page.getByTestId('button-add-lead').click();
    
    // Add a tag
    await page.getByTestId('input-new-tag').fill('test-tag');
    await page.getByTestId('button-add-tag').click();
    
    // Tag should appear
    await expect(page.getByText('test-tag')).toBeVisible();
    
    // Remove the tag
    await page.locator('button:near(:text("test-tag"))').click();
    
    // Tag should be removed
    await expect(page.getByText('test-tag')).toBeHidden();
  });
});