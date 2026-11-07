// Run with NODE_PATH pointing to a Playwright installation.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../../..');
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let failProject = false;
    let failProducts = false;
    let description = '<p>Clean <strong>water</strong></p><script>window.attacked=1</script><a href="javascript:alert(1)" x-init="window.attacked=1" @click="window.attacked=1">unsafe</a>';
    let lead = '<strong>Project lead</strong><img src=x onerror="window.attacked=1"><a href="javascript:alert(1)" x-init="window.attacked=1">Contact</a>';
    let partners = [{ id: 1, name: '<em>Community partner</em><script>window.attacked=1</script>', url: "https://example.com/partner" }];
    await page.route('http://catalog.test/**', async route => {
      const pathname = new URL(route.request().url()).pathname;
      if (pathname.startsWith('/static/')) {
        const relative = pathname.slice(8);
        const file = relative.startsWith('projects_catalog/')
          ? path.join(root, 'projects_catalog/static', relative)
          : path.join(root, 'static', relative);
        return route.fulfill({ body: fs.readFileSync(file), contentType: pathname.endsWith('.css') ? 'text/css' : 'text/javascript' });
      }
      if (pathname.startsWith('/data/projects/example/')) {
        const products = pathname.endsWith('/products/');
        return route.fulfill({ status: (products ? failProducts : failProject) ? 500 : 200, json: products ? { categories: { Data: [{ id: 1, data_summary: '<p>A <em>dataset</em></p>', resource_detail_url: '/resource/1/' }] } } : {
          project_name: 'Example project', project_description: description, project_impact: '- First impact\n- Second impact',
          start_date: '2026-11-01', project_url: 'javascript:alert(1)', project_leads: [{ id: 1, name: lead, organization: "Research Group", email: "lead@example.com", url: "javascript:alert(1)", role: "Investigator" }, { id: 2, name: "Second Lead", url: "https://example.com/lead" }], partners, pictures: [], keywords: 'air,water', hosting_locations: [],
        } });
      }
      let template = fs.readFileSync(path.join(root, 'projects_catalog/templates/project_catalog_detail.html'), 'utf8');
      template = template.replace(/{% static '([^']+)' %}/g, '/static/$1').replace(/{% url 'project-list-web-data' %}/g, '/data/projects/').replace(/{{ project_code }}/g, 'example').replace(/{%[^%]*%}/g, '');
      const css = fs.readFileSync(path.join(root, 'static/css/bulma/css/versions/bulma-no-dark-mode.css'), 'utf8');
      return route.fulfill({ contentType: 'text/html', body: `<html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>${css}</style></head><body><section class="section"><div class="container">${template}</div></section></body></html>` });
    });
    await page.goto('http://catalog.test/');
    await page.getByRole('heading', { name: 'Example project' }).waitFor();
    assert.equal(await page.locator('main .rich-text strong').textContent(), 'water');
    assert.equal(await page.locator('.project-lead strong').textContent(), 'Project lead');
    assert.equal(await page.locator('.partner-name em').textContent(), 'Community partner');
    assert.equal(await page.locator('.partner-url').textContent(), 'https://example.com/partner');
    assert.equal(await page.locator('.partner-url').getAttribute('href'), 'https://example.com/partner');
    await page.locator('.project-lead a').click();
    assert.equal(await page.evaluate(() => window.attacked), undefined);
    assert.equal(await page.locator('.rich-text [x-init], .rich-text [onclick], .rich-text script, .rich-text [href^="javascript:"]').count(), 0);
    assert.equal(await page.locator('.rich-text li').count(), 2);
    assert.equal(await page.locator('.meta-tile').nth(1).locator('p').last().textContent(), 'Nov 2026');
    for (const width of [375, 768, 1280]) {
      await page.setViewportSize({ width, height: 900 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `overflow at ${width}`);
    }
    failProducts = true;
    await page.reload();
    await page.getByText('Unable to load project products. Please try again.').waitFor();
    assert.ok(await page.getByRole('heading', { name: 'Example project' }).isVisible());
    failProject = true;
    await page.reload();
    await page.getByText('Unable to load this project. Please try again.').waitFor();
    failProject = false;
    failProducts = false;
    lead = 'Plain lead';
    partners = [{ id: 1, name: 'Plain partner', url: 'javascript:alert(1)' }];
    description = 'Plain paragraph one.\n\nPlain paragraph two.';
    await page.getByRole('button', { name: 'Try again', exact: true }).first().click();
    await page.getByText('Plain paragraph two.', { exact: true }).waitFor();
    assert.equal(await page.locator('.project-lead').first().textContent(), 'Plain lead');
    assert.equal(await page.locator('.project-lead').count(), 2);
    assert.ok(await page.getByText('Research Group', { exact: true }).isVisible());
    assert.equal(await page.getByRole('link', { name: 'lead@example.com' }).getAttribute('href'), 'mailto:lead%40example.com');
    assert.equal(await page.getByRole('link', { name: 'https://example.com/lead' }).getAttribute('href'), 'https://example.com/lead');
    assert.equal(await page.locator('.partner-name').textContent(), 'Plain partner');
    assert.equal(await page.locator('.partner-url').isVisible(), false);
    assert.equal(await page.locator('.partner-url').getAttribute('href'), null);
    assert.deepEqual(errors, []);
    console.log('Passed: rich text, XSS protection, plain text, dates, responsive widths, partial failure, retry.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
