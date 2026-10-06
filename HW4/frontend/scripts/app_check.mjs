// Drives the live Campus Customs app in real Chrome and captures the
// screenshots for output/app_check.html. Needs both servers running
// (API on :8000, web on :5174). Run from HW4/frontend:
//   node scripts/app_check.mjs
// Writes PNGs to output/app_check_images/ and the raw results (chat replies,
// card names, page state) to output/app_check_images/results.json.
import puppeteer from 'puppeteer-core'
import { writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../output/app_check_images')
const BASE = 'http://localhost:5174'
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

const browser = await puppeteer.launch({ executablePath: CHROME, headless: true })
const page = await browser.newPage()
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })
const results = { ran_at: new Date().toISOString() }

async function openChat() {
  if (!(await page.$('.chat-panel'))) await page.click('.chat-fab')
  await page.waitForSelector('.chat-form .input')
}

// Type a message like a shopper and wait for the agent's reply to render.
async function ask(text) {
  const before = await page.$$eval('.chat-log .bubble', (b) => b.length)
  await page.type('.chat-form .input', text)
  await page.click('.chat-send')
  await page.waitForFunction(
    (n) => !document.querySelector('.bubble.assistant.muted') &&
      document.querySelectorAll('.chat-log .bubble').length >= n + 2,
    { timeout: 180000 }, before)
  await new Promise((r) => setTimeout(r, 1200)) // let images and layout settle
  return page.$$eval('.bubble.assistant', (all) => {
    const last = all[all.length - 1]
    return {
      reply: last.querySelector('.bubble-text').innerText,
      cards: [...last.querySelectorAll('.chat-card strong')].map((s) => s.textContent),
    }
  })
}

// 1) Inventory: on a product page, ask for stock by size.
await page.goto(`${BASE}/products/baseball-left-chest-crewneck`, { waitUntil: 'networkidle0' })
await openChat()
results.inventory = await ask('How many of this do you have in stock in each size?')
await page.screenshot({ path: `${OUT}/inventory_chat.png` })

// 2) Dynamic search cards: from the home page, ask for a category.
await page.goto(`${BASE}/`, { waitUntil: 'networkidle0' })
await openChat()
results.search = await ask('What kind of crewnecks do you have?')
await page.waitForSelector('.chat-results-banner')
await new Promise((r) => setTimeout(r, 1500))
results.search.page = await page.evaluate(() => ({
  url: location.pathname,
  heading: document.querySelector('.page h1')?.textContent,
  banner: document.querySelector('.chat-results-banner span')?.innerText,
  tiles: document.querySelectorAll('.product-grid .product-card').length,
  allCrewnecks: [...document.querySelectorAll('.product-grid .type')].every((t) => /crew/i.test(t.textContent)),
}))
await page.screenshot({ path: `${OUT}/search_cards.png` })

// 3) Compare: product page -> Compare button -> picker -> side-by-side page.
const fresh = await browser.newPage()
await fresh.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })
await fresh.goto(`${BASE}/products/basic-hoodie-big-yale`, { waitUntil: 'networkidle0' })
await fresh.evaluate(() => [...document.querySelectorAll('.detail-buttons button')].find((b) => b.textContent.includes('Compare')).click())
await fresh.waitForSelector('.modal .picker-item')
await fresh.type('.modal .input', 'saybrook fleece')
await new Promise((r) => setTimeout(r, 400))
await fresh.screenshot({ path: `${OUT}/compare_picker.png` })
await fresh.click('.picker-item')
await fresh.waitForSelector('.compare-table')
await new Promise((r) => setTimeout(r, 1500))
results.compare = await fresh.evaluate(() => ({
  url: location.pathname,
  names: [...document.querySelectorAll('.compare-name')].map((n) => n.textContent),
  rows: [...document.querySelectorAll('.compare-table tr')].map((tr) => [tr.querySelector('th').textContent, ...[...tr.querySelectorAll('td')].map((td) => td.innerText.replace(/\s+/g, ' ').trim())]),
}))
await fresh.screenshot({ path: `${OUT}/compare.png`, fullPage: true })

writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 2))
await browser.close()
console.log(JSON.stringify(results, null, 2))
