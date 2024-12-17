import redis

def clear_redis():
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    r.delete("todo_urls")  # Elimina la lista de URLs pendientes
    r.delete("done_urls")  # Elimina el conjunto de URLs procesadas
    print("Redis keys 'todo_urls', 'done_urls', images y failed_images han sido eliminadas.")

def delete_all_image_keys():
    """Borra todas las claves relacionadas con imágenes (descargadas y falladas) en Redis."""
    r = redis.StrictRedis(host='localhost', port=6379, db=0)

    # Buscar y eliminar todas las claves relacionadas con imágenes
    patterns = ["images:*", "failed_images:*", "last_downloaded_image:*"]  # Patrones para imágenes exitosas y falladas
    for pattern in patterns:
        print(f"Eliminando claves que coinciden con: {pattern}")
        for key in r.scan_iter(pattern):
            r.delete(key)
            print(f"Clave eliminada: {key.decode()}")

    print("Todas las claves relacionadas con imágenes han sido eliminadas.")

if __name__ == "__main__":
    clear_redis()
    delete_all_image_keys()
