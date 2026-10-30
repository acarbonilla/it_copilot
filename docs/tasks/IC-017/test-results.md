# IC-017 Test Results

**Environment:** Windows 11, native MySQL, installed Google Chrome, Next.js 16.4.3

| Evidence | Result |
| --- | --- |
| Real-Chrome owner/App Admin workflow | PASS - 1/1 (15.8 seconds) |
| Upload and real isolated-worker processing to READY | PASS |
| Secure attachment body/disposition/nosniff/no-store | PASS |
| App Admin metadata-only/no download | PASS |
| Archive/restore/delete | PASS |
| Browser storage/URL/console synthetic-marker scan | PASS |
| Django/Next.js log synthetic-marker/filename scan | PASS |
| Disposable native-MySQL and private-root cleanup | PASS |
| Focused reconciliation/storage suite | PASS - 21/21 |
| Complete native MySQL backend suite | PASS - 208/208 (263.044 seconds) exact-head rerun |
| Frontend unit suite | PASS - 8 files / 36 tests (12.25 seconds) exact-head rerun |
| TypeScript and zero-warning ESLint | PASS |
| Production build | PASS - static `/documents` route |
