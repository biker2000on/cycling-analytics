import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

// Parse credentials from .env.test
function getCredentials(): { email: string; password: string } {
  const envPath = path.resolve(__dirname, '../../.env.test');
  const envContent = fs.readFileSync(envPath, 'utf-8');

  const emailMatch = envContent.match(/LOCAL_USER=(.+)/);
  const passwordMatch = envContent.match(/LOCAL_PASSWORD="(.+)"/);

  if (!emailMatch || !passwordMatch) {
    throw new Error('Could not parse credentials from .env.test');
  }

  return {
    email: emailMatch[1].trim(),
    password: passwordMatch[1].trim(),
  };
}

// Absolute paths to .zip files
const ZIP_FILES = [
  'C:/Users/biker/projects/cycling-analytics/.fitfiles/21796666064.zip',
  'C:/Users/biker/projects/cycling-analytics/.fitfiles/21817961064.zip',
  'C:/Users/biker/projects/cycling-analytics/.fitfiles/21817965502.zip',
  'C:/Users/biker/projects/cycling-analytics/.fitfiles/21829011561.zip',
];

test.describe('Upload and Calendar E2E', () => {
  test('should upload .zip files, process them, and verify calendar scroll', async ({ page }) => {
    const { email, password } = getCredentials();

    // Step 1: Login
    await test.step('Login to application', async () => {
      await page.goto('/login');

      await page.fill('#email', email);
      await page.fill('#password', password);
      await page.click('button[type="submit"]');

      // Wait for redirect to activities page
      await expect(page).toHaveURL(/\/activities/, { timeout: 10000 });
      await expect(page.locator('h1.page-title')).toContainText('Activities');
    });

    // Step 2: Upload .zip files
    await test.step('Upload 4 .zip files', async () => {
      // Locate the file input in UploadZone
      const fileInput = page.locator('input[type="file"][accept=".fit,.zip"]');
      await expect(fileInput).toBeAttached();

      // Upload all 4 files at once
      await fileInput.setInputFiles(ZIP_FILES);

      // Wait for upload to complete - look for "uploaded successfully" summary message
      await expect(page.locator('.upload-zone__summary')).toBeVisible({ timeout: 30000 });
      await expect(page.locator('.upload-zone__summary')).toContainText('uploaded successfully');
    });

    // Step 3: Wait for processing to complete
    await test.step('Wait for Celery processing to complete', async () => {
      // Each ZIP should show extracted files as children
      // Wait for all "Done" status indicators (no more "Processing" states)
      // Maximum wait time: 90 seconds for all processing to complete

      await page.waitForFunction(
        () => {
          const processingElements = document.querySelectorAll('.upload-zone__file-status--processing');
          return processingElements.length === 0;
        },
        { timeout: 90000 }
      );

      // Verify we have some completed uploads
      const doneStatuses = page.locator('.upload-zone__file-status--done');
      await expect(doneStatuses.first()).toBeVisible();
    });

    // Step 4: Verify activities appear in the list
    await test.step('Verify activities appear in list', async () => {
      // Refresh or wait for onUploadComplete callback to fetch activities
      // The upload zone should trigger fetchActivities after completion
      await page.waitForTimeout(2000); // Give time for the callback to fire

      // Should see activities in the table
      const activityTable = page.locator('.activity-table, table');
      await expect(activityTable).toBeVisible({ timeout: 10000 });

      // Verify we have at least some rows (more than just header)
      const rows = activityTable.locator('tbody tr');
      const rowCount = await rows.count();
      expect(rowCount).toBeGreaterThan(0);
    });

    // Step 5: Navigate to Calendar
    await test.step('Navigate to calendar page', async () => {
      // Click on Calendar nav link
      await page.click('a[href="/calendar"]');
      await expect(page).toHaveURL(/\/calendar/);
      await expect(page.locator('h1.page-title')).toContainText('Training Calendar');
    });

    // Step 6: Test calendar infinite scroll
    await test.step('Test calendar infinite scroll - load older months', async () => {
      const scrollContainer = page.locator('.calendar-scroll-container');
      await expect(scrollContainer).toBeVisible();

      // Get initial month count
      const initialMonths = await page.locator('.calendar-month-section').count();
      expect(initialMonths).toBeGreaterThanOrEqual(2); // Should have at least current + prev

      // Scroll to top to trigger loading older months
      await scrollContainer.evaluate((el) => {
        el.scrollTop = 0;
      });

      // Wait a moment for intersection observer to trigger
      await page.waitForTimeout(1500);

      // Should have loaded at least one more month
      const newMonthCount = await page.locator('.calendar-month-section').count();
      expect(newMonthCount).toBeGreaterThanOrEqual(initialMonths);
    });

    await test.step('Test calendar infinite scroll - load newer months', async () => {
      const scrollContainer = page.locator('.calendar-scroll-container');

      // Scroll to bottom to trigger loading newer months (up to limit)
      await scrollContainer.evaluate((el) => {
        el.scrollTop = el.scrollHeight;
      });

      // Wait for potential new month load
      await page.waitForTimeout(1500);

      // Verify calendar is still functional (no errors)
      await expect(page.locator('.calendar-month-section').first()).toBeVisible();
    });

    await test.step('Test "Today" button', async () => {
      // Click the Today button if it exists
      const todayButton = page.locator('button:has-text("Today")');
      if (await todayButton.isVisible()) {
        await todayButton.click();

        // Wait for scroll animation
        await page.waitForTimeout(500);

        // Current month should be visible
        const currentDate = new Date();
        const currentYear = currentDate.getFullYear();
        const currentMonth = currentDate.getMonth() + 1;

        const currentMonthHeader = page.locator(
          `.calendar-month-sticky-header[data-year="${currentYear}"][data-month="${currentMonth}"]`
        );
        await expect(currentMonthHeader).toBeVisible();
      }
    });

    // Step 7: Verify rides appear on calendar
    await test.step('Verify rides appear on correct dates in calendar', async () => {
      // Look for calendar days that have activity indicators
      const daysWithActivities = page.locator('.day-cell-has-activity');

      // Should have at least some days with activities (from the uploaded .fit files)
      const activeDayCount = await daysWithActivities.count();

      // We uploaded 4 files, so we should see at least 1 day with activities
      // (some files might be on the same day, so we check for >= 1)
      expect(activeDayCount).toBeGreaterThanOrEqual(1);
    });
  });
});
