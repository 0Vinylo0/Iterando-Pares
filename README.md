# Iterando-Pares
Este proyecto es un script en Python para sacar datos y imágenes de una web haciendo scraping

## Pares File Scraper

Este proyecto es un *scraper* de archivos diseñado para recorrer páginas de **pares.mcu.es** a través de TOR, utilizando Redis como sistema de almacenamiento temporal y cookies para descargar imágenes. El programa es capaz de procesar enlaces recursivamente, verificar imágenes descargadas, manejar errores y realizar descargas optimizadas.

## Descripción de los Archivos

### 1. `iterando.py`
- Define la clase principal **`ParesFileScraper`**, que realiza las siguientes acciones:
    - Procesamiento de URLs de tipo `description` y `contiene`.
    - Descarga de imágenes con manejo de cookies y control de reintentos.
    - Integración con Redis para manejar estados de URLs (pendientes, procesadas).
    - Uso de **TOR** como proxy para el anonimato.
- **Claves Importantes**:
    - `todo_urls`: Lista de URLs pendientes en Redis.
    - `done_urls`: Conjunto de URLs procesadas.
    - `images:<page_id>`: Imágenes descargadas.
    - `failed_images:<page_id>`: Imágenes con descarga fallida.

### 2. `delete.py`
- Script de limpieza que:
    - Borra las claves de Redis relacionadas con URLs pendientes y procesadas.
    - Elimina todas las claves relacionadas con imágenes (descargadas o fallidas).

### 3. `controller.py`
- Archivo de control principal para ejecutar el scraper.
- Funciones:
    - **Inicializar Redis** con URLs desde un archivo `todo_urls.txt`.
    - Ejecutar múltiples procesos en paralelo usando `multiprocessing`.

## Requisitos del Sistema

- **Python 3.8+**
- **Redis** instalado y en ejecución en `localhost`.
- **TOR** instalado y configurado para ejecutar en `socks5h://127.0.0.1:9050`.
- Dependencias:
    - `requests`
    - `beautifulsoup4`
    - `redis`
    - `multiprocessing` (built-in)
    - `os` (built-in)
    - `random` (built-in)
    - `re` (built-in)
    - `json` (built-in)
    - `subprocess` (built-in)
    - `time` (built-in)
    - `urllib` (built-in)

## Instalación

### 1. Clonar el Repositorio
```bash
git clone <URL_DEL_REPO>
cd <REPO_NAME>
```

### 2. Crear un Entorno Virtual (Opcional pero Recomendado)
```bash
python -m venv env
source env/bin/activate
```

### 3. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 4. Instalar y Configurar TOR
- Instala TOR desde su página oficial: [TOR Project](https://www.torproject.org/) o con:
  ```bash
  apt install tor
  ```
- Generamos una clave para tor con:
  ```bash
  tor --hash-password "mi_contraseña_segura"
  ```
- Edita el archivo de configuración `torrc` para activar el proxy:
 
- [Archivo /etc/tor/torrc](torrc)

- Inicia el servicio de TOR:
  ```bash
  systemctl start tor
  ```

### 5. Instalar y Configurar Redis
- Sigue las instrucciones de instalación de Redis: [Redis Download](https://redis.io/download).
- En linux si esta en tus repos con:
  ```bash
  apt install redis-server
  ```
- Inicia el servidor Redis en `localhost`:
  ```bash
  redis-server
  ```

## Ejecución del Programa

### 1. Preparar el Archivo de URLs
- Crea un archivo llamado `todo_urls.txt` con las URLs iniciales, por ejemplo:
  ```
  https://pares.mcu.es/ParesBusquedas20/catalogo/description/1235
  ```

### 2. Ejecutar el Controlador Principal
```bash
python3 controller.py
```
- Esto inicializa Redis con las URLs y ejecuta el scraper en paralelo.

### 3. Verificar el Progreso
Puedes monitorear las claves en Redis usando la CLI:
```bash
redis-cli
keys *
```

### 4. Limpiar Redis
Si deseas reiniciar el proceso, ejecuta:
```bash
python3 delete.py
```

## Salida del Programa

- **`description_data.json`**: Archivo JSON con las descripciones procesadas.
- **Carpeta `img`**: Contiene imágenes descargadas organizadas por ID de página.
- **Logs de errores**: Mostrados en consola.

## Mejoras Futuras
- Agregar reintento automático para imágenes fallidas.
- Implementar un sistema de logs más robusto con archivos.
- Integrar un sistema de notificaciones al finalizar el proceso.

---

Desarrollado por 0Vinylo0 para la práctica de scraping avanzado con Redis y TOR.
