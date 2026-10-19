// Browser smoke test of the three main journeys against a running app.
//   Backend (serving frontend/dist) with seeded demo data and DEMO_LLM_STANDIN=true:
//     SEED_DEMO=true SEED_PASSWORD=demo-pass-123 DEMO_LLM_STANDIN=true uvicorn app.main:app --port 8000
//   Then:  node e2e/smoke.mjs   (needs the `playwright` package; BASE_URL, SHOTS env optional)
import { createRequire } from "module";
const require = createRequire(import.meta.url);
let pw;
try { pw = require("playwright"); } catch { pw = require(`${process.env.NODE_PATH || "/opt/node22/lib/node_modules"}/playwright`); }

const BASE = process.env.BASE_URL || "http://localhost:8000";
const PASS = process.env.SEED_PASSWORD || "demo-pass-123";
const SHOTS = process.env.SHOTS || "";
const exe = process.env.CHROMIUM || undefined;

const browser = await pw.chromium.launch({ executablePath: exe });
const shot = async (page, name) => { if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true }); };
const step = (m) => console.log("✓", m);

async function login(page, email) {
  await page.goto(`${BASE}/login`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASS);
  await page.getByRole("button", { name: "Log in" }).click();
}

async function answerIntake(page, complaint) {
  await page.getByRole("textbox").first().fill(complaint);
  await page.getByRole("button", { name: "Next" }).click();
  for (let i = 0; i < 8; i++) {
    await page.waitForTimeout(400);
    if (await page.getByText("Is this right?").isVisible().catch(() => false)) break;
    if (await page.getByText("Please go to the Emergency department now.").isVisible().catch(() => false)) return "emergency";
    if (await page.getByText("Your booking is confirmed").isVisible().catch(() => false)) return "routine";
    const none = page.getByRole("button", { name: /None of these/ });
    if (await none.isVisible().catch(() => false)) {
      await none.click();
      await page.waitForTimeout(300);
      // conditions question: "None" toggles, then Next submits (the safety screen submits on tap)
      if (await none.isVisible().catch(() => false)) await page.getByRole("button", { name: "Next" }).click();
      continue;
    }
    const chip = page.getByRole("button", { name: "1–3 days" });
    if (await chip.isVisible().catch(() => false)) { await chip.click(); continue; }
    const tb = page.getByRole("textbox").first();
    if (await tb.isVisible().catch(() => false)) { await tb.fill("mild, no other problems"); await page.getByRole("button", { name: "Next" }).click(); }
  }
  if (await page.getByText("Is this right?").isVisible().catch(() => false)) {
    await page.getByRole("button", { name: "Yes, this is right" }).click();
  }
  return "submitted";
}

async function bookGM(page) {
  await page.goto(`${BASE}/patient/book`);
  await page.getByRole("button", { name: "Next" }).first().click(); // first hospital
  await page.getByRole("button", { name: "General Medicine" }).click();
  await page.getByRole("button", { name: "Choose this doctor" }).first().click();
  await page.getByRole("heading", { name: "Choose a date and session" }).waitFor();
  await page.locator(".card button.btn:not([disabled])", { hasText: "Next" }).first().click();
}

try {
  // ---- Journey 1: patient registers, books, gets a token
  const ctx = await browser.newContext({ viewport: { width: 360, height: 780 } });
  const page = await ctx.newPage();
  const stamp = Date.now();
  const email = `smoke${stamp}@example.com`;
  const NAME = `Smoke Patient ${stamp}`;
  await page.goto(`${BASE}/register`);
  await page.getByLabel("Full name").fill(NAME);
  await page.getByLabel(/^Email/).fill(email);
  await page.getByLabel(/^Password/).fill("smoke-password-123");
  await page.getByLabel("Age (years)").fill("30");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.getByText("Book an appointment").waitFor();
  await shot(page, "01-home");
  step("patient registered");
  await bookGM(page);
  await answerIntake(page, "mild cold and runny nose since yesterday");
  await page.getByTestId("token").waitFor({ timeout: 15000 });
  const token = await page.getByTestId("token").textContent();
  await shot(page, "02-routine-token");
  step(`routine booking -> token ${token}`);

  // ---- Journey 1b: emergency path, no booking
  await bookGM(page);
  const r = await answerIntake(page, "severe chest pain and I can't breathe");
  await page.getByText("Please go to the Emergency department now.").waitFor({ timeout: 15000 });
  await shot(page, "03-emergency");
  step(`emergency screen shown (${r})`);

  // ---- Journey 2: nurse checks the patient in
  const nctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const nurse = await nctx.newPage();
  await login(nurse, "nurse.adyar@example.com");
  await nurse.getByRole("link", { name: "Check-in desk" }).click();
  await nurse.getByLabel("Search by token or name").fill(NAME);
  await nurse.getByRole("button", { name: "Search" }).click();
  await nurse.getByRole("button", { name: "Check in" }).first().click();
  await nurse.getByRole("button", { name: "No change" }).click();
  await nurse.getByRole("heading", { name: "Vitals" }).waitFor();
  await shot(nurse, "04-nurse-drawer");
  step("nurse checked the patient in");
  await nurse.getByRole("button", { name: "Close" }).click();
  await nurse.getByRole("link", { name: "Dashboard" }).click();
  await nurse.getByText("Present and waiting").first().waitFor();
  await shot(nurse, "05-nurse-dashboard");

  // ---- Journey 3: doctor calls in, writes diagnosis + prescription, completes
  const dctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const doc = await dctx.newPage();
  await login(doc, "dr.gm.adyar@example.com");
  const card = doc.locator(".entry", { hasText: NAME });
  await card.getByRole("button", { name: "Call in" }).click();
  await doc.getByText("1. Triage summary").waitFor();
  await doc.getByLabel("Diagnosis (your words)").fill("Common cold");
  await doc.getByLabel("Drug").fill("Steam inhalation");
  await doc.getByLabel("Frequency").fill("twice daily");
  await shot(doc, "06-doctor-workspace");
  await doc.getByRole("button", { name: "4. Complete consultation" }).click();
  await doc.getByText("Present patients").waitFor();
  step("doctor completed the consultation");

  await page.goto(`${BASE}/patient/records`);
  await page.getByText("Common cold").waitFor();
  await page.getByText("Steam inhalation").waitFor();
  await shot(page, "07-my-records");
  step("patient sees diagnosis and prescription in My records");
  console.log("SMOKE PASS");
} catch (e) {
  console.error("SMOKE FAIL", e);
  process.exitCode = 1;
} finally {
  await browser.close();
}
