import base64
import json
import os
from datetime import date, datetime
from html import escape
from pathlib import Path

import requests

BREVO_URL = "https://api.brevo.com/v3/smtp/email"
DIAS_URGENTE = 3

# Vagas cujo titulo contenha estas palavras sao destacadas e ficam primeiro.
PALAVRAS_RELEVANTES = (
    "desenvolvedor",
    "programador",
    "developer",
    "software",
    "analista de dados",
    "dados",
    "data",
    "ti ",
    "informatica",
    "informática",
    "sistemas",
)

ESTILOS_ESTADO = {
    "Ativa": ("#166534", "#dcfce7"),
    "Indeterminada": ("#92400e", "#fef3c7"),
}
ESTILO_ESTADO_DEFAULT = ("#374151", "#e5e7eb")


def _txt(valor, padrao="Não indicado"):
    """Escapa HTML e trata valores vazios."""
    if valor is None:
        return padrao
    valor = str(valor).strip()
    return escape(valor) if valor else padrao


def _url_seguro(url):
    if isinstance(url, str) and url.strip().lower().startswith(
        ("http://", "https://")
    ):
        return escape(url.strip(), quote=True)
    return ""


def _data(valor):
    try:
        return datetime.strptime(str(valor), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _fmt_data(d):
    return d.strftime("%d/%m/%Y") if d else "Não indicada"


def _relevante(titulo):
    t = f"{titulo.lower()} "
    return any(p in t for p in PALAVRAS_RELEVANTES)


def _analisar_vaga(vaga, ref):
    """Calcula campos derivados usados na ordenacao e no template."""
    titulo = str(vaga.get("vaga") or "").strip()
    prazo = _data(vaga.get("prazo_candidatura"))
    publicacao = _data(vaga.get("data_publicacao"))
    estado = str(vaga.get("estado") or "Indeterminada").strip()

    dias = (prazo - ref).days if prazo else None
    expirada = dias is not None and dias < 0
    urgente = dias is not None and 0 <= dias <= DIAS_URGENTE
    data_suspeita = bool(
        (publicacao and publicacao > ref)
        or (prazo and (prazo - ref).days > 365)
    )

    return {
        "raw": vaga,
        "titulo": titulo,
        "estado": estado,
        "prazo": prazo,
        "publicacao": publicacao,
        "dias": dias,
        "expirada": expirada,
        "urgente": urgente,
        "data_suspeita": data_suspeita,
        "relevante": _relevante(titulo),
    }


def _chave_ordenacao(v):
    ordem_estado = {"Ativa": 0, "Indeterminada": 1}.get(v["estado"], 2)
    return (
        0 if v["relevante"] else 1,
        ordem_estado,
        v["prazo"] or date.max,
        v["titulo"].lower(),
    )


def _badge(texto, cor, fundo):
    return (
        f'<span style="display:inline-block;padding:3px 10px;'
        f"border-radius:12px;font-size:12px;font-weight:600;"
        f'color:{cor};background:{fundo};margin:0 6px 6px 0;">'
        f"{texto}</span>"
    )


def _texto_prazo(v):
    if v["prazo"] is None:
        return "Não indicado"
    base = _fmt_data(v["prazo"])
    if v["expirada"]:
        return f"{base} (expirado)"
    if v["dias"] == 0:
        return f"{base} (termina hoje)"
    if v["dias"] == 1:
        return f"{base} (falta 1 dia)"
    return f"{base} (faltam {v['dias']} dias)"


def _linha_info(rotulo, valor):
    return (
        "<tr>"
        '<td style="padding:3px 0;width:110px;font-size:13px;'
        f'color:#6b7280;vertical-align:top;">{rotulo}</td>'
        '<td style="padding:3px 0;font-size:13px;color:#111827;">'
        f"{valor}</td></tr>"
    )


def _card_vaga(v):
    raw = v["raw"]
    cor, fundo = ESTILOS_ESTADO.get(v["estado"], ESTILO_ESTADO_DEFAULT)

    badges = _badge(_txt(v["estado"]), cor, fundo)
    if v["relevante"]:
        badges = _badge("Relevante", "#1e3a8a", "#dbeafe") + badges
    if v["urgente"]:
        badges += _badge("Prazo a terminar", "#991b1b", "#fee2e2")
    if v["expirada"]:
        badges += _badge("Expirada", "#374151", "#e5e7eb")
    if v["data_suspeita"]:
        badges += _badge("Datas a verificar", "#92400e", "#fef3c7")

    cor_prazo = "#991b1b" if (v["urgente"] or v["expirada"]) else "#111827"

    descricao = _txt(raw.get("descricao"), "")
    bloco_descricao = (
        '<p style="margin:12px 0 0 0;font-size:13px;line-height:1.5;'
        f'color:#4b5563;">{descricao}</p>'
        if descricao
        else ""
    )

    requisitos = _txt(raw.get("requisitos"), "")
    bloco_requisitos = (
        '<p style="margin:8px 0 0 0;font-size:13px;line-height:1.5;'
        f'color:#4b5563;"><b>Requisitos:</b> {requisitos}</p>'
        if requisitos
        else ""
    )

    url = _url_seguro(raw.get("url_candidatura")) or _url_seguro(
        raw.get("url_anuncio")
    )
    botao = (
        '<table role="presentation" cellpadding="0" cellspacing="0" '
        'style="margin-top:16px;"><tr><td style="background:#1d4ed8;'
        'border-radius:6px;">'
        f'<a href="{url}" style="display:inline-block;padding:10px 20px;'
        "font-size:14px;font-weight:600;color:#ffffff;"
        'text-decoration:none;">Ver anúncio</a></td></tr></table>'
        if url
        else ""
    )

    info = (
        _linha_info("Empresa", _txt(raw.get("empresa")))
        + _linha_info("Local", _txt(raw.get("local")))
        + _linha_info("Contrato", _txt(raw.get("tipo_contrato")))
        + _linha_info(
            "Publicação",
            _fmt_data(v["publicacao"]),
        )
        + _linha_info(
            "Prazo",
            f'<span style="color:{cor_prazo};font-weight:600;">'
            f"{escape(_texto_prazo(v))}</span>",
        )
    )

    return (
        '<tr><td style="padding:0 0 16px 0;">'
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" style="background:#ffffff;border:1px solid '
        '#e5e7eb;border-radius:8px;"><tr><td style="padding:20px;">'
        f"<div>{badges}</div>"
        '<h3 style="margin:6px 0 12px 0;font-size:17px;line-height:1.3;'
        f'color:#111827;">{_txt(v["titulo"], "Vaga sem título")}</h3>'
        '<table role="presentation" width="100%" cellpadding="0" '
        f'cellspacing="0">{info}</table>'
        f"{bloco_descricao}{bloco_requisitos}{botao}"
        "</td></tr></table></td></tr>"
    )


def _metrica(valor, rotulo, cor="#111827"):
    return (
        '<td align="center" style="padding:14px 6px;">'
        f'<div style="font-size:26px;font-weight:700;color:{cor};">'
        f"{valor}</div>"
        f'<div style="font-size:12px;color:#6b7280;margin-top:2px;">'
        f"{rotulo}</div></td>"
    )


def _construir_html(dados, vagas, ref):
    total = len(vagas)
    ativas = sum(1 for v in vagas if v["estado"] == "Ativa")
    urgentes = sum(1 for v in vagas if v["urgente"])
    relevantes = sum(1 for v in vagas if v["relevante"])

    site = _txt(dados.get("url_analisado"))
    site_url = _url_seguro(dados.get("url_analisado"))
    site_html = (
        f'<a href="{site_url}" style="color:#93c5fd;'
        f'text-decoration:none;">{site}</a>'
        if site_url
        else site
    )

    preheader = (
        f"{ativas} ativas, {urgentes} a terminar em breve, "
        f"{relevantes} relevantes para o teu perfil."
    )

    if vagas:
        cards = "".join(_card_vaga(v) for v in vagas)
    else:
        cards = (
            '<tr><td style="padding:24px;background:#ffffff;'
            "border:1px solid #e5e7eb;border-radius:8px;"
            'font-size:14px;color:#4b5563;text-align:center;">'
            "Não foram identificadas vagas nesta análise.</td></tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório de vagas</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;\
font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;\
color:transparent;">{escape(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" \
style="background:#f3f4f6;">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" \
style="width:100%;max-width:600px;">

<tr><td style="background:#0f172a;border-radius:8px 8px 0 0;\
padding:28px 24px;">
<div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;\
color:#94a3b8;">Monitor de Vagas</div>
<h1 style="margin:6px 0 10px 0;font-size:22px;color:#ffffff;">\
Relatório de vagas</h1>
<div style="font-size:13px;color:#cbd5e1;line-height:1.6;">\
Fonte: {site_html}<br>Análise: {escape(_fmt_data(ref))}</div>
</td></tr>

<tr><td style="background:#ffffff;border:1px solid #e5e7eb;\
border-top:none;padding:0;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr>
{_metrica(total, "Total")}
{_metrica(ativas, "Ativas", "#166534")}
{_metrica(urgentes, "A terminar", "#991b1b" if urgentes else "#111827")}
{_metrica(relevantes, "Relevantes", "#1d4ed8" if relevantes else "#111827")}
</tr>
</table>
</td></tr>

<tr><td style="padding:20px 0 4px 0;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
{cards}
</table>
</td></tr>

<tr><td style="padding:8px 12px 0 12px;text-align:center;\
font-size:12px;line-height:1.6;color:#6b7280;">
O ficheiro vagas.json segue em anexo.<br>
Ordenação: relevantes, estado e prazo mais próximo.<br>
Relatório gerado automaticamente. Confirma sempre os dados no site oficial.
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def _construir_texto(dados, vagas, ref):
    linhas = [
        "RELATORIO DE VAGAS",
        f"Fonte: {dados.get('url_analisado', 'Nao indicado')}",
        f"Analise: {_fmt_data(ref)}",
        f"Total: {len(vagas)}",
        "",
    ]
    for v in vagas:
        raw = v["raw"]
        linhas += [
            f"- {v['titulo'] or 'Vaga sem titulo'}",
            f"  Empresa: {raw.get('empresa') or 'Nao indicado'}",
            f"  Local: {raw.get('local') or 'Nao indicado'}",
            f"  Estado: {v['estado']}",
            f"  Prazo: {_texto_prazo(v)}",
            f"  Link: {raw.get('url_candidatura') or raw.get('url_anuncio') or ''}",
            "",
        ]
    return "\n".join(linhas)


def enviar_relatorio(ficheiro_json="vagas.json"):
    api_key = os.getenv("BREVO_API_KEY")
    remetente = os.getenv("BREVO_SENDER_EMAIL")
    nome_remetente = os.getenv("BREVO_SENDER_NAME", "Monitor de Vagas")
    destinatario = os.getenv("DESTINATARIO")

    if not api_key or not remetente:
        raise RuntimeError("Configura BREVO_API_KEY e BREVO_SENDER_EMAIL.")

    caminho = Path(ficheiro_json)
    if not caminho.exists():
        raise FileNotFoundError(f"JSON nao encontrado: {caminho}")

    dados = json.loads(caminho.read_text(encoding="utf-8"))

    ref = _data(dados.get("data_analise")) or date.today()
    vagas = sorted(
        (_analisar_vaga(v, ref) for v in dados.get("vagas", [])),
        key=_chave_ordenacao,
    )

    ativas = sum(1 for v in vagas if v["estado"] == "Ativa")
    urgentes = sum(1 for v in vagas if v["urgente"])

    assunto = f"Vagas: {ativas} ativas"
    if urgentes:
        assunto += f", {urgentes} a terminar em breve"
    assunto += f" ({_fmt_data(ref)})"

    payload = {
        "sender": {"name": nome_remetente, "email": remetente},
        "to": [{"email": destinatario}],
        "subject": assunto,
        "htmlContent": _construir_html(dados, vagas, ref),
        "textContent": _construir_texto(dados, vagas, ref),
    }

    resposta = requests.post(
        BREVO_URL,
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    if not resposta.ok:
        raise RuntimeError(
            f"Erro Brevo ({resposta.status_code}): {resposta.text}"
        )

    print("[Brevo] Relatorio enviado para o remetente.")
    return resposta.json()
