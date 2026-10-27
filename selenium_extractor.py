
import json
import time
from pathlib import Path
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait


def extrair_site(url: str, output_file="conteudo.txt") -> str:
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("URL invalido. Usa http:// ou https://.")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-notifications")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=pt-PT")

    driver = None

    try:
        print("[Selenium] A abrir o site...")

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)
        driver.get(url)

        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script(
                "return document.readyState"
            ) in ("interactive", "complete")
        )

        time.sleep(2)

        altura_anterior = 0
        repeticoes = 0

        for _ in range(15):
            driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight)"
            )
            time.sleep(0.7)

            altura = driver.execute_script(
                "return document.body.scrollHeight"
            )

            if altura == altura_anterior:
                repeticoes += 1
            else:
                repeticoes = 0

            altura_anterior = altura

            if repeticoes >= 2:
                break

        dados = driver.execute_script("""
            const links = Array.from(
                document.querySelectorAll('a[href]')
            ).map(a => ({
                texto: (
                    a.innerText ||
                    a.getAttribute('aria-label') ||
                    ''
                ).trim(),
                url: a.href
            })).filter(a =>
                a.url.startsWith('http://') ||
                a.url.startsWith('https://')
            );

            return {
                titulo: document.title,
                url: location.href,
                texto: document.body
                    ? document.body.innerText : '',
                links: links
            };
        """)

        links_unicos = []
        vistos = set()

        for link in dados["links"]:
            if link["url"] not in vistos:
                vistos.add(link["url"])
                links_unicos.append(link)

        conteudo = (
            f"TITULO: {dados['titulo']}\n"
            f"URL DA PAGINA: {dados['url']}\n\n"
            f"CONTEUDO VISIVEL:\n{dados['texto']}\n\n"
            f"LINKS ENCONTRADOS:\n"
            f"{json.dumps(links_unicos, ensure_ascii=False, indent=2)}"
        )

        destino = Path(output_file)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo, encoding="utf-8")

        print(f"[Selenium] Texto guardado em {destino}")
        print(f"[Selenium] Caracteres: {len(conteudo)}")

        return dados["url"]

    finally:
        if driver is not None:
            driver.quit()

