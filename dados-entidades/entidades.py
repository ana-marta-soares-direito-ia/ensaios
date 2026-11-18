#!/usr/bin/env python3
"""Organiza por entidade adjudicante os dados abertos oficiais dos contratos públicos (portal BASE, IMPIC, dados.gov.pt).

Lê os ficheiros anuais publicados em dados.gov.pt e escreve, na pasta de saída:
  a/<n>.json     contratos das entidades cujo NIF dá resto n na divisão por 1024:
                 { "n": { NIF: nome da entidade }, "c": { NIF: [ contrato, ... ] } }
                 contrato = [id, objecto, adjudicatário, NIF do adjudicatário, data de celebração (aaaammdd), preço contratual,
                             procedimento (índice), tipo (índice), prazo de execução em dias, data de fecho (aaaammdd ou 0),
                             preço total efectivo, data de publicação (aaaammdd)]
  a/estado.json  data da leitura, última data de celebração, anos lidos, dicionários de procedimentos e de tipos, contagens
São dados públicos. Uso: python entidades.py <pasta de saída> [primeiro ano]
"""
import collections, datetime, io, json, os, re, sys, traceback, unicodedata
import requests, openpyxl

API = "https://dados.gov.pt/api/1/datasets/contratos-publicos-portal-base-impic-contratos-de-2012-a-%d/"
HOJE = datetime.date.today()
UA = {"User-Agent": "Mozilla/5.0 (contratos publicos por entidade; dados abertos do IMPIC)"}
BALDES = 1024

def norm(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn")).strip()

def data_num(v):
    if isinstance(v, datetime.datetime): v = v.date()
    if isinstance(v, datetime.date): return v.year * 10000 + v.month * 100 + v.day
    s = str(v or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m: return int(m.group(1) + m.group(2) + m.group(3))
    m = re.match(r"(\d{2})[-/](\d{2})[-/](\d{4})", s)
    if m: return int(m.group(3) + m.group(2) + m.group(1))
    return 0

def numero(v):
    if isinstance(v, (int, float)): return float(v)
    s = re.sub(r"[€\s ]", "", str(v or ""))
    if not s: return 0.0
    if "," in s: s = s.replace(".", "").replace(",", ".")
    try: return float(s)
    except ValueError: return 0.0

def entidades(v):
    """Uma entidade por linha, em pares chave=valor separados por «|» (nifEntContrato=...|descEntContrato=...), ou «NIF - Nome»."""
    r = []
    for linha in str(v or "").replace("\r", "").split("\n"):
        linha = linha.strip()
        if not linha: continue
        if "=" in linha.split("|")[0]:
            d = {}
            for par in linha.split("|"):
                if "=" in par:
                    k, x = par.split("=", 1); d[k.strip().lower()] = x.strip()
            nif = d.get("nifentcontrato") or d.get("nipcentidade") or ""
            r.append((nif if re.fullmatch(r"\d{6,12}", nif) else "", d.get("descentcontrato") or d.get("entidade") or ""))
        else:
            m = re.match(r"^(\d{6,12})\s*-\s*(.*)$", linha)
            r.append((m.group(1), m.group(2).strip()) if m else ("", linha.lstrip("-").strip()))
    return r

def coluna(cab, *chaves):
    for ch in chaves:
        for i, c in enumerate(cab):
            if c == ch: return i
    for ch in chaves:
        for i, c in enumerate(cab):
            if ch in c: return i
    return -1

def recursos():
    for ano in (HOJE.year, HOJE.year + 1, HOJE.year - 1):
        try:
            r = requests.get(API % ano, headers=UA, timeout=60)
            if r.status_code == 200: return r.json()["resources"]
        except Exception as e:
            print("API %d: %s" % (ano, e))
    raise RuntimeError("Não foi possível ler a lista de ficheiros em dados.gov.pt")

def main():
    saida = os.path.join(sys.argv[1], "a"); primeiro = int(sys.argv[2]) if len(sys.argv) > 2 else HOJE.year - 5
    os.makedirs(saida, exist_ok=True)
    estado = {"gerado": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"), "fonte": "Dados abertos do portal BASE, publicados pelo IMPIC em dados.gov.pt", "baldes": BALDES, "anos": {}}
    rec = recursos(); procs, tipos = [], []; pi_, ti_ = {}, {}
    def idx(lista, mapa, v):
        v = str(v or "").strip()
        if v not in mapa: mapa[v] = len(lista); lista.append(v)
        return mapa[v]
    baldes = [dict(n={}, c=collections.defaultdict(list)) for _ in range(BALDES)]
    vistos = set(); total = 0; ultima = 0; hoje_num = HOJE.year * 10000 + HOJE.month * 100 + HOJE.day
    for ano in range(primeiro, HOJE.year + 1):
        cand = [x for x in rec if re.search(r"contratos%d\.xlsx$" % ano, (x.get("title") or "") + " " + (x.get("url") or ""), re.I)]
        info = estado["anos"][str(ano)] = {}
        if not cand: info["erro"] = "ficheiro não encontrado"; continue
        cand.sort(key=lambda x: x.get("last_modified") or "", reverse=True)
        info["modificado"] = cand[0].get("last_modified")
        try:
            r = requests.get(cand[0]["url"], headers=UA, timeout=1200); r.raise_for_status(); info["bytes"] = len(r.content)
            wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True, data_only=True); del r
            linhas = wb[wb.sheetnames[0]].iter_rows(values_only=True); cab = [norm(c).replace(" ", "") for c in next(linhas)]
            C = dict(id=coluna(cab, "idcontrato"), tipo=coluna(cab, "tipocontrato"), proc=coluna(cab, "tipoprocedimento"), obj=coluna(cab, "objectocontrato", "objetocontrato", "objecto", "objeto"),
                     adj=coluna(cab, "adjudicante", "adjudicantes"), ada=coluna(cab, "adjudicatarios", "adjudicatario"), cel=coluna(cab, "datacelebracaocontrato", "datacelebracao"), pub=coluna(cab, "datapublicacao"),
                     preco=coluna(cab, "precocontratual"), prazo=coluna(cab, "prazoexecucao"), fecho=coluna(cab, "datafechocontrato"), efe=coluna(cab, "precototalefetivo", "precototalefectivo"))
            lidas = boas = 0
            for row in linhas:
                lidas += 1
                g = lambda k: row[C[k]] if 0 <= C[k] < len(row) else None
                try: ident = int(float(g("id")))
                except Exception: continue
                cel = data_num(g("cel")); pub = data_num(g("pub")); d = cel or pub
                adj = entidades(g("adj"))
                if not d or d > hoje_num or ident in vistos or not adj: continue
                ada = entidades(g("ada"))
                try: prazo = int(float(g("prazo") or 0))
                except Exception: prazo = 0
                obj = re.sub(r"\s+", " ", str(g("obj") or "")).strip()[:200]
                tipo = " e ".join(x.strip() for x in str(g("tipo") or "").split("\n") if x.strip())
                linha = [ident, obj, ((ada[0][1][:80] + (" e outros" if len(ada) > 1 else "")) if ada else ""), ada[0][0] if ada else "", d, round(numero(g("preco")), 2), idx(procs, pi_, g("proc")), idx(tipos, ti_, tipo), prazo, data_num(g("fecho")), round(numero(g("efe")), 2), pub]
                posto = False
                for nif, nome in adj:  # nas compras conjuntas, o contrato fica em cada entidade adjudicante
                    if not re.fullmatch(r"\d{9}", nif): continue
                    b = baldes[int(nif) % BALDES]; b["c"][nif].append(linha); posto = True
                    if nome and nif not in b["n"]: b["n"][nif] = nome[:120]
                if posto:
                    vistos.add(ident); boas += 1; total += 1
                    if cel > ultima: ultima = cel
            info["linhas"] = lidas; info["aproveitadas"] = boas; wb.close(); print(ano, lidas, boas, flush=True)
        except Exception as e:
            info["erro"] = "%s: %s" % (type(e).__name__, e); print(ano, "ERRO", traceback.format_exc()[-800:], flush=True)
    estado.update({"contratos": total, "ultimaData": ultima, "procedimentos": procs, "tipos": tipos, "entidades": sum(len(b["c"]) for b in baldes), "primeiroAno": primeiro})
    falhados = [a for a, i in estado["anos"].items() if "erro" in i]
    if total < 100000 or falhados:
        print("LEITURA INCOMPLETA: nada foi escrito.", json.dumps(estado, ensure_ascii=False)[:1500]); sys.exit(1)
    maior = 0
    for n, b in enumerate(baldes):
        for l in b["c"].values(): l.sort(key=lambda x: (-x[4], -x[0]))
        txt = json.dumps({"n": b["n"], "c": b["c"]}, ensure_ascii=False, separators=(",", ":")); maior = max(maior, len(txt.encode("utf-8")))
        open(os.path.join(saida, "%d.json" % n), "w", encoding="utf-8").write(txt)
    estado["maiorFicheiro"] = maior
    json.dump(estado, open(os.path.join(saida, "estado.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("contratos:", total, "| entidades:", estado["entidades"], "| última data:", ultima, "| maior ficheiro:", maior)

if __name__ == "__main__":
    main()
