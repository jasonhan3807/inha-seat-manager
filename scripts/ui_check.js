// 브라우저 UI 점검 (Playwright). 서버 실행 후: node scripts/ui_check.js [출력폴더]
// PC/모바일 화면에서 주요 흐름을 실행하고 스크린샷과 결과를 남긴다.
const { chromium, devices } = require("playwright");
const path = require("path");
const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const OUT = process.argv[2] || "ui-check";

async function run(name, ctxOpts) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext(ctxOpts);
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("dialog", (d) => d.accept());
  const r = { name, checks: {} };

  await page.goto(BASE + "/");
  await page.waitForSelector(".room-btn");
  r.checks.demoBanner = await page.isVisible(".demo-banner");
  r.checks.connOk = (await page.textContent("#conn .txt")) !== "연결 확인 중…";
  await page.screenshot({ path: path.join(OUT, `${name}-dashboard.png`), fullPage: true });

  // 좌석 배치도 → 빈자리 하나를 희망 좌석으로 추가
  await page.click('.tabs button[data-tab="seats"]');
  await page.waitForSelector(".seat");
  r.checks.seatCount = await page.locator(".seat").count();
  r.checks.seatHasText = (await page.locator(".seat .st").first().textContent()).length > 0;
  await page.locator(".seat:not(.watched)").first().click();
  await page.waitForSelector("#seat-dialog[open]");
  await page.click("#sd-watch");
  await page.waitForSelector(".seat.watched");
  r.checks.watchAdded = await page.locator(".seat.watched").count();
  await page.screenshot({ path: path.join(OUT, `${name}-seats.png`), fullPage: true });

  // 가로 스크롤(넘침) 검사: 페이지 전체가 화면보다 넓으면 안 됨
  r.checks.seatMapFits = await page.evaluate(() => { const m = document.querySelector("#seat-map"); return m.scrollWidth <= m.clientWidth + 1; });
  r.checks.noPageOverflow = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);

  // 모니터링 시작 / 중지
  await page.click('.tabs button[data-tab="dashboard"]');
  await page.click("#d-start");
  await page.waitForFunction(() => document.querySelector("#d-monitor").textContent.includes("실행 중"));
  r.checks.monitorStarted = true;
  await page.click("#d-stop");
  await page.waitForFunction(() => document.querySelector("#d-monitor").textContent.includes("중지됨"));
  r.checks.monitorStopped = true;

  for (const tab of ["watches", "notifications", "history", "settings"]) {
    await page.click(`.tabs button[data-tab="${tab}"]`);
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(OUT, `${name}-${tab}.png`), fullPage: true });
  }
  r.checks.systemRows = await page.locator("#sys dt").count();
  r.errors = errors;
  await browser.close();
  return r;
}

(async () => {
  require("fs").mkdirSync(OUT, { recursive: true });
  const results = [
    await run("pc", { viewport: { width: 1280, height: 900 } }),
    await run("mobile", { ...devices["iPhone 13"] }),
  ];
  console.log(JSON.stringify(results, null, 2));
  const bad = results.some((r) => r.errors.length || !r.checks.noPageOverflow || !r.checks.watchAdded || !r.checks.seatMapFits);
  process.exit(bad ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
