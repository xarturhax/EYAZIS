import { chromium, expect } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const output = path.join(root, "webapp/work/browser-check");
await mkdir(output, { recursive: true });
const browser = await chromium.launch({
  executablePath:
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  headless: true,
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 1100 },
});
const page = await context.newPage();
const errors = [];
let microphoneStarts = 0;
page.on("pageerror", (error) => errors.push(String(error)));
page.on("request", (request) => {
  if (request.url().endsWith("/api/live/start")) microphoneStarts++;
});
const base = process.env.EYAZIS_WEB_URL || "http://127.0.0.1:8765";
async function navigate(lab) {
  await page.goto(base + "/#lab-" + lab);
  await expect(page.locator(".workspace-heading")).toBeVisible();
  await expect(
    page.getByText("Загрузка материалов…", { exact: true }),
  ).toHaveCount(0);
}
async function completed() {
  await expect(
    page.locator(".job-strip.completed,.job-strip.failed,.job-strip.cancelled"),
  ).toBeVisible({
    timeout: 180000,
  });
  await expect(page.locator(".error")).toHaveCount(0);
  await expect(page.locator(".job-strip.completed")).toBeVisible();
}
async function submit(name) {
  const prior = (await page.locator(".job-strip small").count())
    ? await page.locator(".job-strip small").textContent()
    : "";
  await page.getByRole("button", { name, exact: true }).click();
  await expect
    .poll(
      () =>
        page
          .locator(".job-strip small")
          .textContent()
          .catch(() => ""),
      { timeout: 15000 },
    )
    .not.toBe(prior);
  await completed();
}
try {
  await page.goto(base);
  await expect(page.locator(".card")).toHaveCount(9);
  await page.getByRole("button", { name: "Текст и язык" }).click();
  await expect(page.locator(".card")).toHaveCount(4);
  await page.getByRole("button", { name: "Голос и звук" }).click();
  await expect(page.locator(".card")).toHaveCount(5);
  await page.getByRole("button", { name: "Все работы", exact: true }).click();
  await page.getByRole("searchbox").fill("BM25");
  await expect(page.locator(".card")).toHaveCount(1);
  await page.getByRole("searchbox").fill("");
  await page.screenshot({
    path: path.join(output, "home-desktop.png"),
    fullPage: true,
  });
  await navigate(1);
  await submit("Загрузить демо-коллекцию");
  await submit("Найти");
  await expect(page.locator(".search-result").first()).toBeVisible();
  await page.screenshot({
    path: path.join(output, "lab1-search.png"),
    fullPage: true,
  });
  await navigate(2);
  await submit("Обучить и сравнить");
  await expect(page.locator(".analysis-image")).toBeVisible();
  await navigate(3);
  await submit("Создать и сравнить рефераты");
  await expect(page.locator(".summary-card")).toHaveCount(2);
  await navigate(4);
  await submit("Перевести и разобрать");
  await expect(page.locator(".translation-output")).toBeVisible();
  await page.screenshot({
    path: path.join(output, "lab4-translation.png"),
    fullPage: true,
  });
  await navigate(5);
  await page.getByLabel("Подтверждённый фрагмент").selectOption("ph_a");
  await page.getByLabel("Операция", { exact: true }).selectOption("crop");
  await submit("Выполнить эксперимент");
  await expect(page.locator(".analysis-image")).toBeVisible();
  await navigate(6);
  await page
    .getByLabel("Операция", { exact: true })
    .selectOption("permutations");
  await submit("Выполнить эксперимент");
  await expect(page.locator(".playlist-item")).toHaveCount(6);
  await navigate(7);
  await submit("Собрать и проанализировать");
  const audioUrl = await page
    .locator(".audio-pair audio")
    .last()
    .getAttribute("src");
  const audio = await context.request.get(base + audioUrl, {
    headers: { Range: "bytes=0-99" },
  });
  expect(audio.status()).toBe(206);
  await navigate(8);
  await page.locator('input[type="file"]').setInputFiles({
    name: "voice.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "Bonjour. La littérature nous aide à comprendre le monde.",
      "utf8",
    ),
  });
  await expect(page.getByText("voice.txt", { exact: false })).toBeVisible();
  await submit("Синтезировать речь");
  await expect(
    page.getByRole("link", { name: "Скачать WAV", exact: true }),
  ).toBeVisible();
  await navigate(9);
  await page
    .getByText("Проверить WAV без выполнения команд", { exact: true })
    .click();
  await submit("Распознать WAV");
  await expect(page.locator(".transcript")).toBeVisible();
  expect(microphoneStarts).toBe(0);
  await page
    .getByRole("button", { name: "Готовые материалы", exact: true })
    .click();
  await expect(page.locator(".resource").first()).toBeVisible();
  await page
    .getByRole("button", { name: "Как это работает", exact: true })
    .click();
  await expect(page.locator(".help-list")).toBeVisible();
  await page.getByRole("button", { name: "Сменить тему" }).click();
  await expect(page.locator("body")).toHaveClass("dark");
  await page.screenshot({
    path: path.join(output, "lab9-dark.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Сменить тему" }).click();
  await page.goto(base + "/#history");
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await page.goto(base);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".card")).toHaveCount(9);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: path.join(output, "home-mobile.png"),
    fullPage: true,
  });
  await navigate(4);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: path.join(output, "lab4-mobile.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
  await writeFile(
    path.join(output, "result.json"),
    JSON.stringify(
      { status: "PASS", labs: 9, microphoneStarts, errors },
      null,
      2,
    ),
  );
  console.log(
    "PASS: all nine live web workflows; actual search, reports, charts, audio, history, themes, mobile widths; microphone not activated.",
  );
} catch (error) {
  await page.screenshot({
    path: path.join(output, "failure.png"),
    fullPage: true,
  });
  console.error(error);
  throw error;
} finally {
  await browser.close();
}
