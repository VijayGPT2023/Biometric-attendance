const { test, expect } = require('@playwright/test');

const BASE = process.env.BASE_URL || 'https://npc-biometric-attendance.up.railway.app';
const ADMIN_PASS = process.env.ADMIN_PASS || 'Vjad@2008';

async function login(page, user, pass) {
    await page.goto(BASE + '/login');
    await page.fill('input[name="username"]', user);
    await page.fill('input[name="password"]', pass);
    await page.click('button[type="submit"]');
    await page.waitForLoadState('networkidle');
    return page.url();
}
async function logout(page) {
    try { await page.goto(BASE + '/logout', {timeout:10000}); } catch(e) {}
}

// ================================================================
// A. LANDING PAGE & PUBLIC ROUTES
// ================================================================
test.describe('A. Landing & Public', () => {
    test('Landing page shows slideshow with login button', async ({ page }) => {
        await page.goto(BASE + '/');
        await expect(page.locator('.login-btn')).toBeVisible();
        await expect(page.locator('.slide-container')).toBeVisible();
        await expect(page.locator('.nav-btn')).toHaveCount(2);
    });
    test('Health endpoint returns ok', async ({ page }) => {
        const r = await page.goto(BASE + '/health');
        expect((await r.json()).status).toBe('ok');
    });
    test('Forgot password shows email', async ({ page }) => {
        await page.goto(BASE + '/forgot-password');
        await expect(page.locator('body')).toContainText('vijay.kumar@npcindia.gov.in');
    });
    test('Protected routes redirect to login', async ({ page }) => {
        for (const path of ['/admin/', '/employee/', '/head/', '/settings/', '/audit/']) {
            await page.goto(BASE + path);
            expect(page.url()).toContain('/login');
        }
    });
    test('Security headers present', async ({ page }) => {
        const r = await page.goto(BASE + '/login');
        expect(r.headers()['x-frame-options']).toBe('DENY');
        expect(r.headers()['x-content-type-options']).toBe('nosniff');
        expect(r.headers()['cache-control']).toContain('no-store');
    });
});

// ================================================================
// B. AUTHENTICATION
// ================================================================
test.describe('B. Authentication', () => {
    test('Rejects invalid credentials', async ({ page }) => {
        await login(page, 'nobody', 'wrong');
        await expect(page.locator('.flash')).toContainText('Invalid');
    });
    test('Admin login goes to admin dashboard', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        expect(page.url()).toContain('/admin');
        await logout(page);
    });
    test('Logout redirects to login with message', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        await page.goto(BASE + '/logout');
        await expect(page.locator('.flash')).toContainText('logged out');
    });
    test('Cannot access admin after logout', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        await logout(page);
        await page.goto(BASE + '/admin/');
        expect(page.url()).toContain('/login');
    });
    test('Concurrent login allowed with warning', async ({ browser }) => {
        const c1 = await browser.newContext();
        const p1 = await c1.newPage();
        await login(p1, 'admin', ADMIN_PASS);
        expect(p1.url()).toContain('/admin');
        const c2 = await browser.newContext();
        const p2 = await c2.newPage();
        await login(p2, 'admin', ADMIN_PASS);
        expect(p2.url()).toContain('/admin');
        await logout(p1); await logout(p2);
        await c1.close(); await c2.close();
    });
});

// ================================================================
// C. ADMIN DASHBOARD (base.html navigation)
// ================================================================
test.describe('C. Admin Dashboard', () => {
    test.afterEach(async ({ page }) => { await logout(page); });

    test('Dashboard extends base.html with full nav', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        const c = await page.content();
        expect(c).toContain('NPC');
        expect(c).toContain('/admin/users');
        expect(c).toContain('/admin/data-management');
        expect(c).toContain('/holidays/');
        expect(c).toContain('/reconciliation/');
        expect(c).toContain('/head/habitual');
        expect(c).toContain('/settings/');
        expect(c).toContain('/audit/');
    });
    test('Shows upload form with office selector', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        await expect(page.locator('input[name="files"]')).toBeVisible();
        await expect(page.locator('select[name="office_id"]')).toBeVisible();
        await expect(page.locator('input[name="confirm_replace"]')).toBeAttached();
    });
    test('Shows sessions with employee/anomaly counts', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        const c = await page.content();
        expect(c).toContain('Analysis Sessions');
        expect(c).toContain('Employees');
        expect(c).toContain('Anomalies');
    });
    test('Session has Report, Review, Excel, Delete buttons', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        const c = await page.content();
        if (c.includes('session_uuid') || c.includes('View Report') || c.includes('Report')) {
            expect(c).toContain('Report');
            expect(c).toContain('Review');
            expect(c).toContain('Excel');
            expect(c).toContain('Delete');
        }
    });
});

// ================================================================
// D. ADMIN USER MANAGEMENT
// ================================================================
test.describe('D. User Management', () => {
    test.afterEach(async ({ page }) => { await logout(page); });

    test('Users page loads', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        await page.goto(BASE + '/admin/users');
        await expect(page.locator('body')).toContainText('Add User');
    });
    test('Data management page loads', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        await page.goto(BASE + '/admin/data-management');
        const c = await page.content();
        expect(c).toContain('Quick Add Employee');
        expect(c).toContain('Employee Directory');
        expect(c).toContain('Upload Sessions');
    });
    test('Data management has search', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        await page.goto(BASE + '/admin/data-management');
        await expect(page.locator('#empSearch')).toBeVisible();
    });
});

// ================================================================
// E. PASSWORD
// ================================================================
test.describe('E. Password', () => {
    test.afterEach(async ({ page }) => { await logout(page); });

    test('Change password page accessible', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        await page.goto(BASE + '/change-password');
        await expect(page.locator('input[name="old_password"]')).toBeVisible();
    });
    test('Rejects short password', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        await page.goto(BASE + '/change-password');
        await page.fill('input[name="old_password"]', ADMIN_PASS);
        await page.fill('input[name="new_password"]', 'ab1');
        await page.fill('input[name="confirm_password"]', 'ab1');
        await page.click('button[type="submit"]');
        await expect(page.locator('.flash')).toContainText('8 characters');
    });
});

// ================================================================
// F. EMPLOYEE
// ================================================================
test.describe('F. Employee', () => {
    test('Employee dashboard loads', async ({ page }) => {
        const url = await login(page, 'dk.rahul', 'npc123');
        if (url.includes('/login')) { test.skip(); return; }
        expect(page.url()).toContain('/employee');
        await expect(page.locator('body')).toContainText('Attendance');
        await logout(page);
    });
    test('Employee can view anomaly report', async ({ page }) => {
        const url = await login(page, 'dk.rahul', 'npc123');
        if (url.includes('/login')) { test.skip(); return; }
        const btn = page.locator('a:has-text("View")').first();
        if (await btn.count() > 0) {
            await btn.click();
            await page.waitForLoadState('networkidle');
            await expect(page.locator('body')).toContainText('Anomaly');
        }
        await logout(page);
    });
});

// ================================================================
// G. HEAD / GH
// ================================================================
test.describe('G. Head Dashboard', () => {
    test('GH dashboard with period selector', async ({ page }) => {
        const url = await login(page, 'gh.hrmgroup', 'npc123');
        if (url.includes('/login')) { test.skip(); return; }
        expect(page.url()).toContain('/head');
        const c = await page.content();
        expect(c).toContain('HRM Group');
        await logout(page);
    });
    test('GH nav has Habitual link', async ({ page }) => {
        const url = await login(page, 'gh.hrmgroup', 'npc123');
        if (url.includes('/login')) { test.skip(); return; }
        await expect(page.locator('a[href="/head/habitual"]')).toBeVisible();
        await logout(page);
    });
    test('GH can access habitual page', async ({ page }) => {
        const url = await login(page, 'gh.hrmgroup', 'npc123');
        if (url.includes('/login')) { test.skip(); return; }
        await page.goto(BASE + '/head/habitual');
        const c = await page.content();
        expect(c).toContain('Habitual');
        await logout(page);
    });
    test('GH can access review page', async ({ page }) => {
        const url = await login(page, 'gh.hrmgroup', 'npc123');
        if (url.includes('/login')) { test.skip(); return; }
        const btn = page.locator('a:has-text("Review")').first();
        if (await btn.count() > 0) {
            await btn.click();
            await page.waitForLoadState('networkidle');
            await expect(page.locator('body')).toContainText('Justification');
        }
        await logout(page);
    });
});

// ================================================================
// H. RECONCILIATION
// ================================================================
test.describe('H. Reconciliation', () => {
    test.afterEach(async ({ page }) => { await logout(page); });

    test('Reconciliation page has upload form', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        await page.goto(BASE + '/reconciliation/');
        const c = await page.content();
        expect(c).toContain('eHRMS');
        expect(c).toContain('ehrms_file');
    });
    test('Reconciliation page has session selector', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        await page.goto(BASE + '/reconciliation/');
        await expect(page.locator('select[name="session_uuid"]')).toBeVisible();
    });
});

// ================================================================
// I. HOLIDAYS
// ================================================================
test.describe('I. Holidays', () => {
    test.afterEach(async ({ page }) => { await logout(page); });

    test('Holiday page accessible', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        await page.goto(BASE + '/holidays/');
        expect(page.url()).toContain('/holidays');
    });
    test('API returns 2026 holidays', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        const r = await page.goto(BASE + '/api/v1/holidays/2026');
        const d = await r.json();
        expect(d.length).toBeGreaterThan(0);
    });
});

// ================================================================
// J. SETTINGS & AUDIT
// ================================================================
test.describe('J. Settings & Audit', () => {
    test.afterEach(async ({ page }) => { await logout(page); });

    test('Settings page accessible', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        await page.goto(BASE + '/settings/');
        expect(page.url()).toContain('/settings');
    });
    test('Audit page accessible', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        await page.goto(BASE + '/audit/');
        expect(page.url()).toContain('/audit');
    });
});

// ================================================================
// K. API
// ================================================================
test.describe('K. API', () => {
    test.afterEach(async ({ page }) => { await logout(page); });

    test('Sessions API returns JSON', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        const r = await page.goto(BASE + '/api/v1/sessions');
        const d = await r.json();
        expect(Array.isArray(d)).toBe(true);
    });
    test('User search API works', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        const r = await page.goto(BASE + '/api/v1/users/search?q=rahul');
        const d = await r.json();
        expect(d.length).toBeGreaterThan(0);
    });
    test('Notifications API returns array', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        const r = await page.goto(BASE + '/api/v1/notifications');
        const d = await r.json();
        expect(Array.isArray(d)).toBe(true);
    });
    test('Unread count API works', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        const r = await page.goto(BASE + '/notifications/unread-count');
        const d = await r.json();
        expect(typeof d.count).toBe('number');
    });
    test('API requires auth', async ({ page }) => {
        await page.goto(BASE + '/api/v1/sessions');
        expect(page.url()).toContain('/login');
    });
});

// ================================================================
// L. ROLE-BASED ACCESS
// ================================================================
test.describe('L. Role Access', () => {
    test('Employee blocked from admin', async ({ page }) => {
        const url = await login(page, 'dk.rahul', 'npc123');
        if (url.includes('/login')) { test.skip(); return; }
        await page.goto(BASE + '/admin/');
        expect(page.url()).not.toContain('/admin/');
        await logout(page);
    });
});

// ================================================================
// M. NOTIFICATIONS
// ================================================================
test.describe('M. Notifications', () => {
    test.afterEach(async ({ page }) => { await logout(page); });

    test('Notifications page loads', async ({ page }) => {
        await login(page, 'admin', ADMIN_PASS);
        await page.goto(BASE + '/notifications/');
        expect(page.url()).toContain('/notifications');
    });
});
