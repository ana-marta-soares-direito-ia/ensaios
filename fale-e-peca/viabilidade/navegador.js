// Viabilidade: o modelo de linguagem corre dentro do navegador (WebGPU), sem servidor?
const http = require('http'), fs = require('fs'), path = require('path'), pw = require('playwright');
(async () => {
  const srv = http.createServer((q, r) => { r.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cross-origin-opener-policy': 'same-origin', 'cross-origin-embedder-policy': 'credentialless' }); r.end(fs.readFileSync(path.join(__dirname, 'pagina.html'))); }).listen(8123);
  const res = {};
  for (const [nome, args] of [['gpu-por-software', ['--enable-unsafe-webgpu', '--enable-features=Vulkan', '--use-angle=swiftshader', '--use-webgpu-adapter=swiftshader', '--ignore-gpu-blocklist']]]) {
    const b = await pw.chromium.launch({ args }), p = await b.newPage(); p.on('console', (m) => console.log('  [' + nome + '] ' + m.text().slice(0, 300))); p.on('pageerror', (e) => console.log('  erro de página: ' + e.message.slice(0, 300)));
    await p.goto('http://localhost:8123/'); const t0 = Date.now(); let r = {};
    while (Date.now() - t0 < 40 * 60000) { r = await p.evaluate(() => window.R || {}); if (r.fim) break; await new Promise((x) => setTimeout(x, 15000)); console.log('  ' + nome + ': ' + (r.passos || []).slice(-1)[0]); }
    res[nome] = r; await b.close();
  }
  srv.close(); console.log('@@INICIO@@'); console.log(Buffer.from(JSON.stringify(res)).toString('base64')); console.log('@@FIM@@');
})().catch((e) => { console.error(e); process.exit(1); });
