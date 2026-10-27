
import time
from pathlib import Path

from selenium_extractor import extrair_site
from llm_analyzer import analisar_ficheiro
from brevo_sender import enviar_relatorio

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
URLS_FILE = BASE_DIR / "urls.txt"

INTERVALO_SEGUNDOS = 9 * 60 * 60

DATA_DIR.mkdir(parents=True, exist_ok=True)


def carregar_urls():
    if not URLS_FILE.exists():
        raise FileNotFoundError(f"Ficheiro não encontrado: {URLS_FILE}")

    urls = []

    for linha in URLS_FILE.read_text(encoding="utf-8").splitlines():
        url = linha.strip()

        if url and not url.startswith("#"):
            urls.append(url)

    return urls


def executar_ronda():
    urls = carregar_urls()

    if not urls:
        print("Nenhum URL configurado em urls.txt.")
        return

    print(f"\nA verificar {len(urls)} site(s)...")

    for indice, url in enumerate(urls, start=1):
        prefixo = f"site_{indice:02d}"

        conteudo_file = DATA_DIR / f"{prefixo}_conteudo.txt"
        vagas_file = DATA_DIR / f"{prefixo}_vagas.json"

        print(f"\n[{indice}/{len(urls)}] A verificar: {url}")

        try:
            url_final = extrair_site(
                url,
                output_file=str(conteudo_file)
            )

            resultado = analisar_ficheiro(
                input_file=str(conteudo_file),
                output_file=str(vagas_file),
                url_pagina=url_final
            )

            print(
                f"Vagas identificadas: "
                f"{resultado['total_vagas']}"
            )

            enviar_relatorio(str(vagas_file))
            print("Relatório enviado.")

        except KeyboardInterrupt:
            raise

        except Exception as erro:
            print(f"Erro ao processar {url}: {erro}")
            continue


def main():
    print("=== Monitor automático de vagas ===")
    print(f"Intervalo entre rondas: {INTERVALO_SEGUNDOS // 60} minutos")

    while True:
        inicio = time.monotonic()

        try:
            executar_ronda()

        except KeyboardInterrupt:
            print("\nMonitor interrompido.")
            break

        except Exception as erro:
            print(f"Erro na ronda: {erro}")

        duracao = time.monotonic() - inicio
        espera = max(0, INTERVALO_SEGUNDOS - duracao)

        print(f"\nRonda concluída em {duracao:.0f} segundos.")
        print(f"Próxima ronda em {espera:.0f} segundos.")

        try:
            time.sleep(espera)
        except KeyboardInterrupt:
            print("\nMonitor interrompido.")
            break


if __name__ == "__main__":
    main()

