// Entrega da chave do pacote à máquina de ensaio, sem segredos guardados no repositório.
// A máquina gera um par de chaves, publica a pública e recebe a chave do pacote cifrada só para si.
const crypto = require('crypto'), fs = require('fs'), path = require('path');
const [, , modo, a, b, c] = process.argv, PRIV = path.join(process.env.RUNNER_TEMP || require('os').tmpdir(), 'chave-privada.pem');
if (modo === 'gerar') { const { publicKey, privateKey } = crypto.generateKeyPairSync('rsa', { modulusLength: 3072 }); fs.writeFileSync(PRIV, privateKey.export({ type: 'pkcs8', format: 'pem' }), { mode: 0o600 }); fs.writeFileSync(a, publicKey.export({ type: 'spki', format: 'pem' })); console.log('Chave pública escrita em ' + a); }
else if (modo === 'abrir') { const k = crypto.privateDecrypt({ key: fs.readFileSync(PRIV), oaepHash: 'sha256' }, Buffer.from(fs.readFileSync(a, 'utf8').trim(), 'base64')), d = fs.readFileSync(b), iv = d.subarray(0, 12), tag = d.subarray(12, 28), dc = crypto.createDecipheriv('aes-256-gcm', k, iv); dc.setAuthTag(tag); fs.writeFileSync(c, Buffer.concat([dc.update(d.subarray(28)), dc.final()])); fs.unlinkSync(PRIV); console.log('Pacote aberto.'); }
else process.exit(1);
