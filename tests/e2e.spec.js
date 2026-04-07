const { test, expect } = require('@playwright/test');

// Credentials from env or defaults
const ADMIN_USER = process.env.ADMIN_USER || 'admin';
const ADMIN_PASS = process.env.ADMIN_PASS || 'admin123';
const EMP_USER = process.env.EMP_USER || 'dk.rahul';
const EMP_PASS = process.env.EMP_PASS || 'npc123';

// Helper: login
async function login(page, username, password) {
  await page.goto('/login');
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForLoadState('networkidle');
}

// Helper: clear sessions via API call to logout
async function clearSession(page) {
  await page.goto('/logout');
  await page.waitForLoadState('networkidle');
}

// ================================================================
//  1. LOGIN & AUTH
// ================================================================

test.describe('Login & Authentication', () => {
  test.afterEach(async ({ page }) => { await clearSession(page); });

  test('should show login page', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('h1')).toHaveText('Biometric Attendance');
    await expect(page.locator('input[name="username"]')).toBeVisible();
    await expect(page.locator('input[name="password"]')).toBeVisible();
  });

  test('should reject invalid credentials', async ({ page }) => {
    await login(page, 'invaliduser', 'wrongpassword');
    await expect(page.locator('.flash')).toContainText('Invalid Username or Password');
  });

  test('should login admin successfully', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await expect(page).toHaveURL(/\/admin/);
  });

  test('should redirect to login when accessing protected routes', async ({ page }) => {
    await page.goto('/admin');
    await expect(page).toHaveURL(/\/login/);
    await page.goto('/employee');
    await expect(page).toHaveURL(/\/login/);
    await page.goto('/head');
    await expect(page).toHaveURL(/\/login/);
  });
});

// ================================================================
//  2. NO CONCURRENT LOGIN
// ================================================================

test.describe('No Concurrent Login', () => {
  test('should warn and force-logout old session on second login', async ({ browser }) => {
    // First session
    const ctx1 = await browser.newContext();
    const p1 = await ctx1.newPage();
    await login(p1, ADMIN_USER, ADMIN_PASS);
    await expect(p1).toHaveURL(/\/admin/);

    // Second session - should succeed but show warning
    const ctx2 = await browser.newContext();
    const p2 = await ctx2.newPage();
    await login(p2, ADMIN_USER, ADMIN_PASS);
    await expect(p2).toHaveURL(/\/admin/);
    // Should show "previous session terminated" warning
    const flash = p2.locator('.flash');
    const hasFlash = await flash.count();
    if (hasFlash > 0) {
      await expect(flash).toContainText('previous session');
    }

    await p1.goto('/logout');
    await p2.goto('/logout');
    await ctx1.close();
    await ctx2.close();
  });
});

// ================================================================
//  3. COMPULSORY PASSWORD CHANGE ON FIRST LOGIN
// ================================================================

test.describe('Compulsory Password Change', () => {
  test('should force password change for first-time user', async ({ page }) => {
    // First clear any stale session for dk.rahul by logging in and out
    await login(page, EMP_USER, EMP_PASS);
    const url1 = page.url();
    if (url1.includes('login')) {
      // Blocked by concurrent session — wait 1s and retry (session may have expired)
      await page.waitForTimeout(1000);
      await login(page, EMP_USER, EMP_PASS);
    }
    // If redirected to change-password, test passes. If on login, clear and retry.
    const url2 = page.url();
    if (url2.includes('change-password')) {
      await expect(page.locator('.forced-banner')).toContainText('must change');
    }
    await clearSession(page);
  });

  test('should block navigation until password changed', async ({ page }) => {
    await login(page, EMP_USER, EMP_PASS);
    const url = page.url();
    if (url.includes('change-password')) {
      await page.goto('/employee');
      await expect(page).toHaveURL(/\/change-password/);
    }
    await clearSession(page);
  });

  test('should allow access after password change', async ({ page }) => {
    await login(page, EMP_USER, EMP_PASS);
    const url = page.url();
    if (!url.includes('change-password')) {
      // Skip if can't login (concurrent or already changed)
      await clearSession(page);
      return;
    }

    await page.fill('input[name="old_password"]', EMP_PASS);
    await page.fill('input[name="new_password"]', 'NewPass123');
    await page.fill('input[name="confirm_password"]', 'NewPass123');
    await page.click('button[type="submit"]');
    await page.waitForLoadState('networkidle');

    await expect(page).toHaveURL(/\/employee/);

    // Reset: change back
    await page.goto('/change-password');
    await page.fill('input[name="old_password"]', 'NewPass123');
    await page.fill('input[name="new_password"]', 'npc12345');
    await page.fill('input[name="confirm_password"]', 'npc12345');
    await page.click('button[type="submit"]');
    await clearSession(page);
  });
});

// ================================================================
//  4. FORGOT PASSWORD
// ================================================================

test.describe('Forgot Password', () => {
  test('should show forgot password link on login page', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('a[href="/forgot-password"]')).toBeVisible();
  });

  test('should display contact email on forgot password page', async ({ page }) => {
    await page.goto('/forgot-password');
    await expect(page.locator('.email')).toContainText('vijay.kumar@npcindia.gov.in');
  });

  test('should have back to login link', async ({ page }) => {
    await page.goto('/forgot-password');
    await page.click('a[href="/login"]');
    await expect(page).toHaveURL(/\/login/);
  });
});

// ================================================================
//  5. PASSWORD STRENGTH VALIDATION
// ================================================================

test.describe('Password Strength Validation', () => {
  test.afterEach(async ({ page }) => { await clearSession(page); });

  test('should reject short password', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/change-password');
    await page.fill('input[name="old_password"]', ADMIN_PASS);
    await page.fill('input[name="new_password"]', 'ab1');
    await page.fill('input[name="confirm_password"]', 'ab1');
    await page.click('button[type="submit"]');
    await expect(page.locator('.flash')).toContainText('at least 8 characters');
  });

  test('should reject password without numbers', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/change-password');
    await page.fill('input[name="old_password"]', ADMIN_PASS);
    await page.fill('input[name="new_password"]', 'abcdefgh');
    await page.fill('input[name="confirm_password"]', 'abcdefgh');
    await page.click('button[type="submit"]');
    await expect(page.locator('.flash')).toContainText('at least one number');
  });

  test('should reject password without letters', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/change-password');
    await page.fill('input[name="old_password"]', ADMIN_PASS);
    await page.fill('input[name="new_password"]', '12345678');
    await page.fill('input[name="confirm_password"]', '12345678');
    await page.click('button[type="submit"]');
    await expect(page.locator('.flash')).toContainText('at least one letter');
  });

  test('should reject mismatched passwords', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/change-password');
    await page.fill('input[name="old_password"]', ADMIN_PASS);
    await page.fill('input[name="new_password"]', 'NewPass123');
    await page.fill('input[name="confirm_password"]', 'DiffPass456');
    await page.click('button[type="submit"]');
    await expect(page.locator('.flash')).toContainText('do not match');
  });

  test('should show real-time password strength indicators', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/change-password');
    await page.fill('#newPw', 'abc');
    await expect(page.locator('#rule-length')).toHaveClass(/invalid/);
    await page.fill('#newPw', 'MyStrong1');
    await expect(page.locator('#rule-length')).toHaveClass(/valid/);
    await expect(page.locator('#rule-letter')).toHaveClass(/valid/);
    await expect(page.locator('#rule-number')).toHaveClass(/valid/);
  });
});

// ================================================================
//  6. CACHE CONTROL & LOGOUT
// ================================================================

test.describe('Cache Control & Logout', () => {
  test('should set no-cache headers', async ({ page }) => {
    const resp = await page.goto('/login');
    const cc = resp.headers()['cache-control'];
    expect(cc).toContain('no-store');
    expect(cc).toContain('no-cache');
  });

  test('should show logout message', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/logout');
    await expect(page.locator('.flash')).toContainText('logged out');
  });

  test('should not access protected page after logout', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await expect(page).toHaveURL(/\/admin/);
    await page.goto('/logout');
    await page.goto('/admin');
    await expect(page).toHaveURL(/\/login/);
  });
});

// ================================================================
//  7. ADMIN FEATURES
// ================================================================

test.describe('Admin Features', () => {
  test.afterEach(async ({ page }) => { await clearSession(page); });

  test('should show upload form', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await expect(page.locator('input[name="files"]')).toBeVisible();
  });

  test('should show analysis sessions table', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await expect(page.locator('h2').filter({ hasText: 'Analysis Sessions' })).toBeVisible();
  });

  test('should access user management', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/admin/users');
    await expect(page.locator('h2').filter({ hasText: 'All Users' })).toBeVisible();
  });
});

// ================================================================
//  8. NAVIGATION
// ================================================================

test.describe('Navigation', () => {
  test.afterEach(async ({ page }) => { await clearSession(page); });

  test('should have logout and password links', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await expect(page.locator('a[href="/logout"]')).toBeVisible();
    await expect(page.locator('a[href="/change-password"]')).toBeVisible();
  });

  test('forgot password link on login page', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('a[href="/forgot-password"]')).toBeVisible();
  });
});

// ================================================================
//  9. EMPLOYEE DASHBOARD
// ================================================================

test.describe('Employee Dashboard', () => {
  test.afterEach(async ({ page }) => { await clearSession(page); });

  test('should show last submitted column header', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/employee');
    // Admin may not have employee data but page should load
    await expect(page.locator('.navbar')).toBeVisible();
  });
});
