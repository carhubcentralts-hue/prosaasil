# Testing Framework Documentation

## Overview

This project includes a comprehensive testing framework with both backend API tests and frontend UI tests using Playwright.

## Available Test Commands

### Unified Test Runner
```bash
# Run all tests (backend + frontend)
./run_all_tests.sh

# Run only backend API tests
./run_all_tests.sh backend

# Run only frontend UI tests  
./run_all_tests.sh frontend
```

### Individual Test Runners

#### Backend API Tests
```bash
# Comprehensive curl-based API tests
bash curl_leads_test_suite.sh
```

#### Frontend UI Tests (Playwright)
```bash
# Run all UI tests
npx playwright test

# Run tests with browser visible
npx playwright test --headed

# Debug mode (step through tests)
npx playwright test --debug

# Run specific test file
npx playwright test tests/ui/auth.spec.ts

# Run tests on specific browser
npx playwright test --project=chromium
```

## Test Structure

### Backend Tests (`curl_leads_test_suite.sh`)
- Authentication flow (CSRF, login)
- CRUD operations for leads
- Status updates and bulk operations
- Error handling and validation
- Security testing

### Frontend UI Tests (`tests/ui/`)
- **auth.spec.ts**: Login/logout functionality
- **leads.spec.ts**: Lead management and creation
- **kanban.spec.ts**: Drag-and-drop status changes
- **reminders.spec.ts**: Reminder creation and management
- **navigation.spec.ts**: Page navigation and layout

## Test Configuration

### Environment Variables
```bash
export BASE_URL="http://localhost:5000"
export ADMIN_EMAIL="admin@shai-realestate.co.il"
export ADMIN_PASSWORD="admin123"
```

### Playwright Configuration
- **Config file**: `playwright.config.ts`
- **Browsers**: Chromium, Firefox, WebKit
- **Mobile testing**: Pixel 5, iPhone 12
- **Screenshots**: On failure
- **Video**: On failure
- **Test reports**: HTML, JSON, and console

## Test Data and Utilities

### Helper Functions (`tests/utils/`)
- **auth.ts**: Login/logout utilities
- **helpers.ts**: Form filling, waiting, lead creation

### Test Users
```typescript
const testUsers = {
  admin: {
    email: 'admin@shai-realestate.co.il',
    password: 'admin123',
    role: 'admin'
  }
};
```

## Critical Test Flows

### 1. End-to-End Lead Management
```bash
npx playwright test tests/ui/leads.spec.ts tests/ui/kanban.spec.ts
```

### 2. Authentication and Security
```bash
bash curl_leads_test_suite.sh auth
npx playwright test tests/ui/auth.spec.ts
```

### 3. Reminder System
```bash
npx playwright test tests/ui/reminders.spec.ts
```

## Test Reports and Artifacts

### Report Locations
- **Unified reports**: `test-results/unified_test_report_TIMESTAMP.log`
- **Playwright HTML**: `test-results/html/index.html`
- **Screenshots**: `test-results/`
- **Videos**: `test-results/videos/`

### Opening Reports
```bash
# Open Playwright HTML report
npx playwright show-report

# View unified test report
cat test-results/unified_test_report_*.log
```

## Data-TestId Conventions

All interactive elements include `data-testid` attributes following these patterns:

- **Actions**: `{action}-{target}` (e.g., `button-submit`, `input-email`)
- **Content**: `{type}-{content}` (e.g., `text-username`, `status-payment`)
- **Dynamic**: `{type}-{description}-{id}` (e.g., `card-lead-123`)

## Troubleshooting

### Common Issues

1. **App not running**: Ensure the server is started before running tests
2. **Port conflicts**: Change BASE_URL if using different port
3. **Browser installation**: Run `npx playwright install`
4. **Timeout errors**: Increase timeout in playwright.config.ts

### Debug Mode
```bash
# Debug specific test
npx playwright test --debug tests/ui/auth.spec.ts

# Debug with browser visible
npx playwright test --headed --debug
```

### Test Dependencies
- Node.js (for Playwright)
- curl (for API tests)
- python3 (for JSON parsing in curl tests)

## CI/CD Integration

The test framework is designed for CI/CD with:
- Parallel execution
- Retry on failure
- Comprehensive reporting
- Exit codes for pass/fail

Example CI command:
```bash
# Production test run
CI=true ./run_all_tests.sh
```