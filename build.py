#!/usr/bin/env python3
"""Gera feriados.ics e o site estático a partir de data/feriados.json.

Uso: python3 build.py   (saída em ./public)
Sem dependências externas.
"""
import json
import shutil
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "public"
DOMINIO_UID = "feriados-patos-de-minas"


def pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo gregoriano anônimo / Meeus-Jones-Butcher)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return date(ano, mes, dia)


def data_do_feriado(f: dict, ano: int) -> date:
    if f["tipo"] == "fixo":
        return date(ano, f["mes"], f["dia"])
    p = pascoa(ano)
    if f["regra"] == "pascoa-2":
        return p - timedelta(days=2)
    if f["regra"] == "pascoa+60":
        return p + timedelta(days=60)
    raise ValueError(f"regra desconhecida: {f['regra']}")


def dobrar(linha: str) -> str:
    """Dobra linha em 75 octetos (RFC 5545 §3.1), sem partir caracteres UTF-8."""
    b = linha.encode("utf-8")
    if len(b) <= 75:
        return linha
    partes, atual, tam = [], "", 0
    limite = 75
    for ch in linha:
        n = len(ch.encode("utf-8"))
        if tam + n > limite:
            partes.append(atual)
            atual, tam, limite = "", 0, 74  # continuação começa com espaço
        atual += ch
        tam += n
    partes.append(atual)
    return "\r\n ".join(partes)


def esc(t: str) -> str:
    return t.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def gerar_eventos(dados: dict):
    ano_ini = dados["ano_inicial"]
    ano_fim = max(dados["ano_final_minimo"], date.today().year + 10)
    eventos = []
    for ano in range(ano_ini, ano_fim + 1):
        for f in dados["feriados"]:
            eventos.append((data_do_feriado(f, ano), f, ano))
    eventos.sort(key=lambda x: (x[0], x[1]["id"]))
    return eventos


def gerar_ics(dados: dict, eventos) -> str:
    stamp = dados["atualizado_em"].replace("-", "") + "T000000Z"
    L = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Feriados de Patos de Minas//PT-BR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Feriados de Patos de Minas",
        "X-WR-CALDESC:Feriados municipais de Patos de Minas - MG (por lei municipal)",
        "X-WR-TIMEZONE:America/Sao_Paulo",
        "REFRESH-INTERVAL;VALUE=DURATION:P1D",
        "X-PUBLISHED-TTL:P1D",
        # Brasil não adota horário de verão desde 2019; offset fixo -03:00.
        "BEGIN:VTIMEZONE",
        "TZID:America/Sao_Paulo",
        "BEGIN:STANDARD",
        "DTSTART:19700101T000000",
        "TZOFFSETFROM:-0300",
        "TZOFFSETTO:-0300",
        "TZNAME:-03",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]
    for d, f, ano in eventos:
        fim = d + timedelta(days=1)
        desc = f"Feriado municipal - {f['lei']}."
        if f["tipo"] == "movel":
            desc += f" Data móvel: {f['regra_texto']}."
        L += [
            "BEGIN:VEVENT",
            f"UID:{f['id']}-{ano}@{DOMINIO_UID}",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{d:%Y%m%d}",
            f"DTEND;VALUE=DATE:{fim:%Y%m%d}",
            f"SUMMARY:{esc(f['nome'])}",
            f"DESCRIPTION:{esc(desc)}",
            "LOCATION:Patos de Minas - MG",
            "CATEGORIES:Feriado municipal",
            "TRANSP:TRANSPARENT",
            "STATUS:CONFIRMED",
            "SEQUENCE:0",
            "END:VEVENT",
        ]
    L.append("END:VCALENDAR")
    return "\r\n".join(dobrar(x) for x in L) + "\r\n"


def main():
    dados = json.loads((ROOT / "data" / "feriados.json").read_text(encoding="utf-8"))
    eventos = gerar_eventos(dados)
    OUT.mkdir(exist_ok=True)
    (OUT / "feriados.ics").write_bytes(gerar_ics(dados, eventos).encode("utf-8"))

    site = {
        "atualizado_em": dados["atualizado_em"],
        "fontes": dados["fontes"],
        "feriados": [
            {k: f[k] for k in ("id", "nome", "tipo", "lei", "fontes") if k in f}
            | ({"regra_texto": f["regra_texto"]} if "regra_texto" in f else {})
            for f in dados["feriados"]
        ],
        "eventos": [
            {"data": d.isoformat(), "id": f["id"], "ano": ano} for d, f, ano in eventos
        ],
    }
    (OUT / "dados.json").write_text(json.dumps(site, ensure_ascii=False), encoding="utf-8")
    shutil.copy(ROOT / "site" / "index.html", OUT / "index.html")
    (OUT / ".nojekyll").write_text("")
    print(f"{len(eventos)} eventos gerados em {OUT}")


if __name__ == "__main__":
    main()
