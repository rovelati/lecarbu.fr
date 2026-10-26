#!/usr/bin/env node
/**
 * notify-indexnow.js — LeCarbu.fr
 * Notifies Bing, IndexNow, and search engines about the most important live fuel URLs.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const HOST = 'lecarbu.fr';
const KEY = 'd7192a54e9bc4fa58e65842c129e917d';
const KEY_LOCATION = `https://${HOST}/${KEY}.txt`;

const citiesPath = path.join(__dirname, '..', 'src', 'data', 'fr_cities.json');
const brandsPath = path.join(__dirname, '..', 'src', 'data', 'fr_brands.json');
const deptPath = path.join(__dirname, '..', 'src', 'data', 'fr_departements.json');

const cities = JSON.parse(fs.readFileSync(citiesPath, 'utf8'));
const brands = JSON.parse(fs.readFileSync(brandsPath, 'utf8'));
const depts = JSON.parse(fs.readFileSync(deptPath, 'utf8'));

const urlList = [
  `https://${HOST}/`,
  `https://${HOST}/carburant-moins-cher/`,
  `https://${HOST}/supermarche-carburant/`,
  `https://${HOST}/prix-carburant/gazole/`,
  `https://${HOST}/prix-carburant/essence-e10/`,
  `https://${HOST}/prix-carburant/sp98/`,
  `https://${HOST}/prix-carburant/e85/`,
];

// Top 8 Brands
for (const b of brands) {
  urlList.push(`https://${HOST}/enseigne/${b.slug}/`);
}

// Top Departments
for (const d of depts.slice(0, 20)) {
  urlList.push(`https://${HOST}/departement/${d.slug}/`);
}

// Top 40 cities x 3 fuel URLs
for (const c of cities.slice(0, 40)) {
  urlList.push(`https://${HOST}/prix-carburant/${c.slug}/`);
  urlList.push(`https://${HOST}/prix-carburant/${c.slug}/gazole/`);
  urlList.push(`https://${HOST}/prix-carburant/${c.slug}/essence-e10/`);
}

const payload = {
  host: HOST,
  key: KEY,
  keyLocation: KEY_LOCATION,
  urlList: urlList.slice(0, 200),
};

const endpoints = [
  'https://api.indexnow.org/indexnow',
  'https://www.bing.com/indexnow',
  'https://yandex.com/indexnow',
];

console.log(`[IndexNow] LeCarbu.fr — Pinging ${payload.urlList.length} priority URLs`);
console.log(`[IndexNow] First URL: ${payload.urlList[0]}`);
console.log(`[IndexNow] Last URL:  ${payload.urlList[payload.urlList.length - 1]}`);

for (const ep of endpoints) {
  try {
    const res = await fetch(ep, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify(payload),
    });
    console.log(`[IndexNow] ${ep} -> status ${res.status}`);
  } catch (err) {
    console.error(`[IndexNow] ${ep} failed:`, err.message);
  }
}
