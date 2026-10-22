// -*- coding: utf-8 -*-
/**
 * 真浏览器联调（TASK-018-2 收尾 / 生产化验证）：用 Playwright + 系统 Chrome 实跑前端。
 *
 * 流程：
 *   [0] admin/123456 登录（前端首页为鉴权门控，须先登录）
 *   [1] 仪表盘 / 系统健康面板：四维检查 + 边缘站点看门狗 + 近5分钟工具错误率 + 刷新按钮
 *   [2] 登录态访问 /edge-sites、/releases 真实渲染
 *   致命信号 = 未捕获 JS 异常（pageerror）；登录页正常的 401/404 网络噪声仅作告警。
 *
 * 运行（Playwright 装于 managed node 工作区）：
 *   NODE_PATH=/c/Users/mymatebook/.workbuddy/binaries/node/workspace/node_modules \
 *     node tests/e2e/browser_smoke.cjs
 * 前置：后端 127.0.0.1:8000（/api/health 公开）、前端 :3001（next 反代 /api/backend -> 8000）。
 */
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.BASE_URL || "http://localhost:3001";
const OUT = path.resolve(__dirname, "screenshots");
fs.mkdirSync(OUT, { recursive: true });

let PASS = 0;
let FAIL = 0;
const fails = [];
function check(name, cond) {
  if (cond) {
    PASS++;
    console.log("  ✅ " + name);
  } else {
    FAIL++;
    fails.push(name);
    console.log("  ❌ " + name);
  }
}

(async () => {
  const exe =
    process.env.CHROME_PATH ||
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe";
  const launchOpts = { args: ["--no-sandbox"] };
  if (fs.existsSync(exe)) {
    launchOpts.executablePath = exe;
    console.log("[env] 使用系统浏览器: " + exe);
  } else {
    console.log("[env] 使用 Playwright 自带 chromium");
  }
  const browser = await chromium.launch(launchOpts);
  const context = await browser.newContext();
  const page = await context.newPage();

  // 致命信号：未捕获 JS 异常；网络 401/404 仅作告警
  const pageErrors = [];
  const netNoise = [];
  page.on("pageerror", (e) => pageErrors.push("PAGEERROR: " + e.message));
  page.on("console", (m) => {
    if (m.type() === "error") {
      const t = m.text();
      if (/Failed to load resource/i.test(t)) netNoise.push(t);
      else pageErrors.push("CONSOLE: " + t);
    }
  });

  // ---------- [0] 登录 ----------
  console.log("[0] 登录 admin/123456");
  try {
    await page.goto(BASE + "/login", { waitUntil: "domcontentloaded", timeout: 90000 });
    await page.waitForSelector('input[placeholder="请输入用户名"]', { timeout: 90000 });
    await page.fill('input[placeholder="请输入用户名"]', "admin");
    await page.fill('input[placeholder="请输入密码"]', "123456");
    await page.click('button[type="submit"]');
    await page.waitForURL("**/", { timeout: 30000 }).catch(() => {});
    await page.waitForSelector("text=系统健康", { timeout: 90000 });
    check("登录成功并进入仪表盘（出现系统健康）", true);
  } catch (e) {
    check("登录并进入仪表盘", false);
    console.log("     err: " + e.message);
    await page.screenshot({ path: path.join(OUT, "login-failed.png"), fullPage: true });
  }

  // ---------- [1] 系统健康面板（含 Watchdog 看门狗） ----------
  console.log("[1] 仪表盘：系统健康 + Watchdog 看门狗面板渲染");
  try {
    // 「系统健康」标题是静态的；检查卡片依赖异步 health 请求。等卡片出现再断言，消除竞态。
    await page.waitForSelector("text=对话模型", { timeout: 30000 });
    const t1 = (await page.textContent("body")) || "";
    check("四维检查-数据库", t1.includes("数据库"));
    check("四维检查-对话模型", t1.includes("对话模型"));
    check("四维检查-语义检索", t1.includes("语义检索"));
    check("四维检查-系统", t1.includes("系统"));
    check("边缘站点看门狗面板", t1.includes("边缘站点看门狗"));
    check("近5分钟工具错误率面板", t1.includes("工具错误率"));
    const refresh = page.locator('button:has-text("刷新")');
    if ((await refresh.count()) > 0) {
      await refresh.first().click();
      await page.waitForTimeout(2500);
      check("点击「刷新」后仍可见系统健康（无崩溃）", ((await page.textContent("body")) || "").includes("系统健康"));
    } else {
      check("存在「刷新」按钮", false);
    }
    // 数据已加载后再截图（截图过早会拍到「未就绪」占位）
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(OUT, "dashboard.png"), fullPage: true });
  } catch (e) {
    check("系统健康面板渲染", false);
    console.log("     err: " + e.message);
  }

  // ---------- [2] 登录态页面 ----------
  console.log("[2] 登录态访问 /edge-sites、/releases");
  for (const [route, token] of [
    ["/edge-sites", "边缘站点"],
    ["/releases", "发布"],
  ]) {
    try {
      await page.goto(BASE + route, { waitUntil: "domcontentloaded", timeout: 90000 });
      await page.waitForTimeout(4000);
      const t = (await page.textContent("body")) || "";
      check(`${route} 渲染（含「${token}」）`, t.includes(token));
      await page.screenshot({ path: path.join(OUT, route.replace("/", "") + ".png"), fullPage: true });
    } catch (e) {
      check(`${route} 渲染`, false);
      console.log("     err: " + e.message);
    }
  }

  // 致命信号：仅未捕获 JS 异常
  check("无未捕获 JS 运行时异常", pageErrors.length === 0);
  if (pageErrors.length) {
    console.log("     致命 JS 错误：");
    pageErrors.slice(0, 25).forEach((e) => console.log("       | " + e.slice(0, 220)));
  }
  if (netNoise.length) {
    console.log(`     （网络噪声 ${netNoise.length} 条 401/404，非致命，仅供参考）`);
  }

  await browser.close();
  console.log("=".repeat(48));
  console.log(`PASS ${PASS} / FAIL ${FAIL}`);
  if (FAIL) {
    console.log("失败项: " + fails.join("; "));
    process.exit(1);
  }
  console.log("结果：全部通过");
})().catch((e) => {
  console.error("FATAL", e);
  process.exit(2);
});
