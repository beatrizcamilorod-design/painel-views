# -*- coding: utf-8 -*-
"""Lê historico.csv e grava data.json do painel (site/public e site/dist)."""
import csv, json, os
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
HERE = os.path.dirname(os.path.abspath(__file__))
# no repositório do GitHub: dados em ../dados e data.json na raiz do site
ROOT = os.path.dirname(HERE)
DADOS = os.environ.get("PAINEL_DADOS", os.path.join(ROOT, "dados"))
SAIDAS = os.environ.get("PAINEL_SAIDA", ROOT).split(os.pathsep)
from zoneinfo import ZoneInfo
AGORA_BR = lambda: datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)

def main():
    rows = list(csv.DictReader(open(os.path.join(DADOS, "historico.csv"), encoding="utf-8")))
    coletas = sorted({r["quando"] for r in rows})
    por = {c: {} for c in coletas}
    info = OrderedDict()
    seg = {}
    for r in rows:
        if r["id"] == "_seguidores":
            seg[r["quando"]] = int(r["views"]); continue
        por[r["quando"]][r["id"]] = int(r["views"])
        info[r["id"]] = (r["plataforma"], r["titulo"])
    # mantém o último valor conhecido de cada vídeo nas coletas seguintes (se faltar numa coleta)
    ultimo = {}
    cheio = []
    for c in coletas:
        ultimo.update(por[c]); cheio.append(dict(ultimo))
    ig = [sum(v for k, v in s.items() if info[k][0] == "Instagram") for s in cheio]
    tt = [sum(v for k, v in s.items() if info[k][0] == "TikTok") for s in cheio]
    agora = datetime.strptime(coletas[-1], "%Y-%m-%d %H:%M")
    base_i = 0
    for i, c in enumerate(coletas):
        if datetime.strptime(c, "%Y-%m-%d %H:%M") <= agora - timedelta(hours=24): base_i = i
    pub_path = os.path.join(DADOS, "publicados.json")
    pub = json.load(open(pub_path, encoding="utf-8")) if os.path.exists(pub_path) else {}
    videos = []
    for vid, (plat, tit) in info.items():
        serie = [s[vid] for s in cheio if vid in s]
        antes = cheio[base_i].get(vid, 0)
        link = f"https://www.instagram.com/data_academy_hub/reel/{vid}/" if plat == "Instagram" else "https://www.tiktok.com/@automatizei.sem.cd"
        videos.append({"id": vid, "titulo": tit, "plataforma": plat, "link": link, "publicado": pub.get(vid),
                       "views": serie[-1], "serie": serie[-48:], "ganho24h": max(0, serie[-1] - antes),
                       "ganhoUltima": max(0, serie[-1] - serie[-2]) if len(serie) > 1 else 0})
    # meta da semana (segunda 00:00 a domingo 23:59): views ganhas desde a 1ª coleta da semana
    meta_path = os.path.join(DADOS, "meta.json")
    meta_cfg = json.load(open(meta_path, encoding="utf-8")) if os.path.exists(meta_path) else {"views_semana": 20000}
    seg_ini = (agora - timedelta(days=agora.weekday())).replace(hour=0, minute=0)
    tot = [a + b for a, b in zip(ig, tt)]
    i0 = next(i for i, c in enumerate(coletas) if datetime.strptime(c, "%Y-%m-%d %H:%M") >= seg_ini)
    fim = seg_ini + timedelta(days=7)
    semana = {"meta": int(meta_cfg["views_semana"]), "ganho": tot[-1] - tot[i0], "inicio": seg_ini.strftime("%Y-%m-%d"),
              "fim": (fim - timedelta(days=1)).strftime("%Y-%m-%d"), "base": coletas[i0],
              "horasRestantes": max(0, round((fim - agora).total_seconds() / 3600))}
    # tipo de conteúdo e ritmo (views por hora desde a publicação)
    for v in videos:
        t = v["titulo"].lower()
        v["tipo"] = "Série da Tessa" if t.startswith("tessa") else "Dica" if t.startswith("dica") else "Meme" if t.startswith("meme") else "Outros"
        if v["publicado"]:
            horas = max(1.0, (datetime.now(timezone.utc).replace(tzinfo=None) - datetime.strptime(v["publicado"], "%Y-%m-%dT%H:%M:%SZ")).total_seconds() / 3600)
            v["ritmo"] = round(v["views"] / horas, 1); v["horas"] = round(horas)
        else:
            v["ritmo"] = None; v["horas"] = None
    tipos = {}
    for v in videos:
        tipos.setdefault(v["tipo"], []).append(v["views"])
    por_tipo = sorted(({"tipo": k, "videos": len(x), "total": sum(x), "media": round(sum(x) / len(x))} for k, x in tipos.items()), key=lambda r: -r["media"])

    # resumo e dicas automáticas (regras simples sobre os números)
    fmt = lambda n: f"{int(round(n)):,}".replace(",", ".")
    ganho24 = sum(v["ganho24h"] for v in videos)
    cresce = max(videos, key=lambda v: v["ganho24h"])
    pct = min(100, semana["ganho"] / semana["meta"] * 100)
    resumo = f"Nas últimas 24 h: +{fmt(ganho24)} views."
    if cresce["ganho24h"] > 0:
        resumo += f" O que mais cresce é “{cresce['titulo']}” (+{fmt(cresce['ganho24h'])})."
    resumo += f" Meta da semana: {(f'{pct:.1f}' if pct < 1 else f'{pct:.0f}').replace('.', ',')}%."
    dicas = []
    comp = [r for r in por_tipo if r["tipo"] != "Outros"]
    if len(comp) >= 2 and comp[-1]["media"] > 0:
        a, b = comp[0], comp[-1]
        x = a["media"] / b["media"]
        if x >= 1.5:
            dicas.append({"titulo": f"{a['tipo']} rende {x:.0f}x mais", "texto": f"Média de {fmt(a['media'])} views por vídeo, contra {fmt(b['media'])} em {b['tipo']}. Vale priorizar: {a['tipo']}.", "tom": "success", "acao": "Faz o roteiro do próximo episódio da série da Tessa pra eu aprovar."})
    if cresce["ganho24h"] > 0:
        dicas.append({"titulo": "Aproveite quem está em alta", "texto": f"“{cresce['titulo']}” ganhou +{fmt(cresce['ganho24h'])} views em 24 h. Repost nos stories enquanto ele está subindo.", "tom": "info", "acao": f"Cria um story chamando pro Reel “{cresce['titulo']}” (está em alta) e me mostra antes de postar."})
    parados = [v for v in videos if v["ganho24h"] == 0 and (v["horas"] or 0) > 24 and v["plataforma"] == "Instagram"]
    if parados:
        dicas.append({"titulo": (f"{len(parados)} vídeos pararam de crescer" if len(parados) > 1 else "1 vídeo parou de crescer"), "texto": f"Ex.: “{parados[0]['titulo']}”. Reaproveite num story com enquete ou faça uma continuação.", "tom": "warning", "acao": f"Cria um story com enquete reaproveitando o Reel “{parados[0]['titulo']}” e me mostra antes de postar."})
    tt_total = tt[-1]
    if tot[-1] and tt_total / tot[-1] < 0.02:
        dicas.append({"titulo": "TikTok quase parado", "texto": f"Só {fmt(tt_total)} views lá. Postar os mesmos Reels no TikTok é público novo sem esforço extra.", "tom": "warning", "acao": "Prepara os Reels prontos pra postar no TikTok @automatizei.sem.cd e me mostra antes."})
    falta = max(0, semana["meta"] - semana["ganho"])
    dias = semana["horasRestantes"] / 24
    if falta and dias > 0 and ganho24 < falta / dias:
        dicas.append({"titulo": "Ritmo abaixo da meta", "texto": f"Faltam {fmt(falta)} views: cerca de {fmt(falta / dias)} por dia. Nas últimas 24 h vieram {fmt(ganho24)}. Episódios da série puxam mais.", "tom": "danger", "acao": "Monta um plano pra bater a meta de views da semana e me mostra antes de agendar."})

    # próximos agendados
    ag_path = os.path.join(DADOS, "agenda.json")
    agenda = json.load(open(ag_path, encoding="utf-8")) if os.path.exists(ag_path) else []
    agora_real = AGORA_BR().strftime("%Y-%m-%d %H:%M")
    proximos = [a for a in sorted(agenda, key=lambda a: a["quando"]) if a["quando"] > agora_real][:6]

    out = {"atualizado": coletas[-1], "semana": semana, "porTipo": por_tipo, "resumo": resumo, "dicas": dicas[:3], "proximos": proximos, "agendaFutura": [a for a in sorted(agenda, key=lambda a: a["quando"]) if a["quando"][:10] >= agora_real[:10]],
           "agendadosSemana": len([a for a in agenda if a["quando"] > agora_real]), "coletas": coletas, "instagram": ig, "tiktok": tt,
           "seguidores": [seg.get(c) for c in coletas], "videos": videos}
    for p in SAIDAS:
        if os.path.isdir(p):
            json.dump(out, open(os.path.join(p, "data.json"), "w", encoding="utf-8"), ensure_ascii=False)
    return out

if __name__ == "__main__":
    print(main()["atualizado"])
