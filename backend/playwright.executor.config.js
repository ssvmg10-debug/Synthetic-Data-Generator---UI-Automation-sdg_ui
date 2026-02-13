// Minimal config for executor-run tests only (avoids testDir scanning and version conflicts)
// RUN_DIR env set by executor (e.g. test_outputs/run_0) so only that folder is used
const path = require('path');
const runDir = process.env.RUN_DIR || '.';
module.exports = {
  testDir: path.resolve(process.cwd(), runDir),
  testMatch: '**/test.spec.js',
  fullyParallel: false,
  workers: 1,
  timeout: 180000,
  use: {
    actionTimeout: 30000,
    navigationTimeout: 60000,
    headless: false,
  },
  projects: [{ name: 'chromium', use: { channel: 'chromium' } }],
};
