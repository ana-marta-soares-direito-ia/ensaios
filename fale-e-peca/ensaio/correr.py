# Fale e Peça: ensaio prévio dos modelos de linguagem e de voz em português europeu (antes de construir o produto).
import json, os, re, subprocess, sys, time, glob, shutil, traceback
AQUI = os.path.dirname(os.path.abspath(__file__)); SAIDA = os.environ.get('SAIDA', os.path.join(AQUI, 'saida')); os.makedirs(SAIDA, exist_ok=True)
pedidos = json.load(open(os.path.join(AQUI, 'pedidos.json'), encoding='utf-8')); instr = open(os.path.join(AQUI, 'instrucao.txt'), encoding='utf-8').read()
res = {'maquina': {'cpus': os.cpu_count(), 'mem_gb': round(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 2**30, 1)}, 'modelos': {}, 'voz': {}}
BR = ['você', 'usuário', 'arquivo', 'tela ', 'celular', 'equipe', 'contato', 'registro', 'planilha', 'e-mail profissional para você', 'gerenciar', 'time ', 'cadastr', 'ônibus', 'esporte', 'fato ', 'ação judicial trabalhista']
TITULOS = ['Papel:', 'Contexto:', 'Tarefa:', 'Regras:', 'Formato da resposta:']
def avaliar(t):
    b = t.lower(); return {'titulos': sum(1 for x in TITULOS if x.lower() in b), 'brasileirismos': [x.strip() for x in BR if x in b], 'gerundio': len(re.findall(r'\b(est[áa]|estou|estão|estamos)\s+\w+ndo\b', b)), 'palavras': len(t.split())}
def guardar(): json.dump(res, open(os.path.join(SAIDA, 'resultado.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

def litert(nome, repo, ficheiro):
    r = res['modelos'][nome] = {'motor': 'LiteRT-LM', 'respostas': []}
    for i, p in enumerate(pedidos):
        t0 = time.time()
        try:
            o = subprocess.run(['litert-lm', 'run', '--from-huggingface-repo=' + repo, ficheiro, '--prompt=' + instr.replace('{PEDIDO}', p)], capture_output=True, text=True, timeout=1500)
            txt = o.stdout.strip(); dt = time.time() - t0
            r['respostas'].append(dict(avaliar(txt), pedido=i, segundos=round(dt, 1), texto=txt, erro=(o.stderr[-600:] if o.returncode else '')))
        except Exception as e: r['respostas'].append({'pedido': i, 'erro': repr(e)[:400]})
        guardar()

def gguf(nome, candidatos):
    r = res['modelos'][nome] = {'motor': 'llama.cpp', 'respostas': []}
    try:
        from huggingface_hub import list_repo_files, hf_hub_download
        from llama_cpp import Llama
        caminho = None
        for repo in candidatos:
            try:
                fs = [f for f in list_repo_files(repo) if f.lower().endswith('.gguf')]; alvo = [f for f in fs if 'q4_k_m' in f.lower()] or fs
                if alvo: caminho = hf_hub_download(repo, alvo[0]); r['repositorio'] = repo; r['ficheiro'] = alvo[0]; r['mb'] = round(os.path.getsize(caminho) / 2**20); break
            except Exception as e: r.setdefault('tentativas', []).append(repo + ': ' + repr(e)[:160])
        if not caminho: r['erro'] = 'nenhum repositório encontrado'; return
        m = Llama(model_path=caminho, n_ctx=4096, n_threads=os.cpu_count(), verbose=False)
        for i, p in enumerate(pedidos):
            t0 = time.time(); o = m.create_chat_completion(messages=[{'role': 'user', 'content': instr.replace('{PEDIDO}', p)}], max_tokens=700, temperature=0.3)
            txt = o['choices'][0]['message']['content'].strip(); txt = re.sub(r'<think>.*?</think>', '', txt, flags=re.S).strip(); dt = time.time() - t0
            r['respostas'].append(dict(avaliar(txt), pedido=i, segundos=round(dt, 1), tokens=o['usage']['completion_tokens'], tokens_s=round(o['usage']['completion_tokens'] / dt, 1), texto=txt)); guardar()
        del m
    except Exception as e: r['erro'] = traceback.format_exc()[-900:]
    guardar()

def voz():
    try:
        import jiwer
        from faster_whisper import WhisperModel
        frases = [l.strip() for l in open(os.path.join(AQUI, 'frases.txt'), encoding='utf-8') if l.strip()]; d = os.path.join(SAIDA, 'audio'); os.makedirs(d, exist_ok=True)
        from huggingface_hub import hf_hub_download
        vozes = []
        for v in ['pt/pt_PT/tugão/medium/pt_PT-tugão-medium']:
            try: vozes.append((hf_hub_download('rhasspy/piper-voices', v + '.onnx'), hf_hub_download('rhasspy/piper-voices', v + '.onnx.json')))
            except Exception as e: res['voz']['erro_voz'] = repr(e)[:300]
        wavs = []
        for vi, (onx, cfg) in enumerate(vozes):
            for i, f in enumerate(frases):
                w = os.path.join(d, 'v%d-%d.wav' % (vi, i)); subprocess.run(['piper', '--model', onx, '--config', cfg, '--output_file', w], input=f, text=True, capture_output=True, timeout=300)
                if os.path.exists(w): wavs.append((w, f))
        res['voz']['frases'] = len(wavs); res['voz']['aviso'] = 'voz sintética em português europeu: serve de indicação, não substitui o ensaio com vozes verdadeiras'
        norm = lambda s: re.sub(r'[^\w\s-]', '', s.lower()).replace('-', ' ')
        for tam in ['base', 'small', 'medium', 'large-v3-turbo']:
            try:
                t0 = time.time(); m = WhisperModel(tam, device='cpu', compute_type='int8'); carga = time.time() - t0; ref, hip, exemplos = [], [], []; t0 = time.time()
                for w, f in wavs:
                    seg, _ = m.transcribe(w, language='pt', beam_size=5, initial_prompt='Transcrição em português de Portugal.'); t = ' '.join(s.text.strip() for s in seg); ref.append(norm(f)); hip.append(norm(t)); exemplos.append({'dito': f, 'ouvido': t})
                res['voz'][tam] = {'erro_palavras_pct': round(100 * jiwer.wer(ref, hip), 1), 'segundos_por_frase': round((time.time() - t0) / max(1, len(wavs)), 1), 'segundos_carga': round(carga, 1), 'exemplos': exemplos}; del m
            except Exception as e: res['voz'][tam] = {'erro': repr(e)[:300]}
            guardar()
    except Exception as e: res['voz']['erro'] = traceback.format_exc()[-900:]
    guardar()

qual = sys.argv[1] if len(sys.argv) > 1 else 'tudo'
if qual in ('voz', 'tudo'): voz()
if qual in ('gemma', 'tudo'):
    litert('Gemma 4 E2B (2,6 GB)', 'litert-community/gemma-4-E2B-it-litert-lm', 'gemma-4-E2B-it.litertlm')
    litert('Gemma 4 E4B (3,7 GB)', 'litert-community/gemma-4-E4B-it-litert-lm', 'gemma-4-E4B-it.litertlm')
if qual in ('outros', 'tudo'):
    gguf('EuroLLM 1.7B', ['bartowski/EuroLLM-1.7B-Instruct-GGUF', 'mradermacher/EuroLLM-1.7B-Instruct-GGUF', 'QuantFactory/EuroLLM-1.7B-Instruct-GGUF'])
    gguf('Qwen 3 4B', ['bartowski/Qwen_Qwen3-4B-GGUF', 'unsloth/Qwen3-4B-GGUF', 'Qwen/Qwen3-4B-GGUF'])
    gguf('Gemma 3 4B', ['bartowski/google_gemma-3-4b-it-GGUF', 'unsloth/gemma-3-4b-it-GGUF', 'lmstudio-community/gemma-3-4b-it-GGUF'])
    gguf('Gemma 3 1B', ['bartowski/google_gemma-3-1b-it-GGUF', 'unsloth/gemma-3-1b-it-GGUF'])
guardar(); print(json.dumps({k: (len(v.get('respostas', [])), v.get('erro', '')[:200]) for k, v in res['modelos'].items()}, ensure_ascii=False)); print(json.dumps({k: (v.get('erro_palavras_pct') if isinstance(v, dict) else v) for k, v in res['voz'].items()}, ensure_ascii=False))
# ensaio lançado em 2026-11-17 21:16
