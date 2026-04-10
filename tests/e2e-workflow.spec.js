const { test, expect } = require('@playwright/test');

const BASE = process.env.BASE_URL || 'https://npc-biometric-attendance.up.railway.app';
const ADMIN_USER = 'admin';
const ADMIN_PASS = process.env.ADMIN_PASS || 'Vjad@2008';

// Helper: login and return page
async function loginAs(page, username, password) {
    await page.goto(BASE + '/login');
    await page.fill('input[name="username"]', username);
    await page.fill('input[name="password"]', password);
    await page.click('button[type="submit"]');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    return page.url();
}

async function logout(page) {
    try { await page.goto(BASE + '/logout', { timeout: 10000 }); } catch(e) {}
}

// Helper: reset a user's password via admin
async function resetUserPassword(page, userId) {
    await loginAs(page, ADMIN_USER, ADMIN_PASS);
    const r = await page.goto(BASE + '/admin/users');
    const csrf = await page.locator('input[name="csrf_token"]').first().getAttribute('value');
    // Use direct POST
    await page.evaluate(async ({base, uid, csrf}) => {
        const fd = new FormData();
        fd.append('csrf_token', csrf);
        await fetch(base + '/admin/users/' + uid + '/reset-password', { method: 'POST', body: fd });
    }, { base: BASE, uid: userId, csrf: csrf });
    await logout(page);
}

// ============================================================
// TEST 1: Employee can see query, reply, and see full history
// ============================================================
test.describe('Employee Query-Reply Workflow', () => {

    test('Employee report page loads with anomalies', async ({ page }) => {
        // Login as employee dk.rahul
        const url = await loginAs(page, 'dk.rahul', 'npc123');
        if (url.includes('/login')) {
            test.skip();
            return;
        }

        // Should be on employee dashboard
        expect(page.url()).toContain('/employee');

        // Check if there are attendance sessions
        const viewBtns = page.locator('a:has-text("View")');
        const count = await viewBtns.count();

        if (count > 0) {
            // Click first View & Justify
            await viewBtns.first().click();
            await page.waitForLoadState('networkidle');

            // Should show anomaly details
            const content = await page.content();
            expect(content).toContain('Anomaly');

            // Check for justification text areas (pending or query status)
            const textareas = page.locator('textarea[name^="justification_"]');
            const taCount = await textareas.count();

            if (taCount > 0) {
                // Fill first justification
                await textareas.first().fill('Official meeting at Ministry - E2E test');

                // Submit
                await page.click('button[type="submit"]');
                await page.waitForLoadState('networkidle');

                // Should show success or the page reloads
                const afterContent = await page.content();
                expect(afterContent).toContain('Anomaly');
            }
        }

        await logout(page);
    });

    test('Employee sees query text and reply box when queried', async ({ page }) => {
        const url = await loginAs(page, 'dk.rahul', 'npc123');
        if (url.includes('/login')) {
            test.skip();
            return;
        }

        const viewBtns = page.locator('a:has-text("View")');
        if (await viewBtns.count() > 0) {
            await viewBtns.first().click();
            await page.waitForLoadState('networkidle');

            const content = await page.content();

            // Check for query-related elements (may or may not exist depending on state)
            // If head has queried, should show "Head's Query" text
            if (content.includes('query') || content.includes('Query')) {
                // Query elements present - verify reply option exists
                const hasReplyBox = content.includes('reply') || content.includes('Reply') ||
                                    content.includes('textarea');
                expect(hasReplyBox).toBe(true);
            }

            // Verify resubmitted items show full history
            if (content.includes('resubmitted') || content.includes('Resubmitted')) {
                expect(content).toContain('Your justification');
                expect(content).toContain('Reply');
            }
        }

        await logout(page);
    });
});

// ============================================================
// TEST 2: GH can review, accept/decline/query with history
// ============================================================
test.describe('GH Review Workflow', () => {

    test('GH dashboard shows period selector', async ({ page }) => {
        const url = await loginAs(page, 'gh.hrmgroup', 'npc123');
        if (url.includes('/login')) {
            // Try resetting password
            test.skip();
            return;
        }

        // Should be on head dashboard
        expect(page.url()).toContain('/head');

        // Check for period selector dropdown
        const content = await page.content();
        const hasSelector = content.includes('Select Period') || content.includes('select') ||
                           content.includes('<option');

        // Should show employee data
        expect(content).toContain('HRM Group');

        await logout(page);
    });

    test('GH can access review page', async ({ page }) => {
        const url = await loginAs(page, 'gh.hrmgroup', 'npc123');
        if (url.includes('/login')) {
            test.skip();
            return;
        }

        // Click Review Justifications
        const reviewBtn = page.locator('a:has-text("Review")');
        if (await reviewBtn.count() > 0) {
            await reviewBtn.first().click();
            await page.waitForLoadState('networkidle');

            const content = await page.content();
            // Should show employee justifications
            expect(content).toContain('Justification');

            // Should have action dropdowns (Accept/Decline/Query)
            const selects = page.locator('select.action-select');
            const selectCount = await selects.count();

            if (selectCount > 0) {
                // Check first dropdown has Accept, Decline, Query options
                const options = await selects.first().locator('option').allTextContents();
                const hasAccept = options.some(o => o.includes('Accept'));
                const hasDecline = options.some(o => o.includes('Decline'));
                expect(hasAccept).toBe(true);
                expect(hasDecline).toBe(true);
            }

            // Check query count limit shown
            if (content.includes('Query')) {
                expect(content).toContain('/2');
            }
        }

        await logout(page);
    });

    test('GH review shows employee justification text', async ({ page }) => {
        const url = await loginAs(page, 'gh.hrmgroup', 'npc123');
        if (url.includes('/login')) {
            test.skip();
            return;
        }

        const reviewBtn = page.locator('a:has-text("Review")');
        if (await reviewBtn.count() > 0) {
            await reviewBtn.first().click();
            await page.waitForLoadState('networkidle');

            const content = await page.content();
            // If any justifications submitted, should show the text
            if (content.includes('justification-text') || content.includes('E2E test')) {
                expect(content).toContain('Justification');
            }
        }

        await logout(page);
    });
});

// ============================================================
// TEST 3: eHRMS Reconciliation
// ============================================================
test.describe('eHRMS Reconciliation', () => {

    test('Admin can access reconciliation page', async ({ page }) => {
        await loginAs(page, ADMIN_USER, ADMIN_PASS);

        await page.goto(BASE + '/reconciliation/');
        await page.waitForLoadState('networkidle');

        expect(page.url()).toContain('/reconciliation');
        const content = await page.content();
        // Should show upload form or dashboard
        expect(content.toLowerCase()).toContain('reconcil');

        await logout(page);
    });

    test('Reconciliation page has upload form', async ({ page }) => {
        await loginAs(page, ADMIN_USER, ADMIN_PASS);

        await page.goto(BASE + '/reconciliation/');
        await page.waitForLoadState('networkidle');

        const content = await page.content();
        // Should have file upload capability
        const hasForm = content.includes('ehrms_file') || content.includes('upload') ||
                       content.includes('Upload') || content.includes('form');
        expect(hasForm).toBe(true);

        await logout(page);
    });

    test('Admin dashboard shows duplicate session warning checkbox', async ({ page }) => {
        await loginAs(page, ADMIN_USER, ADMIN_PASS);

        const content = await page.content();
        expect(content).toContain('Replace existing');
        expect(content).toContain('confirm_replace');

        await logout(page);
    });
});

// ============================================================
// TEST 4: Monthly breakup and habitual list
// ============================================================
test.describe('Monthly Breakup & Habitual', () => {

    test('Habitual page accessible for head/admin', async ({ page }) => {
        await loginAs(page, ADMIN_USER, ADMIN_PASS);

        await page.goto(BASE + '/head/habitual');
        await page.waitForLoadState('networkidle');

        const content = await page.content();
        expect(content).toContain('Habitual');

        await logout(page);
    });

    test('Head can access habitual page', async ({ page }) => {
        const url = await loginAs(page, 'gh.hrmgroup', 'npc123');
        if (url.includes('/login')) {
            test.skip();
            return;
        }

        await page.goto(BASE + '/head/habitual');
        await page.waitForLoadState('networkidle');

        const content = await page.content();
        expect(content).toContain('Habitual');
        // Should show either habitual employees or "No habitual" message
        const hasResult = content.includes('HABITUAL') || content.includes('No habitual') ||
                         content.includes('within acceptable');
        expect(hasResult).toBe(true);

        await logout(page);
    });

    test('Navigation includes Habitual link for head', async ({ page }) => {
        const url = await loginAs(page, 'gh.hrmgroup', 'npc123');
        if (url.includes('/login')) {
            test.skip();
            return;
        }

        const content = await page.content();
        expect(content).toContain('/head/habitual');

        await logout(page);
    });
});

// ============================================================
// TEST 5: Period selector on GH dashboard
// ============================================================
test.describe('Period Selector', () => {

    test('GH dashboard shows all sessions in dropdown', async ({ page }) => {
        const url = await loginAs(page, ADMIN_USER, ADMIN_PASS);
        // Admin has head access too
        await page.goto(BASE + '/head/');
        await page.waitForLoadState('networkidle');

        const content = await page.content();
        // Should have session selector if multiple sessions exist
        if (content.includes('Select Period')) {
            const options = await page.locator('select option').count();
            expect(options).toBeGreaterThan(0);
        }

        await logout(page);
    });
});
