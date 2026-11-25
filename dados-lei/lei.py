#!/usr/bin/env python3
# Dados públicos de legislação: lê o repositório aberto legalize-pt (Diário da República, 1.ª série, em texto)
# e prepara um índice dos diplomas, a estrutura dos diplomas consolidados e a lista de quem menciona quem.
# Uso: python3 lei.py <pasta do legalize-pt> <pasta de saída>
import os, re, sys, json, collections, datetime

ORIG, SAI = sys.argv[1], sys.argv[2]
REGS = (('pt', ''), ('pt-20', 'A'), ('pt-30', 'M'))

TIPO = {
    'lei': 'lei', 'lei-organica': 'lo', 'lei-constitucional': 'lc', 'decreto-lei': 'dl',
    'decreto-regulamentar': 'dr', 'decreto': 'd', 'decreto-governo': 'dg', 'portaria': 'p', 'portaria-extracto': 'p', 'portaria-extrato': 'p',
    'resolucao-conselho-ministros': 'rcm', 'resolucao-assembleia-republica': 'rar', 'resolucao': 'r',
    'despacho-normativo': 'dn', 'despacho-normativo-extracto': 'dn', 'despacho-normativo-extrato': 'dn',
    'declaracao-rectificacao': 'ret', 'declaracao-retificacao': 'ret', 'declaracao-retificacao-extrato': 'ret', 'declaracao-rectificacao-extracto': 'ret',
    'decreto-presidente-republica': 'dpr', 'decreto-legislativo-regional': 'dlr', 'decreto-regional': 'dlr',
    'decreto-regulamentar-regional': 'drr', 'acordao-tribunal-constitucional': 'atc', 'acordao-supremo-tribunal-justica': 'astj',
    'assento': 'ass', 'decreto-aprovacao-constituicao': 'crp', 'despacho': 'desp', 'aviso': 'av', 'aviso-banco-portugal': 'avbp',
    'regulamento-cmvm': 'rcmvm', 'regulamento': 'reg', 'declaracao': 'decl', 'deliberacao': 'delib',
}
ESTADO = {'VIGENTE': 'v', 'NAO_VIGENTE': 'r', 'VIGENCIA_CONDICIONADA': 'p', 'CADUCADO': 'c'}
ESTADO2 = {'repealed': 'r', 'partially_repealed': 'p', 'expired': 'c'}

def cab(t):
    m = t.split('\n---', 1)[0]
    return dict(re.findall(r'^(\w+): "(.*)"\s*$', m, re.M))

def numero(on, ano_pub, reg):
    """devolve (numero, ano, regiao) a partir do número oficial"""
    if not on: return None
    on = re.sub(r'\s*\(.*$', '', on).strip()
    on = re.sub(r',.*$', '', on)
    m = re.match(r'^(\d+(?:-[A-Z]{1,2})?)(?:/(\d{2,4}))?(?:[/-]([AM12]))?$', on)
    if not m: return None
    n, a, r = m.group(1), m.group(2), m.group(3)
    if a is None: a = ano_pub
    elif len(a) == 2: a = '19' + a
    elif len(a) == 3: return None
    if r in ('1', '2'): r = ''
    return n, a, (r or reg or '')

ART = re.compile(r'^#{6}\s+Art(?:igo|\.)\s+(\d+)\.?[ºª°]?(?:\s*-\s*([A-Z]{1,2})\b)?\.?\s*(?:—\s*(.*)|(\S.*))?$')
ART_UNICO = re.compile(r'^#{6}\s+Artigo\s+único\b\.?\s*(?:—\s*(.*)|(\S.*))?$', re.I)
REV = re.compile(r'^[\[(]\s*Revogad[oa]s?\b[^\])]*[\])]\.?$', re.I)
NUM = re.compile(r'^(\d+)\s*[-–—.]\s+(.*)$')
ALI = re.compile(r'^([a-z]{1,2})\)\s+(.*)$')

def estrutura(linhas):
    """blocos de artigos: [{n: nome do bloco, a: [[num, epigrafe, revogado, estrutura]]}]"""
    blocos, cur, titulo, pend = [], None, '', None
    def fecha():
        nonlocal pend
        if pend is None: return
        num, ep, corpo = pend
        txt = [l.strip() for l in corpo if l.strip()]
        rev = 1 if (len(txt) >= 1 and all(REV.match(x) for x in txt)) or (ep and REV.match(ep.strip())) else 0
        partes, atual = [], None
        for l in txt:
            m = NUM.match(l)
            if m and (not partes or int(m.group(1)) == int(re.match(r'\d+', partes[-1][0]).group()) + 1 or int(m.group(1)) == 1 and not partes):
                atual = [m.group(1), 1 if REV.match(m.group(2).strip()) else 0, []]; partes.append(atual); continue
            m = ALI.match(l)
            if m:
                if atual is None: atual = ['0', 0, []]; partes.append(atual)
                atual[2].append(m.group(1) + ('!' if REV.match(m.group(2).strip()) else ''))
        s = ','.join(p[0] + ('!' if p[1] else '') + ('(' + ' '.join(p[2]) + ')' if p[2] else '') for p in partes)
        cur['a'].append([num, (ep or '')[:90], rev, s])
        pend = None
    for l in linhas:
        if l.startswith('#'):
            m = ART.match(l); u = None if m else ART_UNICO.match(l)
            if m or u:
                fecha()
                num = (m.group(1) + ('-' + m.group(2) if m.group(2) else '')) if m else 'U'
                ep = (m.group(3) if m else u.group(1)) or ''
                na_linha = (m.group(4) if m else u.group(2)) or ''
                if cur is None or (num in ('1', 'U') and cur['a']):
                    cur = {'n': titulo if blocos else '', 'a': []}; blocos.append(cur)
                pend = (num, ep, [na_linha] if na_linha else [])
                continue
            h = re.match(r'^(#{1,2})\s+(.*)$', l)
            if h and re.search(r'anexo|c[óo]digo|regulamento|estatuto|regime|lei\b|bases', h.group(2), re.I):
                titulo = re.sub(r'^Anexo\s*[IVX\d]*\s*—\s*', '', h.group(2)).strip()[:90]
                # um anexo sem artigos (modelo, lista) fecha o artigo em curso
                fecha()
            continue
        if pend is not None: pend[2].append(l)
    fecha()
    return [b for b in blocos if b['a']]

# --- menções a diplomas no texto
TIPOS_TXT = [
    (r'Leis?\s+Constituciona(?:l|is)', 'lc'), (r'Leis?\s+Orgânicas?', 'lo'), (r'Decretos?-Leis?', 'dl'),
    (r'Decretos?\s+Legislativos?\s+Regiona(?:l|is)', 'dlr'), (r'Decretos?\s+Regulamentar(?:es)?\s+Regiona(?:l|is)', 'drr'),
    (r'Decretos?\s+Regulamentar(?:es)?', 'dr'), (r'Decretos?\s+do\s+Presidente\s+da\s+República', 'dpr'), (r'Decretos?\s+do\s+Governo', 'dg'),
    (r'Decretos?\s+Regiona(?:l|is)', 'dlr'),
    (r'Resoluç(?:ão|ões)\s+do\s+Conselho\s+de\s+Ministros', 'rcm'), (r'Resoluç(?:ão|ões)\s+da\s+Assembleia\s+da\s+República', 'rar'),
    (r'Despachos?\s+Normativos?', 'dn'), (r'Declaraç(?:ão|ões)\s+de\s+Rec?tificação', 'ret'),
    (r'Portarias?', 'p'), (r'Leis?', 'lei'), (r'Decretos?', 'd'),
]
RE_NO = re.compile(r'n\.\s?(?:º|°|o|<sup>o)s?(?:</sup>)?\.?\s*(?=\d)')
RE_TIPO_FIM = re.compile(r'(?<![\w-])(?:' + '|'.join('(?P<t%d>%s)' % (i, p) for i, (p, _) in enumerate(TIPOS_TXT)) + r')\s+$', re.I)
MES = r'(?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)'
RE_NUM = re.compile(r'(\d[\d ]{0,6}\d|\d)(?:-([A-Z]{1,2}))?(?:/(\d{4}|\d{2}))?(?:/([AM]))?(?:,?\s+de\s+(\d{1,2})\s+de\s+(' + MES + r')(?:\s+de\s+(\d{4}))?)?', re.I)
RE_SEP = re.compile(r'\s*(?:,\s*e\s+|,\s*|\s+e\s+|;\s*)(?=\d)')
RE_ARTS = re.compile(r'artigos?\s+(\d+\.?[ºª°]?(?:-[A-Z])?(?:(?:\s*,\s*(?:e\s+)?|\s+e\s+|\s+a\s+|\s+ou\s+)\d+\.?[ºª°]?(?:-[A-Z])?)*)\s*,?\s*(?:ambos\s+|todos\s+)?d[oa]s?\s+(?:referid[oa]s?\s+|citad[oa]s?\s+|mencionad[oa]s?\s+)?$', re.I)
RE_SALTA = re.compile(r'(alterad|redac?ç|rec?tificad|republicad|revogad|modificad|aditad|na\s+versão)[^.;]{0,60}$', re.I)

RE_LINK = re.compile(r'\[([^\]]{1,200})\]\s?\((?:https?:)[^)\s]+\)')

RE_CESSA = re.compile(r'revogad|cessação\s+de\s+vigência|deixam?\s+de\s+vigorar|cessam?\s+a\s+(?:sua\s+)?vigência|não\s+se\s+encontram?\s+em\s+vigor|considera(?:m)?-se\s+(?:não\s+vigentes|caducad)', re.I)

def mencoes(linha):
    """devolve [(tipo, numero, ano, regiao, artigos_alvo, saltar)]"""
    out, pos, ult_salta = [], 0, False
    for no in RE_NO.finditer(linha):
        if no.start() < pos: continue
        mt = RE_TIPO_FIM.search(linha[max(0, no.start() - 48):no.start()])
        if not mt: continue
        t = next(TIPOS_TXT[i][1] for i in range(len(TIPOS_TXT)) if mt.group('t%d' % i))
        ini = max(0, no.start() - 48) + mt.start()
        antes = linha[max(0, ini - 160):ini]
        salta = bool(RE_SALTA.search(antes)) or (ult_salta and pos and re.match(r'^\s*,?\s*(?:e\s+|bem\s+como\s+)?(?:ainda\s+)?pel[oa]s?\s+$', linha[pos:ini]) is not None)
        ult_salta = salta
        ma = RE_ARTS.search(antes)
        arts = re.findall(r'\d+(?:-[A-Z])?', re.sub(r'[.ºª°]', '', ma.group(1))) if ma else []
        if ma and re.search(r'\d\s*[ºª°.]*\s+a\s+\d', ma.group(1)) and len(arts) == 2 and arts[0].isdigit() and arts[1].isdigit() and 0 < int(arts[1]) - int(arts[0]) < 60:
            arts = [str(x) for x in range(int(arts[0]), int(arts[1]) + 1)]
        p = no.end()
        while True:
            n = RE_NUM.match(linha, p)
            if not n: break
            num = n.group(1).replace(' ', '') + ('-' + n.group(2).upper() if n.group(2) else '')
            ano = n.group(3) or n.group(7)
            if ano and len(ano) == 2: ano = '19' + ano
            if ano or len(num) >= 4:
                out.append((t, num, ano or '', (n.group(4) or '').upper(), arts, salta))
            p = n.end()
            s = RE_SEP.match(linha, p)
            if not s: break
            p = s.end()
        pos = p
    return out

# --- artigos revogados por inteiro: o texto consolidado da fonte conserva o texto antigo, pelo que se lê a norma revogatória
import unicodedata
def reduz(t):
    t = unicodedata.normalize('NFD', t); t = ''.join(c for c in t if unicodedata.category(c) != 'Mn').lower()
    t = re.sub(r'c(?=[tc])', '', t); t = re.sub(r'p(?=[tc])', '', t); t = re.sub(r'[^a-z0-9]+', ' ', t)
    return ' '.join(w for w in t.split() if not re.match(r'^(d[aeo]s?|e|a|o|as|os|em|n[ao]s?|para|ao|aos)$', w))
RE_NOMEADO = re.compile(r'((?:Código|Estatuto|Regime\s+(?:Jurídico|Geral)|Lei\s+(?:Geral|de\s+Bases|Quadro|Orgânica|de\s+Enquadramento)|Regulamento\s+(?:Geral|das|dos|de|do|da))(?:\s+(?:d[aoe]s?|e|em|à|ao|aos|às|para|sobre|n[ao]s?|com|por|entre|a|o|as|os)|\s+[A-ZÀ-Ý][\wÀ-ÿ-]*){1,14})')
RE_REVOGA = re.compile(r'(?:^|[^\w])(?:é|são|fica|ficam|consideram-se|considera-se)\s+(?:igualmente\s+|também\s+|ainda\s+|expressamente\s+)?revogad[oa]s?(?!\w)', re.I)
RE_ARTIGO_INTEIRO = re.compile(r'(?<![\w])os?\s+artigos?\s+(\d+\.?[ºª°](?:-[A-Z]{1,2})?(?:(?:\s*,\s*(?:e\s+)?|\s+e\s+|\s+a\s+)\d+\.?[ºª°](?:-[A-Z]{1,2})?)*)', re.I)

S_ARTN = r'\d+\.?[ºª°](?:-[A-Z]{1,2})?'
S_SEP = r'(?:\s*,\s*(?:e\s+)?|\s+e\s+|\s+a\s+)'
RE_NUM_ART = re.compile(r'(?<![\w])os?\s+n\.[ºo°]s?\s*(\d+(?:' + S_SEP + r'\d+)*)\s+do\s+artigo\s+(' + S_ARTN + ')', re.I)
RE_AL_ART = re.compile(r'(?<![\w])as?\s+alíneas?\s+([a-z]{1,2}\)(?:' + S_SEP + r'[a-z]{1,2}\))*)\s+do\s+(?:n\.[ºo°]\s*(\d+)\s+do\s+)?artigo\s+(' + S_ARTN + ')', re.I)
RE_TOCA = re.compile(r'passam?\s+a\s+ter\s+a\s+seguinte\s+redac?ção|(?:é|são)\s+aditad[oa]s?|(?:é|são)\s+alterad[oa]s?|nova\s+redac?ção', re.I)

def lista_nums(t):
    toks = re.findall(r'(\d+)|(\s+a\s+)', t); out = []
    for i, (n, a) in enumerate(toks):
        if a:
            if out and i + 1 < len(toks) and toks[i + 1][0]:
                de, ate = int(out[-1]), int(toks[i + 1][0])
                if 0 < ate - de <= 60: out.extend(str(x) for x in range(de + 1, ate))
        else: out.append(n)
    return out
def lista_als(t):
    toks = re.findall(r'([a-z]{1,2})\)|(\s+a\s+)', t); out = []
    for i, (n, a) in enumerate(toks):
        if a:
            if out and i + 1 < len(toks) and toks[i + 1][0] and len(out[-1]) == 1 and len(toks[i + 1][0]) == 1:
                out.extend(chr(x) for x in range(ord(out[-1]) + 1, ord(toks[i + 1][0])) if chr(x) not in 'kwy')
        else: out.append(n)
    return out
def art_norm(t):
    m = re.match(r'(\d+)\.?[ºª°](?:-([A-Z]{1,2}))?', t); return m.group(1) + ('-' + m.group(2) if m.group(2) else '')

def ancoras_pos(linha, nomes_k):
    """diplomas na linha, com posição: [(ini, fim, ('t', tipo, num, ano, reg) ou ('id', identificador))]"""
    out, pos = [], 0
    for no in RE_NO.finditer(linha):
        if no.start() < pos: continue
        mt = RE_TIPO_FIM.search(linha[max(0, no.start() - 48):no.start()])
        if not mt: continue
        t = next(TIPOS_TXT[i][1] for i in range(len(TIPOS_TXT)) if mt.group('t%d' % i))
        ini = max(0, no.start() - 48) + mt.start()
        n = RE_NUM.match(linha, no.end())
        if not n: continue
        num = n.group(1).replace(' ', '') + ('-' + n.group(2).upper() if n.group(2) else '')
        ano = n.group(3) or n.group(7) or ''
        if len(ano) == 2: ano = '19' + ano
        out.append((ini, n.end(), ('t', t, num, ano, (n.group(4) or '').upper()))); pos = n.end()
    for m in RE_NOMEADO.finditer(linha):
        pal = m.group(1).split()
        for k in range(len(pal), 1, -1):
            ident = nomes_k.get(reduz(' '.join(pal[:k])))
            if ident:
                out.append((m.start(), m.start() + len(' '.join(pal[:k])), ('id', ident))); break
    out.sort()
    return out

def expande_arts(txt):
    toks = re.findall(r'(\d+)\.?[ºª°](?:-([A-Z]{1,2}))?|(\s+a\s+)', txt); out = []
    i = 0
    while i < len(toks):
        n, suf, a = toks[i]
        if a:
            if out and i + 1 < len(toks) and toks[i + 1][0] and out[-1].isdigit() and not toks[i + 1][1]:
                de, ate = int(out[-1]), int(toks[i + 1][0])
                if 0 < ate - de <= 300: out.extend(str(x) for x in range(de + 1, ate))
        else: out.append(n + ('-' + suf if suf else ''))
        i += 1
    return out

def main():
    os.makedirs(SAI, exist_ok=True)
    indice = collections.defaultdict(list)       # ano -> entradas
    porid, chave = {}, {}                        # identificador -> entrada ; chave -> [identificadores]
    estr = collections.defaultdict(dict)         # ano -> id -> blocos
    nomes = []
    ficheiros = []
    for pasta, reg in REGS:
        base = os.path.join(ORIG, pasta)
        if not os.path.isdir(base): continue
        for ano in sorted(os.listdir(base)):
            d = os.path.join(base, ano)
            if not os.path.isdir(d): continue
            for f in sorted(os.listdir(d)):
                if f.endswith('.md'): ficheiros.append((pasta, reg, ano, f))
    # 1.ª passagem: índice e estrutura
    for k, (pasta, reg, ano, f) in enumerate(ficheiros):
        with open(os.path.join(ORIG, pasta, ano, f), encoding='utf8') as h: t = h.read()
        c = cab(t)
        rank = c.get('rank', '')
        tp = TIPO.get(rank, rank)
        pub = c.get('publication_date', '')
        nn = numero(c.get('official_number'), pub[:4] or ano, reg)
        raw = c.get('in_force_raw')
        est = ESTADO.get(raw) if raw else (ESTADO2.get(c.get('status')) or ('v' if c.get('eli_in_force') == 'InForce-inForce' else 's'))
        est = est or 's'
        cons = 1 if c.get('surface') == 'cons' else 0
        ident = c.get('identifier') or f[:-3]
        st = c.get('short_title') or c.get('summary') or ''
        e = {'id': ident, 'rk': rank, 'pa': pasta, 'ano': ano, 't': tp, 'n': nn[0] if nn else '', 'a': nn[1] if nn else (pub[:4] or ano), 'r': nn[2] if nn else reg,
             'd': pub, 's': est, 'c': cons, 'st': st[:110], 'la': c.get('last_amendment', ''), 'u': c.get('last_updated', ''), 'dep': c.get('department', '')[:80]}
        porid[ident] = e
        if nn: chave.setdefault((tp, nn[0], nn[1], nn[2]), []).append(ident)
        if cons:
            corpo = t.split('\n---', 1)[1] if '\n---' in t else t
            b = estrutura(corpo.split('\n'))
            if b: estr[ano][ident] = b
            m = re.match(r'^(.{4,90}?)\s+-\s+([A-ZÇÃÉÍÓÚ][A-Za-zÇÃÉÍÓÚ]{1,11})$', st)
            if m and est != 'r': nomes.append([m.group(1).strip(), m.group(2), ident])
            elif est != 'r' and re.match(r'^(Código|Constituição|Estatuto|Regime|Lei|Regulamento)\b', st) and len(st) < 90 and not re.match(r'^(Aprova|Altera|Estabelece|Regula|Procede)', st):
                nomes.append([st.strip(), '', ident])
        if k % 20000 == 0: print('índice', k, len(ficheiros), flush=True)
    # designação legível
    NOME_T = {'lei': 'Lei', 'lo': 'Lei Orgânica', 'lc': 'Lei Constitucional', 'dl': 'Decreto-Lei', 'dr': 'Decreto Regulamentar', 'd': 'Decreto', 'dg': 'Decreto do Governo',
              'p': 'Portaria', 'rcm': 'Resolução do Conselho de Ministros', 'rar': 'Resolução da Assembleia da República', 'r': 'Resolução', 'dn': 'Despacho Normativo',
              'ret': 'Declaração de Retificação', 'dpr': 'Decreto do Presidente da República', 'dlr': 'Decreto Legislativo Regional', 'drr': 'Decreto Regulamentar Regional'}
    def desig(e):
        if not e: return ''
        nm = NOME_T.get(e['t'], e['t'].replace('-', ' ').capitalize())
        if not e['n']: return nm + ' de ' + e['d'][8:10] + '/' + e['d'][5:7] + '/' + e['d'][:4]
        a = int(e['a'] or 0)
        return nm + ' n.º ' + e['n'] + ('/' + (e['a'][2:] if a < 2000 else e['a']) if a >= 1976 or len(e['n']) < 4 else '') + ('/' + e['r'] if e['r'] else '')
    for ano_num in sorted({e['a'] for e in porid.values()}):
        pass
    for e in porid.values():
        la = porid.get(e['la'])
        linha = [e['rk'], e['n'], e['r'], e['d'], e['s'], e['c'], e['id'], e['pa'][2:], e['st'], (desig(la) + '|' + la['d']) if la else '', e['u'] if e['c'] else '']
        indice[e['a']].append(linha)
    os.makedirs(os.path.join(SAI, 'i'), exist_ok=True); os.makedirs(os.path.join(SAI, 'e'), exist_ok=True); os.makedirs(os.path.join(SAI, 'c'), exist_ok=True)
    for a, ls in indice.items():
        ls.sort(key=lambda x: (x[0], x[1].zfill(8)))
        json.dump(ls, open(os.path.join(SAI, 'i', a + '.json'), 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
    for a, d in estr.items():
        json.dump(d, open(os.path.join(SAI, 'e', a + '.json'), 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
    sa = {}
    for (tt, nn, aa, rr), v in chave.items():
        if int(aa) < 1976 and len(nn) >= 4 and len(v) == 1: sa[tt + '|' + nn] = aa
    json.dump(sa, open(os.path.join(SAI, 'semano.json'), 'w', encoding='utf8'), separators=(',', ':'))
    json.dump(nomes, open(os.path.join(SAI, 'nomes.json'), 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))

    # 2.ª passagem: quem menciona quem (só articulado de diplomas que não estão revogados)
    def resolve(t, num, ano, reg):
        if ano:
            ids = chave.get((t, num, ano, reg)) or (chave.get((t, num, ano, 'A' if reg == '' else reg)) if False else None)
            if not ids and t == 'd': ids = chave.get(('dg', num, ano, reg))
            if not ids and t == 'ret': ids = None
            return ids[0] if ids and len(ids) == 1 else None
        c = [i for (tt, nn, aa, rr), v in () for i in v]
        return None
    semano = collections.defaultdict(list)
    for (tt, nn, aa, rr), v in chave.items():
        if int(aa) < 1975 and len(nn) >= 4: semano[(tt, nn)].extend(v)
    nomes_k = {reduz(re.sub(r'\s*\(.*?\)\s*$', '', x[0])): x[2] for x in nomes}
    toques = collections.defaultdict(lambda: collections.defaultdict(dict))  # artigos com nova redacção ou aditados, e quando
    revs = collections.defaultdict(lambda: collections.defaultdict(dict))   # ano (pasta) do alvo -> id alvo -> artigo -> [designação de quem revoga, data]
    cit = collections.defaultdict(lambda: collections.defaultdict(list))   # ano alvo -> id alvo -> [[id citante, artigo citante, artigos alvo]]
    mortas = []
    tot = collections.Counter()
    for k, (pasta, reg, ano, f) in enumerate(ficheiros):
        ident = f[:-3]; e = porid.get(ident)
        if not e:
            with open(os.path.join(ORIG, pasta, ano, f), encoding='utf8') as h: c0 = cab(h.read(4000))
            e = porid.get(c0.get('identifier'))
        if not e or e['t'] in ('ret', 'atc', 'astj', 'ass', 'dpr', 'rar'): continue
        with open(os.path.join(ORIG, pasta, ano, f), encoding='utf8') as h: t = h.read()
        corpo = t.split('\n---', 1)[1] if '\n---' in t else t
        # normas revogadas e normas com nova redacção noutros diplomas: lê-se a norma revogatória e os artigos de alteração
        if 'evogad' in corpo or 'redação' in corpo or 'redacção' in corpo or 'aditad' in corpo:
            em_rev, em_toca, alvo_intro = False, False, None
            def alvo_de(alvo_k):
                if not alvo_k: return None
                if alvo_k[0] == 'id': ids = [alvo_k[1]]
                elif alvo_k[3]: ids = chave.get((alvo_k[1], alvo_k[2], alvo_k[3], alvo_k[4])) or []
                else: ids = semano.get((alvo_k[1], alvo_k[2])) or []
                return porid[ids[0]] if len(ids) == 1 and ids[0] != e['id'] else None
            for l in corpo.split('\n'):
                if l.startswith('#'):
                    cab_l = l
                    em_rev = bool(re.search(r'revogat', l, re.I)); em_toca = bool(re.search(r'alteraç|aditament', l, re.I)); alvo_intro = None
                    l = re.sub(r'^#+\s*Art(?:igo|\.)\s+\S+\s*(?:—\s*)?', '', l) if re.match(r'^#{6}\s+Art', l) else ''
                    if em_toca and l:
                        ac = ancoras_pos(RE_LINK.sub(r'\1', l), nomes_k)
                        if ac: alvo_intro = ac[0][2]
                    if not l or re.search(r'—', cab_l): continue
                if not l.strip(): continue
                if l.lstrip().startswith('«') or l.lstrip().startswith('"'): em_rev = False; em_toca = False; continue
                l = RE_LINK.sub(r'\1', l) if '[' in l else l
                l = re.sub(r'</?sup>', '', l)
                tem_r = RE_REVOGA.search(l); tem_t = RE_TOCA.search(l)
                if tem_r: em_rev = True
                if not (em_rev or tem_t): continue
                anc = ancoras_pos(l, nomes_k)
                if l.rstrip().endswith(':') and anc and not tem_t: alvo_intro = anc[-1][2]
                modo_toca = bool(tem_t) and not tem_r
                # diploma revogado por inteiro: "É revogado o Decreto-Lei n.º ...", "a) A Lei n.º ..."
                if not modo_toca:
                    for (a_ini, a_fim, a_k) in anc:
                        if a_k[0] != 't': continue
                        if not re.search(r'(?:^|[:;,]\s*|\se\s+|revogad[oa]s?\s+)(?:[a-z]{1,2}\)\s*)?[oa]s?\s+$', l[:a_ini], re.I): continue
                        al = alvo_de(a_k)
                        if not al or al['s'] != 'r' or e['d'] < al['d']: continue
                        ant = revs[al['ano']][al['id']].get('*')
                        if not ant or ant[1] > e['d']: revs[al['ano']][al['id']]['*'] = [desig(e), e['d']]
                        tot['diplomas revogados'] += 1
                for sm in re.finditer(r'[^;]+', l):
                    seg_ini, seg = sm.start(), sm.group(0)
                    def destino(fim, ini):
                        if modo_toca and re.search(r'aditad', l, re.I):
                            antes = [a for a in anc if a[1] <= ini]
                            if antes: return alvo_de(antes[-1][2])
                        prox = next((a for a in anc if a[0] >= fim and a[0] < seg_ini + len(seg) + 1), None)
                        return alvo_de(prox[2] if prox else alvo_intro)
                    for ma in RE_ARTIGO_INTEIRO.finditer(seg):
                        fim = seg_ini + ma.end()
                        if re.match(r'^\s*,?\s*(?:d[oa]\s+presente|d[oa]\s+anexo|deste|desta)', l[fim:fim + 40], re.I): continue
                        al = destino(fim, seg_ini + ma.start())
                        if not al or e['d'] < al['d']: continue
                        for a_num in expande_arts(ma.group(1)):
                            reg = (toques if modo_toca else revs)[al['ano']][al['id']]
                            ant = reg.get(a_num)
                            if not ant or ant[1] < e['d']: reg[a_num] = [desig(e), e['d']]
                            tot['artigos tocados' if modo_toca else 'artigos revogados'] += 1
                    if modo_toca: continue
                    for mn in RE_NUM_ART.finditer(seg):
                        al = destino(seg_ini + mn.end(), seg_ini + mn.start())
                        if not al or e['d'] < al['d']: continue
                        for nn_ in lista_nums(mn.group(1)):
                            revs[al['ano']][al['id']][art_norm(mn.group(2)) + ':' + nn_] = [desig(e), e['d']]; tot['números revogados'] += 1
                    for ml in RE_AL_ART.finditer(seg):
                        al = destino(seg_ini + ml.end(), seg_ini + ml.start())
                        if not al or e['d'] < al['d']: continue
                        for aa_ in lista_als(ml.group(1)):
                            revs[al['ano']][al['id']][art_norm(ml.group(3)) + ':' + (ml.group(2) or '0') + ':' + aa_] = [desig(e), e['d']]; tot['alíneas revogadas'] += 1
        if e['s'] in ('r', 'c'): continue
        if re.search(r'cessação\s+de\s+vigência|SIMPLEGIS|não\s+vigência', e['st'], re.I): continue
        art, ep, salta_art, vistos, rev_lista = None, '', False, set(), False
        for l in corpo.split('\n'):
            if l.startswith('#'): rev_lista = False
            elif l.strip():
                # lista de uma norma revogatória ("São revogados:" seguido de alíneas), também quando vem citada
                if RE_REVOGA.search(l): rev_lista = l.rstrip().endswith(':')
                elif rev_lista and not re.match(r'^\s*[«"]?\s*(?:[a-z]{1,2}\)|[ivx]+\))', l): rev_lista = False
                elif rev_lista: continue
            if l.startswith('#'):
                m = ART.match(l); u = None if m else ART_UNICO.match(l)
                if m or u:
                    art = (m.group(1) + ('-' + m.group(2) if m.group(2) else '')) if m else 'U'
                    ep = ((m.group(3) if m else u.group(1)) or '')
                    salta_art = bool(re.search(r'revoga|alteraç|aditament|republica|rec?tifica', ep, re.I))
                    l = (m.group(4) if m else u.group(2)) or ''
                    if not l: continue
                    # diplomas antigos: o texto vem na linha do artigo; uma alteração diz-se no próprio texto
                    if re.match(r'^(?:É|São|Fica|Ficam|O|Os|A|As)\b.{0,200}?(revogad|alterad|substituíd|passam? a ter|nova redac|aditad)', l): salta_art = True
                else: continue
            if art is None or 'n.' not in l: continue
            if RE_CESSA.search(l): continue
            l = l.replace('](', '] (') if '](' in l else l
            if '[' in l: l = RE_LINK.sub(r'\1', l)
            for (tt, num, an, rg, arts, salta) in mencoes(l):
                if an: ids = chave.get((tt, num, an, rg)) or (chave.get(('dg', num, an, rg)) if tt == 'd' else None)
                else: ids = semano.get((tt, num))
                if not ids or len(ids) != 1: tot['por resolver'] += 1; continue
                alvo = porid[ids[0]]
                if alvo['id'] == e['id']: continue
                tot['menções'] += 1
                if salta or salta_art: tot['de alteração'] += 1; continue
                ch = (alvo['id'], art, ','.join(arts))
                if ch in vistos: continue
                vistos.add(ch)
                cit[alvo['a']][alvo['id']].append([e['id'], art, ','.join(arts)])
                if alvo['s'] == 'r':
                    la = porid.get(alvo['la'])
                    # só conta se o diploma citante é anterior à revogação conhecida, ou se não se conhece a data
                    mortas.append([e['id'], art, alvo['id'], ','.join(arts)])
        if k % 20000 == 0: print('menções', k, len(ficheiros), dict(tot), flush=True)
    os.makedirs(os.path.join(SAI, 'rv'), exist_ok=True)
    for a, d in revs.items():
        # uma norma revogada que voltou a ter redacção num diploma posterior deixa de contar
        for ident, m in d.items():
            tq = toques.get(a, {}).get(ident, {})
            for k in list(m.keys()):
                t0 = tq.get(k.split(':')[0]) if k != '*' else None
                if t0 and t0[1] > m[k][1]: del m[k]; tot['revogações superadas'] += 1
        d = {k: v for k, v in d.items() if v}
        json.dump(d, open(os.path.join(SAI, 'rv', a + '.json'), 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
    for a, d in cit.items():
        json.dump(d, open(os.path.join(SAI, 'c', a + '.json'), 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
    # Observatório das Remissões: remissões de diplomas vigentes para diplomas revogados
    def data_pt(d): return d[8:10] + '/' + d[5:7] + '/' + d[:4]
    def desig_d(e):
        return desig(e)
    obs_alvos = collections.Counter(); obs_cit = set(); por_dec = collections.Counter(); por_tipo = collections.Counter(); depois = []
    vistos_par = set()
    for (cid, art, aid, arts) in mortas:
        c, a = porid[cid], porid[aid]
        if c['s'] != 'v': continue
        if (cid, aid) in vistos_par: continue
        vistos_par.add((cid, aid))
        obs_alvos[aid] += 1; obs_cit.add(cid); por_dec[c['d'][:3] + '0'] += 1; por_tipo[NOME_T.get(c['t'], c['t'])] += 1
        rv = revs.get(a['ano'], {}).get(aid, {}).get('*')
        if rv and c['d'] > rv[1]:
            depois.append([c['d'], desig_d(c), c['st'], art, desig_d(a), a['st'], rv[0], rv[1], c['rk'], c['n'], c['id'].split('-')[-1], c['a'], a['rk'], a['n'], a['id'].split('-')[-1], a['a']])
    depois.sort(reverse=True)
    topo = []
    for aid, n in obs_alvos.most_common(40):
        a = porid[aid]; rv = revs.get(a['ano'], {}).get(aid, {}).get('*')
        topo.append([desig_d(a), a['d'], a['st'], n, rv[0] if rv else '', rv[1] if rv else '', a['rk'], a['n'], a['id'].split('-')[-1], a['a']])
    json.dump({'feito': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'ultimo': max(e['d'] for e in porid.values() if e['d']),
               'pares': len(vistos_par), 'citantes': len(obs_cit), 'alvos': len(obs_alvos), 'vigentes': sum(1 for e in porid.values() if e['s'] == 'v'),
               'decadas': sorted(por_dec.items()), 'tipos': por_tipo.most_common(8), 'topo': topo, 'depois_total': len(depois), 'depois': depois[:400]},
              open(os.path.join(SAI, 'observatorio.json'), 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
    tot['remissões posteriores à revogação'] = len(depois)
    est = collections.Counter(e['s'] for e in porid.values())
    json.dump({'feito': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'diplomas': len(porid), 'consolidados': sum(len(d) for d in estr.values()),
               'estados': dict(est), 'nomes': len(nomes), 'mencoes': tot['menções'], 'mortas': len(mortas), 'anos': sorted(indice.keys()),
               'ultimo': max(e['d'] for e in porid.values() if e['d'])},
              open(os.path.join(SAI, 'estado.json'), 'w', encoding='utf8'), ensure_ascii=False)
    print('feito', len(porid), dict(tot), len(mortas))

def vigia():
    # Para os diplomas da lista (dados-lei/vigia.txt), publica uma impressão digital de cada artigo: quem usa as regras desses artigos fica a saber quando o texto muda.
    import hashlib, glob
    lista = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vigia.txt')
    if not os.path.exists(lista): return
    os.makedirs(os.path.join(SAI, 'v'), exist_ok=True)
    re_art = re.compile(r'^#{6}\s+Artigo\s+(?:(\d+)\.?[ºª°]?(?:\s*-\s*([A-Z]{1,2}))?|(único))(?![\wÀ-ÿ])', re.I)
    for ident in [l.split('#')[0].strip() for l in open(lista, encoding='utf8')]:
        if not ident: continue
        fs = glob.glob(os.path.join(ORIG, 'pt*', '*', ident + '.md'))
        if not fs: continue
        txt = open(fs[0], encoding='utf8').read(); arts = {}; cur = None
        m = re.search(r'^last_updated: "([^"]+)"', txt, re.M)
        for l in txt.split('\n'):
            if l.startswith('#'):
                a = re_art.match(l)
                if a:
                    n = 'U' if a.group(3) else a.group(1) + ('-' + a.group(2) if a.group(2) else '')
                    cur = []; arts.setdefault(n, []).append(cur)
                else: cur = None
                continue
            if cur is not None: cur.append(l)
        h = {}
        for n, blocos in arts.items():
            t = '\n§\n'.join(re.sub(r'[ \t\r\n\u00a0]+', ' ', '\n'.join(b)).strip() for b in blocos)
            h[n] = hashlib.sha1(t.encode('utf8')).hexdigest()[:12]
        # última intervenção registada no Diário da República (serve para os diplomas sem texto consolidado)
        ui = ''
        try:
            for r in json.load(open(os.path.join(SAI, 'i', ident.split('-')[1] + '.json'), encoding='utf8')):
                if r[6] == ident: ui = r[9] or ''; break
        except Exception: pass
        json.dump({'u': m.group(1) if m else '', 'ui': ui, 'a': h}, open(os.path.join(SAI, 'v', ident + '.json'), 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))

if __name__ == '__main__':
    main()
    vigia()
