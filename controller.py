from iterando import initialize_redis, run_scraper
from multiprocessing import Process

if __name__ == "__main__":
    # Inicializa Redis con las URLs desde el archivo externo
    initialize_redis("todo_urls.txt")

    # Crear múltiples procesos para ejecutar el scraper en paralelo
    num_processes = 1  # Cambia este número según la cantidad de procesos deseados
    processes = []

    for _ in range(num_processes):
        p = Process(target=run_scraper)
        p.start()
        processes.append(p)

    for p in processes:
        p.join()
