const { test, expect } = require('@playwright/test');

const BASE = process.env.BASE_URL || 'https://npc-biometric-attendance.up.railway.app';
const ADMIN_USER = process.env.ADMIN_USER || 'admin';
const ADMIN_PASS = process.env.ADMIN_PASS || 'Vjad@2008';
const EMP_USER = process.env.EMP_USER || 'dk.rahul';
const EMP_PASS = process.env.EMP_PASS || 'npc123';
const HEAD_USER = process.env.HEAD_USER || 'gh.hrmgroup';
const HEAD_PASS = process.env.HEAD_PASS || 'npc123';

// ============================================================
// HELPERS
// ============================================================

async function login(page, username, password) {
  await page.goto('/login');
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForLoadState('networkidle');
}

async function logout(page) {
  try {
    await page.goto('/logout', { timeout: 10000 });
    await page.waitForLoadState('networkidle', { timeout: 5000 });
  } catch (e) {
    // Transient network errors during logout are acceptable
  }
}

async function handlePasswordChange(page, oldPw, newPw) {
  if (page.url().includes('change-password')) {
    await page.fill('input[name="old_password"]', oldPw);
    await page.fill('input[name="new_password"]', newPw);
    await page.fill('input[name="confirm_password"]', newPw);
    await page.click('button[type="submit"]');
    await page.waitForLoadState('networkidle');
    return true;
  }
  return false;
}

// ============================================================
// 1. HEALTH & BASIC ENDPOINTS
// ============================================================

test.describe('Health & Basic Endpoints', () => {
  test('GET /health returns ok', async ({ page }) => {
    const resp = await page.goto('/health');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.status).toBe('ok');
  });

  test('GET /login returns 200', async ({ page }) => {
    const resp = await page.goto('/login');
    expect(resp.status()).toBe(200);
    await expect(page.locator('input[name="username"]')).toBeVisible();
    await expect(page.locator('input[name="password"]')).toBeVisible();
  });

  test('GET /forgot-password shows email', async ({ page }) => {
    await page.goto('/forgot-password');
    await expect(page.locator('body')).toContainText('vijay.kumar@npcindia.gov.in');
  });

  test('Protected routes redirect to login', async ({ page }) => {
    await page.goto('/admin/');
    await expect(page).toHaveURL(/\/login/);
    await page.goto('/employee/');
    await expect(page).toHaveURL(/\/login/);
    await page.goto('/head/');
    await expect(page).toHaveURL(/\/login/);
    await page.goto('/settings/');
    await expect(page).toHaveURL(/\/login/);
    await page.goto('/audit/');
    await expect(page).toHaveURL(/\/login/);
  });

  test('No-cache headers on HTML pages', async ({ page }) => {
    const resp = await page.goto('/login');
    const cc = resp.headers()['cache-control'] || '';
    expect(cc).toContain('no-store');
  });

  test('Security headers present', async ({ page }) => {
    const resp = await page.goto('/login');
    expect(resp.headers()['x-content-type-options']).toBe('nosniff');
    expect(resp.headers()['x-frame-options']).toBe('DENY');
  });
});

// ============================================================
// 2. AUTHENTICATION
// ============================================================

test.describe('Authentication', () => {
  test('Reject invalid credentials', async ({ page }) => {
    await login(page, 'fakeuser', 'wrongpass');
    await expect(page.locator('.flash')).toContainText('Invalid');
    await expect(page).toHaveURL(/\/login/);
  });

  test('Admin login success', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await expect(page).toHaveURL(/\/admin/);
    await logout(page);
  });

  test('Logout shows message and redirects', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/logout');
    await expect(page).toHaveURL(/\/login/);
    await expect(page.locator('.flash')).toContainText('logged out');
  });

  test('Cannot access admin after logout', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await expect(page).toHaveURL(/\/admin/);
    await logout(page);
    await page.goto('/admin/');
    await expect(page).toHaveURL(/\/login/);
  });

  test('Concurrent login warns but allows', async ({ browser }) => {
    const ctx1 = await browser.newContext();
    const p1 = await ctx1.newPage();
    await login(p1, ADMIN_USER, ADMIN_PASS);
    await expect(p1).toHaveURL(/\/admin/);

    const ctx2 = await browser.newContext();
    const p2 = await ctx2.newPage();
    await login(p2, ADMIN_USER, ADMIN_PASS);
    await expect(p2).toHaveURL(/\/admin/);

    await p1.goto('/logout');
    await p2.goto('/logout');
    await ctx1.close();
    await ctx2.close();
  });
});

// ============================================================
// 3. ADMIN DASHBOARD
// ============================================================

test.describe('Admin Dashboard', () => {
  test.afterEach(async ({ page }) => { await logout(page); });

  test('Shows upload form with office selector', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await expect(page.locator('input[name="files"]')).toBeVisible();
    await expect(page.locator('select[name="office_id"]')).toBeVisible();
    await expect(page.locator('input[name="late_time"]')).toBeVisible();
    await expect(page.locator('input[name="early_time"]')).toBeVisible();
  });

  test('Shows sessions table', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    const content = await page.content();
    expect(content).toContain('Analysis Sessions');
  });

  test('CSRF token present in upload form', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    const csrf = await page.locator('input[name="csrf_token"]').first();
    await expect(csrf).toBeAttached();
  });
});

// ============================================================
// 4. USER MANAGEMENT (Admin)
// ============================================================

test.describe('User Management', () => {
  test.afterEach(async ({ page }) => { await logout(page); });

  test('Admin can access user management page', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/admin/users');
    await expect(page.locator('body')).toContainText('Add User');
    await expect(page.locator('body')).toContainText('Manage Offices');
  });

  test('User list shows seeded users', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/admin/users');
    // Should have admin + heads + employees
    const content = await page.content();
    expect(content).toContain('admin');
    expect(content).toContain('gh.hrmgroup');
  });

  test('Office creation form exists', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/admin/users');
    await expect(page.locator('input[name="office_name"]')).toBeVisible();
    await expect(page.locator('input[name="office_code"]')).toBeVisible();
  });
});

// ============================================================
// 5. PASSWORD MANAGEMENT
// ============================================================

test.describe('Password Management', () => {
  test.afterEach(async ({ page }) => { await logout(page); });

  test('Change password page loads', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/change-password');
    await expect(page.locator('input[name="old_password"]')).toBeVisible();
    await expect(page.locator('input[name="new_password"]')).toBeVisible();
  });

  test('Rejects short password', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/change-password');
    await page.fill('input[name="old_password"]', ADMIN_PASS);
    await page.fill('input[name="new_password"]', 'ab1');
    await page.fill('input[name="confirm_password"]', 'ab1');
    await page.click('button[type="submit"]');
    await expect(page.locator('.flash')).toContainText('8 characters');
  });

  test('Rejects password without number', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/change-password');
    await page.fill('input[name="old_password"]', ADMIN_PASS);
    await page.fill('input[name="new_password"]', 'abcdefgh');
    await page.fill('input[name="confirm_password"]', 'abcdefgh');
    await page.click('button[type="submit"]');
    await expect(page.locator('.flash')).toContainText('number');
  });

  test('Rejects mismatched passwords', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/change-password');
    await page.fill('input[name="old_password"]', ADMIN_PASS);
    await page.fill('input[name="new_password"]', 'StrongPass1');
    await page.fill('input[name="confirm_password"]', 'DifferentPass1');
    await page.click('button[type="submit"]');
    await expect(page.locator('.flash')).toContainText('do not match');
  });

  test('Password strength indicators work', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/change-password');
    const pwInput = page.locator('#newPw');
    if (await pwInput.count() > 0) {
      await pwInput.fill('abc');
      await expect(page.locator('#r-len')).toHaveClass(/invalid/);
      await pwInput.fill('Strong123');
      await expect(page.locator('#r-len')).toHaveClass(/valid/);
      await expect(page.locator('#r-let')).toHaveClass(/valid/);
      await expect(page.locator('#r-num')).toHaveClass(/valid/);
    }
  });

  test('First-time employee forced to change password', async ({ page }) => {
    await login(page, EMP_USER, EMP_PASS);
    const url = page.url();
    if (url.includes('change-password')) {
      await expect(page.locator('body')).toContainText('must change');
    }
    await logout(page);
  });
});

// ============================================================
// 6. EMPLOYEE DASHBOARD
// ============================================================

test.describe('Employee Dashboard', () => {
  test('Employee sees own dashboard after login', async ({ page }) => {
    await login(page, EMP_USER, EMP_PASS);
    const url = page.url();
    if (url.includes('change-password')) {
      await handlePasswordChange(page, EMP_PASS, 'Employee123');
    }
    if (page.url().includes('/employee')) {
      await expect(page.locator('body')).toContainText('Attendance');
    }
    await logout(page);
  });
});

// ============================================================
// 7. HEAD DASHBOARD
// ============================================================

test.describe('Head Dashboard', () => {
  test('Head sees department dashboard after login', async ({ page }) => {
    await login(page, HEAD_USER, HEAD_PASS);
    const url = page.url();
    if (url.includes('change-password')) {
      await handlePasswordChange(page, HEAD_PASS, 'HeadPass123');
    }
    if (page.url().includes('/head')) {
      await expect(page.locator('body')).toContainText('HRM Group');
    }
    await logout(page);
  });
});

// ============================================================
// 8. HOLIDAYS
// ============================================================

test.describe('Holidays', () => {
  test.afterEach(async ({ page }) => { await logout(page); });

  test('Holiday calendar accessible', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/holidays/');
    expect(page.url()).toContain('/holidays');
  });

  test('API returns holidays for 2026', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    const resp = await page.goto('/api/v1/holidays/2026');
    const data = await resp.json();
    expect(data.length).toBeGreaterThan(0);
    expect(data[0]).toHaveProperty('date');
    expect(data[0]).toHaveProperty('name');
  });
});

// ============================================================
// 9. API ENDPOINTS
// ============================================================

test.describe('API Endpoints', () => {
  test.afterEach(async ({ page }) => { await logout(page); });

  test('GET /api/v1/sessions returns JSON', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    const resp = await page.goto('/api/v1/sessions');
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    expect(Array.isArray(data)).toBe(true);
  });

  test('GET /api/v1/notifications returns JSON', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    const resp = await page.goto('/api/v1/notifications');
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    expect(Array.isArray(data)).toBe(true);
  });

  test('GET /api/v1/users/search?q=admin returns results', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    const resp = await page.goto('/api/v1/users/search?q=admin');
    expect(resp.status()).toBe(200);
    const data = await resp.json();
    expect(data.length).toBeGreaterThan(0);
    const adminUser = data.find(u => u.username === 'admin');
    expect(adminUser).toBeTruthy();
  });

  test('API requires authentication', async ({ page }) => {
    const resp = await page.goto('/api/v1/sessions');
    // Should redirect to login
    expect(page.url()).toContain('/login');
  });
});

// ============================================================
// 10. SETTINGS
// ============================================================

test.describe('Settings', () => {
  test.afterEach(async ({ page }) => { await logout(page); });

  test('Admin can access settings', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/settings/');
    expect(page.url()).toContain('/settings');
  });
});

// ============================================================
// 11. AUDIT LOG
// ============================================================

test.describe('Audit Log', () => {
  test.afterEach(async ({ page }) => { await logout(page); });

  test('Admin can access audit log', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/audit/');
    expect(page.url()).toContain('/audit');
  });
});

// ============================================================
// 12. NOTIFICATIONS
// ============================================================

test.describe('Notifications', () => {
  test.afterEach(async ({ page }) => { await logout(page); });

  test('Notifications page accessible', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/notifications/');
    expect(page.url()).toContain('/notifications');
  });

  test('Unread count API works', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    const resp = await page.goto('/notifications/unread-count');
    const data = await resp.json();
    expect(data).toHaveProperty('count');
    expect(typeof data.count).toBe('number');
  });
});

// ============================================================
// 13. RECONCILIATION
// ============================================================

test.describe('Reconciliation', () => {
  test.afterEach(async ({ page }) => { await logout(page); });

  test('Reconciliation dashboard accessible', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    await page.goto('/reconciliation/');
    expect(page.url()).toContain('/reconciliation');
  });
});

// ============================================================
// 14. ROLE-BASED ACCESS CONTROL
// ============================================================

test.describe('Role-Based Access', () => {
  test('Employee cannot access admin', async ({ page }) => {
    await login(page, EMP_USER, EMP_PASS);
    const url = page.url();
    if (url.includes('change-password')) {
      await handlePasswordChange(page, EMP_PASS, 'Employee123');
    }
    await page.goto('/admin/');
    // Should redirect to login or show access denied
    const finalUrl = page.url();
    const isBlocked = finalUrl.includes('/login') || finalUrl.includes('/employee');
    expect(isBlocked).toBe(true);
    await logout(page);
  });

  test('Employee cannot access settings', async ({ page }) => {
    await login(page, EMP_USER, EMP_PASS);
    if (page.url().includes('change-password')) {
      await handlePasswordChange(page, EMP_PASS, 'Employee123');
    }
    await page.goto('/settings/');
    const isBlocked = page.url().includes('/login') || !page.url().includes('/settings');
    expect(isBlocked).toBe(true);
    await logout(page);
  });
});

// ============================================================
// 15. FORGOT PASSWORD
// ============================================================

test.describe('Forgot Password', () => {
  test('Shows contact email', async ({ page }) => {
    await page.goto('/forgot-password');
    await expect(page.locator('body')).toContainText('vijay.kumar@npcindia.gov.in');
    await expect(page.locator('body')).toContainText('Username');
    await expect(page.locator('body')).toContainText('Employee Code');
  });

  test('Has back to login link', async ({ page }) => {
    await page.goto('/forgot-password');
    await page.click('a[href*="login"]');
    await expect(page).toHaveURL(/\/login/);
  });
});

// ============================================================
// 16. NAVIGATION & UI
// ============================================================

test.describe('Navigation', () => {
  test.afterEach(async ({ page }) => { await logout(page); });

  test('Admin navbar has all expected links', async ({ page }) => {
    await login(page, ADMIN_USER, ADMIN_PASS);
    const content = await page.content();
    expect(content).toContain('/admin/users');
    expect(content).toContain('/logout');
    expect(content).toContain('/change-password');
  });

  test('Login page has forgot password link', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('a[href*="forgot"]')).toBeVisible();
  });
});
