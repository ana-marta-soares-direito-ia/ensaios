// Entrega da chave do pacote à máquina de ensaio, sem segredos guardados no repositório.
// A máquina gera um par de chaves, publica a pública e recebe a chave do pacote cifrada só para si.
// «fechar» cifra um resultado com a mesma chave do pacote, para o devolver sem o tornar público.
const crypto = require('crypto'), fs = require('fs'), path = require('path');
const [, , modo, a, b, c] = process.argv, TMP = process.env.RUNNER_TEMP || require('os').tmpdir(), PRIV = path.join(TMP, 'chave-privada.pem'), K = path.join(TMP, 'chave-do-pacote.bin');
if (modo === 'gerar') { const { publicKey, privateKey } = crypto.generateKeyPairSync('rsa', { modulusLength: 3072 }); fs.writeFileSync(PRIV, privateKey.export({ type: 'pkcs8', format: 'pem' }), { mode: 0o600 }); fs.writeFileSync(a, publicKey.export({ type: 'spki', format: 'pem' })); console.log('Chave pública escrita em ' + a); }
else if (modo === 'abrir') { const k = crypto.privateDecrypt({ key: fs.readFileSync(PRIV), oaepHash: 'sha256' }, Buffer.from(fs.readFileSync(a, 'utf8').trim(), 'base64')), d = fs.readFileSync(b), iv = d.subarray(0, 12), tag = d.subarray(12, 28), dc = crypto.createDecipheriv('aes-256-gcm', k, iv); dc.setAuthTag(tag); fs.writeFileSync(c, Buffer.concat([dc.update(d.subarray(28)), dc.final()])); fs.unlinkSync(PRIV); if (process.env.GUARDAR_CHAVE) fs.writeFileSync(K, k, { mode: 0o600 }); console.log('Pacote aberto.'); }
else if (modo === 'fechar') { const k = fs.readFileSync(K), iv = crypto.randomBytes(12), ci = crypto.createCipheriv('aes-256-gcm', k, iv), d = Buffer.concat([ci.update(fs.readFileSync(a)), ci.final()]); fs.writeFileSync(b, Buffer.concat([iv, ci.getAuthTag(), d])); console.log('Resultado cifrado.'); }
else process.exit(1);
