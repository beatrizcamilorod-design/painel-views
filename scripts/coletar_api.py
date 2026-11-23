# -*- coding: utf-8 -*-
"""Coleta views dos Reels e seguidores do @data_academy_hub pela API oficial (Instagram Graph API)
e regenera o data.json do painel. Sem navegador e sem IA.

Precisa da variável de ambiente META_TOKEN (token de página do Facebook ligado ao Instagram,
com instagram_basic, instagram_manage_insights, pages_show_list e pages_read_engagement).
Escreve 'ok=true' em $GITHUB_OUTPUT quando a coleta deu certo."""
import csv, json, os, re, sys, urllib.error, urllib.parse, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DADOS = os.path.join(ROOT, "dados")
API = "https://graph.facebook.com/v22.0/"
USUARIO = "data_academy_hub"
TOKEN = os.environ.get("META_TOKEN", "").strip()


def saida(ok):
    p = os.environ.get("GITHUB_OUTPUT")
    if p:
        with open(p, "a") as f:
            f.write(f"ok={'true' if ok else 'false'}\n")


def get(path_or_url, **params):
    if path_or_url.startswith("http"):
        url = path_or_url
    else:
        params["access_token"] = TOKEN
        url = API + path_or_url + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=40) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", "replace")
        try:
            msg = json.loads(corpo)["error"]["message"]
        except Exception:
            msg = corpo[:300]
        raise RuntimeError(f"API {e.code}: {msg}") from None


def conta_instagram():
    campos = "instagram_business_account{id,username,followers_count}"
    try:  # token de página
        ig = get("me", fields=campos).get("instagram_business_account")
        if ig:
            return ig
    except RuntimeError:
        pass
    for pg in get("me/accounts", fields=campos).get("data", []):  # token de usuário
        ig = pg.get("instagram_business_account")
        if ig and ig.get("username") == USUARIO:
            return ig
    raise RuntimeError("Não achei o Instagram @" + USUARIO + " ligado a este token.")


def views_do_reel(mid):
    for metrica in ("views", "plays", "ig_reels_aggregated_all_plays_count"):
        try:
            d = get(f"{mid}/insights", metric=metrica).get("data", [])
            if d:
                return int(d[0]["values"][0]["value"])
        except RuntimeError:
            continue
    return None


def titulo_curto(legenda):
    linha = (legenda or "").strip().split("\n")[0].strip()
    m = re.match(r"PARTE\s*(\d+)\s*[—-]\s*(.*)", linha, re.I)
    if m:
        return ("Tessa Parte " + m.group(1) + " — " + m.group(2))[:60].rstrip(" .!?😱😭😎")
    base = re.sub(r"[^\w\sÀ-ÿ?!.,:;()+=*/#\-—→]", "", linha).strip()
    prefixo = "Meme: " if "#memes" in (legenda or "").lower() else "Dica: "
    return (prefixo + base)[:60].rstrip(" .,")


def main():
    if not TOKEN:
        print("META_TOKEN não configurado: nada coletado.")
        saida(False)
        return 0
    ig = conta_instagram()
    reels = []
    url = None
    pagina = get(f"{ig['id']}/media", fields="id,caption,media_product_type,permalink,timestamp", limit=50)
    while True:
        for m in pagina.get("data", []):
            if m.get("media_product_type") == "REELS":
                reels.append(m)
        url = pagina.get("paging", {}).get("next")
        if not url:
            break
        pagina = get(url)

    titulos = json.load(open(os.path.join(DADOS, "titulos.json"), encoding="utf-8"))
    publicados = json.load(open(os.path.join(DADOS, "publicados.json"), encoding="utf-8"))
    agora = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M")
    linhas = []
    for m in reels:
        sc = re.search(r"/(?:reel|p)/([^/?]+)", m.get("permalink", ""))
        if not sc:
            continue
        cod = sc.group(1)
        v = views_do_reel(m["id"])
        if v is None:
            continue
        if cod not in titulos:
            titulos[cod] = titulo_curto(m.get("caption"))
        if cod not in publicados and m.get("timestamp"):
            publicados[cod] = m["timestamp"][:19] + "Z"
        linhas.append([agora, "Instagram", cod, titulos[cod], v])
    if not linhas:
        print("A API respondeu, mas nenhum Reel veio com views.")
        saida(False)
        return 1
    linhas.append([agora, "Instagram", "_seguidores", "Seguidores", int(ig.get("followers_count", 0))])

    with open(os.path.join(DADOS, "historico.csv"), "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(linhas)
    json.dump(titulos, open(os.path.join(DADOS, "titulos.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(publicados, open(os.path.join(DADOS, "publicados.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    sys.path.insert(0, HERE)
    import gerar_painel
    gerar_painel.main()
    total = sum(l[4] for l in linhas if l[2] != "_seguidores")
    print(f"ok {agora}: {len(linhas) - 1} Reels, {total} views, {ig.get('followers_count')} seguidores")
    saida(True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as e:
        print("Falhou:", e)
        saida(False)
        sys.exit(1)
