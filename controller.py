from iterando import initialize_redis, run_scraper
from multiprocessing import Process
import argparse

if __name__ == "__main__":
    # Parse command-line option to skip downloads
    parser = argparse.ArgumentParser(
        description='Iniciar scraper con opción de omitir descarga de imágenes'
    )
    parser.add_argument(
        '--skip-download',
        action='store_true',
        help='Si se especifica, se omite la descarga de imágenes, pero se generan los enlaces en description.json'
    )
    parser.add_argument(
        '--tor-disable',
        action='store_true',
        help='Desactiva el uso de Tor (no proxy)'
    )
    args = parser.parse_args()

    # Inicializa Redis con las URLs desde el archivo externo
    initialize_redis("todo_urls.txt")

    # Crear múltiples procesos para ejecutar el scraper en paralelo
    num_processes = 1  # Cambia este número según la cantidad de procesos deseados
    processes = []

    for _ in range(num_processes):
        # Pasar los flags skip_download y tor_disable a run_scraper
        p = Process(
            target=run_scraper,
            kwargs={
                'skip_download': args.skip_download,
                'tor_disable': args.tor_disable
            }
        )
        p.start()
        processes.append(p)

    for p in processes:
        p.join()
