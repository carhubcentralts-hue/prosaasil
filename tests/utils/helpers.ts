import { Page, expect } from '@playwright/test';

export async function waitForSpinner(page: Page) {
  // Wait for any loading spinners to disappear
  await page.waitForFunction(() => {
    const spinners = document.querySelectorAll('[class*="animate-spin"]');
    return spinners.length === 0;
  }, { timeout: 10000 });
}

export async function waitForToast(page: Page, message?: string) {
  // Wait for toast notification
  const toast = page.locator('[role="alert"], .toast, [class*="toast"]').first();
  await expect(toast).toBeVisible({ timeout: 5000 });
  
  if (message) {
    await expect(toast).toContainText(message);
  }
  
  // Wait for toast to disappear
  await expect(toast).toBeHidden({ timeout: 10000 });
}

export async function fillForm(page: Page, formData: Record<string, string>) {
  for (const [fieldTestId, value] of Object.entries(formData)) {
    const field = page.getByTestId(fieldTestId);
    await field.fill(value);
  }
}

export async function createLead(page: Page, leadData: {
  firstName: string;
  lastName?: string;
  phone?: string;
  email?: string;
  source?: string;
  status?: string;
  notes?: string;
}) {
  console.log('📝 Creating new lead');
  
  // Open create lead modal
  await page.getByTestId('button-add-lead').click();
  
  // Fill form
  await page.getByTestId('input-first-name').fill(leadData.firstName);
  
  if (leadData.lastName) {
    await page.getByTestId('input-last-name').fill(leadData.lastName);
  }
  
  if (leadData.phone) {
    await page.getByTestId('input-phone').fill(leadData.phone);
  }
  
  if (leadData.email) {
    await page.getByTestId('input-email').fill(leadData.email);
  }
  
  if (leadData.source) {
    await page.getByTestId('select-source').selectOption(leadData.source);
  }
  
  if (leadData.status) {
    await page.getByTestId('select-status').selectOption(leadData.status);
  }
  
  if (leadData.notes) {
    await page.getByTestId('textarea-notes').fill(leadData.notes);
  }
  
  // Submit form
  await page.getByTestId('button-submit').click();
  
  // Wait for modal to close
  await expect(page.getByTestId('button-close-modal')).toBeHidden();
  
  console.log('✅ Lead created successfully');
}

export async function dragAndDrop(page: Page, sourceSelector: string, targetSelector: string) {
  console.log(`🔄 Dragging from ${sourceSelector} to ${targetSelector}`);
  
  const source = page.locator(sourceSelector);
  const target = page.locator(targetSelector);
  
  // Get bounding boxes
  const sourceBox = await source.boundingBox();
  const targetBox = await target.boundingBox();
  
  if (!sourceBox || !targetBox) {
    throw new Error('Could not get bounding boxes for drag and drop');
  }
  
  // Perform drag and drop
  await page.mouse.move(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2);
  await page.mouse.down();
  await page.mouse.move(targetBox.x + targetBox.width / 2, targetBox.y + targetBox.height / 2);
  await page.mouse.up();
  
  console.log('✅ Drag and drop completed');
}