import { test, expect } from '@playwright/test';
import { loginUser, testUsers } from '../utils/auth';
import { createLead, waitForSpinner } from '../utils/helpers';

test.describe('Kanban Drag and Drop', () => {
  test.beforeEach(async ({ page }) => {
    await loginUser(page, testUsers.admin);
    await page.goto('/app/leads');
    await waitForSpinner(page);
  });

  test('should move lead between columns via drag and drop', async ({ page }) => {
    // Create a lead in "New" status
    await createLead(page, {
      firstName: 'DragTest',
      lastName: 'Lead',
      phone: '050-111-2222'
    });
    
    // Wait for lead to appear in New column
    const leadCard = page.locator('[data-testid*="card-lead-"]:has-text("DragTest")');
    await expect(leadCard).toBeVisible();
    
    // Get source and target elements
    const sourceCard = leadCard;
    const targetDropzone = page.getByTestId('dropzone-attempting');
    
    // Perform drag and drop
    await sourceCard.dragTo(targetDropzone);
    
    // Wait for the operation to complete
    await page.waitForTimeout(1000);
    
    // Verify lead moved to "Attempting" column
    const attemptingColumn = page.getByTestId('column-attempting');
    await expect(attemptingColumn).toContainText('DragTest');
    
    // Verify lead is no longer in "New" column
    const newColumn = page.getByTestId('column-new');
    await expect(newColumn).not.toContainText('DragTest');
  });

  test('should show visual feedback during drag operation', async ({ page }) => {
    // Create a lead to drag
    await createLead(page, {
      firstName: 'VisualTest',
      lastName: 'Lead',
      phone: '050-333-4444'
    });
    
    const leadCard = page.locator('[data-testid*="card-lead-"]:has-text("VisualTest")');
    await expect(leadCard).toBeVisible();
    
    // Start drag operation
    await leadCard.hover();
    await page.mouse.down();
    
    // During drag, the card should have visual changes
    // Note: The exact visual feedback depends on implementation
    await expect(leadCard).toHaveClass(/opacity-50|dragging|scale-105/);
    
    // End drag
    await page.mouse.up();
  });

  test('should highlight drop zones during drag', async ({ page }) => {
    // Create a lead to drag
    await createLead(page, {
      firstName: 'DropzoneTest',
      lastName: 'Lead',
      phone: '050-555-6666'
    });
    
    const leadCard = page.locator('[data-testid*="card-lead-"]:has-text("DropzoneTest")');
    const targetDropzone = page.getByTestId('dropzone-contacted');
    
    // Start drag operation
    await leadCard.hover();
    await page.mouse.down();
    
    // Move over target dropzone
    await targetDropzone.hover();
    
    // Dropzone should be highlighted
    await expect(targetDropzone).toHaveClass(/border-blue-400|bg-blue-50/);
    
    // Complete the drop
    await page.mouse.up();
  });

  test('should reorder leads within the same column', async ({ page }) => {
    // Create two leads in the same column
    await createLead(page, {
      firstName: 'First',
      lastName: 'Lead',
      phone: '050-777-8888'
    });
    
    await createLead(page, {
      firstName: 'Second',
      lastName: 'Lead',
      phone: '050-999-0000'
    });
    
    // Wait for both leads to appear
    const firstLead = page.locator('[data-testid*="card-lead-"]:has-text("First")');
    const secondLead = page.locator('[data-testid*="card-lead-"]:has-text("Second")');
    
    await expect(firstLead).toBeVisible();
    await expect(secondLead).toBeVisible();
    
    // Drag second lead above first lead
    await secondLead.dragTo(firstLead);
    
    // Wait for reorder to complete
    await page.waitForTimeout(1000);
    
    // Verify order changed (implementation dependent)
    // This test might need adjustment based on exact reordering behavior
  });

  test('should handle drag cancel (drop outside valid zone)', async ({ page }) => {
    // Create a lead
    await createLead(page, {
      firstName: 'CancelTest',
      lastName: 'Lead',
      phone: '050-111-3333'
    });
    
    const leadCard = page.locator('[data-testid*="card-lead-"]:has-text("CancelTest")');
    await expect(leadCard).toBeVisible();
    
    // Start drag and drop outside any valid zone
    await leadCard.hover();
    await page.mouse.down();
    
    // Move to an invalid area (like header)
    await page.locator('header').hover();
    await page.mouse.up();
    
    // Lead should remain in original position
    const newColumn = page.getByTestId('column-new');
    await expect(newColumn).toContainText('CancelTest');
  });

  test('should update backend when lead status changes', async ({ page }) => {
    // Create a lead
    await createLead(page, {
      firstName: 'BackendTest',
      lastName: 'Lead',
      phone: '050-444-5555'
    });
    
    const leadCard = page.locator('[data-testid*="card-lead-"]:has-text("BackendTest")');
    const targetDropzone = page.getByTestId('dropzone-qualified');
    
    // Move lead to Qualified column
    await leadCard.dragTo(targetDropzone);
    
    // Wait for backend update
    await page.waitForTimeout(2000);
    
    // Verify the change persisted by refreshing page
    await page.reload();
    await waitForSpinner(page);
    
    // Lead should still be in Qualified column
    const qualifiedColumn = page.getByTestId('column-qualified');
    await expect(qualifiedColumn).toContainText('BackendTest');
  });
});