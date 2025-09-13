import { chromium, FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  const { baseURL } = config.projects[0].use;
  console.log(`🚀 Starting global setup for ${baseURL}`);
  
  // Create a browser instance to verify the app is running
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  try {
    // Wait for the app to be ready
    await page.goto(baseURL || 'http://localhost:5000', { 
      waitUntil: 'networkidle',
      timeout: 60000 
    });
    
    // Verify health endpoint
    const response = await page.request.get('/healthz');
    if (!response.ok()) {
      throw new Error(`Health check failed: ${response.status()}`);
    }
    
    console.log('✅ App is running and healthy');
  } catch (error) {
    console.error('❌ Global setup failed:', error);
    throw error;
  } finally {
    await browser.close();
  }
}

export default globalSetup;