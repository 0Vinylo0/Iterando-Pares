# iterando.py
import redis
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import os
import json
import time
import subprocess
import random
from playwright.sync_api import sync_playwright
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

class ParesFileScraper:
    def __init__(self, base_url="https://pares.mcu.es", skip_download=False):
        # Configurar sistema de logging
        self.setup_logging()
        self.logger.info(f"Inicializando ParesFileScraper con base_url={base_url}, skip_download={skip_download}")

        self.base_url = base_url
        self.skip_download = skip_download  # Nueva bandera para omitir descargas
        self.session = requests.Session()
        self.session.proxies = {
            "http": "socks5h://127.0.0.1:9050",
            "https": "socks5h://127.0.0.1:9050"
        }
        self.r = redis.StrictRedis(host='localhost', port=6379, db=0)
        self.description_file = "description_data.json"
        self.img_folder = "img"
        self.urls_description = self.load_existing_descriptions()
        self.cookie_file = f"cookies_{os.getpid()}.txt"  # Archivo único por proceso
        
    def setup_logging(self):
        """Configura el sistema de logging con múltiples handlers y niveles"""
        # Crear directorio de logs si no existe
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Configurar el logger principal
        self.logger = logging.getLogger('ParesFileScraper')
        self.logger.setLevel(logging.DEBUG)
        
        # Evitar duplicar handlers si ya existen
        if self.logger.handlers:
            return
        
        # Formatter para los logs
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - PID:%(process)d - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        
        # Handler para archivo general (INFO y superior)
        general_handler = RotatingFileHandler(
            os.path.join(log_dir, 'pares_scraper.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        general_handler.setLevel(logging.INFO)
        general_handler.setFormatter(formatter)
        
        # Handler para errores (ERROR y superior)
        error_handler = RotatingFileHandler(
            os.path.join(log_dir, 'pares_scraper_errors.log'),
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        
        # Handler para debug (todos los niveles)
        debug_handler = RotatingFileHandler(
            os.path.join(log_dir, 'pares_scraper_debug.log'),
            maxBytes=50*1024*1024,  # 50MB
            backupCount=2
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(formatter)
        
        # Handler para consola (INFO y superior)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        
        # Añadir handlers al logger
        self.logger.addHandler(general_handler)
        self.logger.addHandler(error_handler)
        self.logger.addHandler(debug_handler)
        self.logger.addHandler(console_handler)
        
        # Logger específico para descargas de imágenes
        self.image_logger = logging.getLogger('ParesFileScraper.Images')
        self.image_logger.setLevel(logging.DEBUG)
        
        image_handler = RotatingFileHandler(
            os.path.join(log_dir, 'image_downloads.log'),
            maxBytes=20*1024*1024,  # 20MB
            backupCount=3
        )
        image_handler.setLevel(logging.DEBUG)
        image_handler.setFormatter(formatter)
        self.image_logger.addHandler(image_handler)
        
        # Logger específico para Redis
        self.redis_logger = logging.getLogger('ParesFileScraper.Redis')
        self.redis_logger.setLevel(logging.DEBUG)
        
        redis_handler = RotatingFileHandler(
            os.path.join(log_dir, 'redis_operations.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=2
        )
        redis_handler.setLevel(logging.DEBUG)
        redis_handler.setFormatter(formatter)
        self.redis_logger.addHandler(redis_handler)

    def load_existing_descriptions(self):
        self.logger.info(f"Cargando descripciones existentes desde {self.description_file}")
        if os.path.exists(self.description_file):
            try:
                with open(self.description_file, "r", encoding='utf-8') as desc_file:
                    data = json.load(desc_file)
                    self.logger.info(f"Cargadas {len(data)} descripciones existentes")
                    return data
            except Exception as e:
                self.logger.error(f"Error cargando descripciones existentes: {e}")
                return {}
        else:
            self.logger.info("No se encontró archivo de descripciones existente, iniciando con diccionario vacío")
        return {}

    def save_descriptions(self):
        try:
            self.logger.debug(f"Guardando {len(self.urls_description)} descripciones en {self.description_file}")
            with open(self.description_file, "w", encoding='utf-8') as desc_file:
                json.dump(self.urls_description, desc_file, indent=4, ensure_ascii=False)
            self.logger.info(f"Descripciones guardadas exitosamente en {self.description_file}")
        except Exception as e:
            self.logger.error(f"Error guardando descripciones: {e}")

    def get_current_ip(self):
        """Obtiene la IP pública visible a través de Tor."""
        try:
            self.logger.debug("Obteniendo IP pública a través de Tor")
            # Cambia la URL por una de las opciones rápidas
            response = self.session.get("https://api64.ipify.org")
            ip = response.text.strip()
            self.logger.info(f"IP Pública obtenida: {ip}")
            print(f"IP Pública: {ip}")
        except Exception as e:
            self.logger.error(f"Error obteniendo la IP pública: {e}")
            print(f"Error obteniendo la IP pública: {e}")

    def get_next_url(self):
        self.redis_logger.debug("Obteniendo siguiente URL de Redis")

        # Verificar si hay URLs disponibles
        pending_count = self.r.llen("todo_urls")
        self.redis_logger.debug(f"URLs pendientes en cola: {pending_count}")

        if pending_count == 0:
            self.redis_logger.info("No hay URLs pendientes en la cola")
            return None

        try:
            # Usar lpop en lugar de blpop para evitar bloqueos
            url_bytes = self.r.lpop("todo_urls")
            if url_bytes:
                decoded_url = url_bytes.decode()
                self.redis_logger.info(f"URL obtenida de Redis: {decoded_url}")
                return decoded_url
            else:
                self.redis_logger.debug("No se obtuvo URL de Redis (cola vacía)")
                return None
        except Exception as e:
            self.redis_logger.error(f"Error obteniendo URL de Redis: {e}")
            return None

    def mark_as_done(self, url):
        # Marca una URL como completada en Redis
        try:
            self.r.sadd("done_urls", url)
            self.redis_logger.info(f"URL marcada como completada: {url}")
        except Exception as e:
            self.redis_logger.error(f"Error marcando URL como completada {url}: {e}")

    def is_done(self, url):
        # Verifica si la URL ya fue procesada
        try:
            is_done = self.r.sismember("done_urls", url)
            self.redis_logger.debug(f"Verificación de URL procesada {url}: {is_done}")
            return is_done
        except Exception as e:
            self.redis_logger.error(f"Error verificando si URL está procesada {url}: {e}")
            return False

    def get_page(self, url):
        try:
            self.logger.debug(f"Obteniendo página: {url}")
            self.get_current_ip()
            response = self.session.get(url)
            response.raise_for_status()
            self.logger.info(f"Página obtenida exitosamente: {url} (Tamaño: {len(response.text)} chars)")
            return response.text
        except requests.RequestException as e:
            self.log_error(f"Error fetching {url}: {e}")
            return None

    def parse_html_to_json(self, html_content):
        """
        Parsea el contenido HTML y lo convierte a un diccionario JSON con datos sanitizados.
        """
        self.logger.debug("Iniciando parseo de HTML a JSON")
        soup = BeautifulSoup(html_content, 'html.parser')
        data = {}

        # Buscar el contenedor principal
        wrapper = soup.find(id="wrapper_ficha")
        if not wrapper:
            self.logger.warning("No se encontró wrapper_ficha en el HTML")
            return data

        # Buscar la sección del área
        area = wrapper.find(class_="area")
        if not area:
            self.logger.warning("No se encontró sección 'area' en el HTML")
            return data

        # Buscar todas las secciones de información
        infos = area.find_all(class_="info")
        self.logger.debug(f"Encontradas {len(infos)} secciones de información")
        
        for info in infos:
            title_element = info.find('h4', class_='aviso')
            if title_element:
                title = title_element.get_text(strip=True).rstrip(':')
                value_element = info.find('p')

                if value_element:
                    # Sanitizar el texto
                    value = self.sanitizar_texto(''.join(value_element.stripped_strings))
                    link = value_element.find('a')
                    if link:
                        data[title] = {
                            'texto': value,
                            'link': link['href']
                        }
                        self.logger.debug(f"Añadido campo con link: {title}")
                    else:
                        data[title] = value
                        self.logger.debug(f"Añadido campo: {title}")

        self.logger.info(f"Parseo completado, extraídos {len(data)} campos")
        return data

    def sanitizar_texto(self, texto):
        """
        Sanitiza un texto eliminando caracteres innecesarios como saltos de línea,
        tabulaciones y espacios extra. También separa números y palabras si están juntos.
        """
        self.logger.debug(f"Sanitizando texto de longitud: {len(texto)}")
        # 1. Eliminar caracteres de espacio, saltos de línea y tabulaciones innecesarias
        texto_limpio = re.sub(r'\s+', ' ', texto).strip()

        # 2. Separar palabras y números si están juntos
        texto_limpio = re.sub(r'(\d+)', r' \1 ', texto_limpio).strip()

        self.logger.debug(f"Texto sanitizado, nueva longitud: {len(texto_limpio)}")
        return texto_limpio
    
    def process_find(self, url):
        try:
            self.logger.info(f"Procesando URL find: {url}")
            html = self.curl_request(url, is_contiene=False)
            time.sleep(2)
            if not html:
                self.logger.warning(f"No se obtuvo contenido HTML para find URL: {url}")
                return

            soup = BeautifulSoup(html, 'html.parser')
            desc_links = soup.find_all('a', href=re.compile(r'/description/\d+'))
            desc_urls = [urljoin(self.base_url, link['href']) for link in desc_links]

            if desc_urls:
                self.logger.info(f"Encontrados {len(desc_urls)} enlaces de descripción en find: {desc_urls}")
                print(f"Found description links in find: {desc_urls}")
                for desc_url in desc_urls:
                    self.r.rpush("todo_urls", desc_url)  # Añade a Redis
                    self.redis_logger.debug(f"Añadida URL description a Redis: {desc_url}")
            else:
                self.logger.info(f"No se encontraron enlaces de descripción en find URL: {url}")
        except Exception as e:
            self.log_error(f"Error processing find URL {url}: {e}")

    def process_description(self, url):
        try:
            self.logger.info(f"Procesando URL description: {url}")
            # Obtener cookies para el contexto de "description"
            # Usar curl con cookies
            html_content = self.curl_request(url, is_contiene=False)
            time.sleep(2)
            if not html_content:
                self.logger.warning(f"No se obtuvo contenido HTML para description URL: {url}")
                return

            match = re.search(r'description/(\d+)', url)
            if match:
                page_id = match.group(1)
                self.logger.info(f"Procesando description con ID: {page_id}")
                soup = BeautifulSoup(html_content, 'html.parser')

                # Encola las URLs de "contiene"
                contiene_links = soup.find_all('a', href=re.compile(r'/contiene/\d+'))
                contiene_urls = [urljoin(self.base_url, link['href']) for link in contiene_links]
                if contiene_urls:
                    self.logger.info(f"Encontrados {len(contiene_urls)} enlaces contiene")
                    for contiene_url in contiene_urls:
                        self.r.rpush("todo_urls", contiene_url)
                        self.redis_logger.debug(f"Añadida URL contiene a Redis: {contiene_url}")

                # Procesa el enlace "show" y genera links de descarga
                has_image = False
                img_download_links = []
                show_link = soup.find('a', href=re.compile(r'/show/\d+'))
                if show_link:
                    has_image = True
                    show_url = urljoin(self.base_url, show_link['href'])
                    self.logger.info(f"Procesando show URL: {show_url}")
                    show_content = self.curl_request(show_url, is_contiene=False, referer=url)
                    if show_content:
                        dbcodes = re.findall(
                            r'VisorController.do?.*txt_id_imagen=(\d*)&txt_rotar=0&txt_contraste=0&appOrigen=&dbCode=(\d*)',
                            show_content
                        )
                        img_download_links = [
                            f"https://pares.mcu.es/ParesBusquedas20/ViewImage.do?accion=42"
                            f"&txt_zoom=10&txt_contraste=0&txt_polarizado=&txt_brillo=10.0"
                            f"&txt_contrast=1.0&txt_transformacion=-1&txt_descarga=1"
                            f"&dbCode={dbcode[1]}&txt_id_imagen={dbcode[0]}"
                            for dbcode in dbcodes
                        ]
                        self.logger.info(f"Generados {len(img_download_links)} enlaces de descarga de imágenes")
                        self.image_logger.info(f"Enlaces de descarga generados para page_id {page_id}: {img_download_links}")
                        print(f"Generated image download links: {img_download_links}")

                        if not self.skip_download:
                            self.logger.info(f"Iniciando descarga de imágenes para page_id: {page_id}")
                            self.download_images(page_id, img_download_links)
                        else:
                            self.logger.info("Descarga de imágenes omitida (skip_download=True)")
                else:
                    self.logger.info(f"No se encontró enlace show para page_id: {page_id}")

                description_data = self.parse_html_to_json(html_content)
                self.urls_description[page_id] = {
                    "url": url,
                    "additional_data": description_data,
                    "has_image": has_image,
                    "image_links": img_download_links,
                }
                self.save_descriptions()
                self.logger.info(f"Procesamiento de description completado para page_id: {page_id}")
            else:
                self.logger.error(f"No se pudo extraer page_id de la URL: {url}")
        except Exception as e:
            self.log_error(f"Error processing description URL {url}: {e}")

    def log_error(self, message):
        self.logger.error(message)
        print(message)  # Mantenemos el print original para compatibilidad

    def get_random_user_agent(self):
        # Lista de User-Agents de diferentes navegadores y dispositivos
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:112.0) Gecko/20100101 Firefox/112.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.2 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Android 11; Mobile; rv:112.0) Gecko/112.0 Firefox/112.0",
        ]
        selected_ua = random.choice(user_agents)
        self.logger.debug(f"User-Agent seleccionado: {selected_ua}")
        return selected_ua

    def curl_request(self, url, is_contiene=False, referer=None, max_retries=3):
        for attempt in range(1, max_retries + 1):
            try:
                ip = self.session.get("https://api64.ipify.org", timeout=10).text.strip()
            except Exception:
                ip = "desconocida"
            self.logger.info(f"[Intento {attempt}/{max_retries}] IP pública antes de Playwright: {ip}")

            try:
                start_time = time.time()
                browser_types = ["chromium", "firefox", "webkit"]
                selected_browser = random.choice(browser_types)
                user_agent = self.get_random_user_agent()
                self.logger.info(f"Simulando navegador '{selected_browser}' con User-Agent: {user_agent}")

                with sync_playwright() as p:
                    browser_launcher = getattr(p, selected_browser)
                    browser = browser_launcher.launch(
                        headless=True,
                        proxy={"server": "socks5://127.0.0.1:9050"}
                    )
                    context = browser.new_context(user_agent=user_agent)
                    page = context.new_page()

                    try:
                        ip_check = page.request.get("https://api64.ipify.org", timeout=15000)
                        if ip_check.ok:
                            ip = ip_check.text()
                            self.image_logger.info(f"IP pública actual (esperada Tor): {ip}")
                        else:
                            self.image_logger.warning(f"No se pudo verificar IP (status {ip_check.status})")
                    except Exception as e:
                        self.image_logger.warning(f"No se pudo verificar IP por Playwright: {e}")

                    headers = {
                        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                        "User-Agent": user_agent,
                        "sec-ch-ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": '"Windows"',
                    }

                    if is_contiene:
                        try:
                            page.goto(url, timeout=60000, wait_until="domcontentloaded")
                            page.wait_for_load_state("networkidle", timeout=10000)
                            self.logger.debug("Navegación inicial a página contiene completada")
                        except Exception as e:
                            self.logger.warning(f"Error en navegación inicial: {e}")

                        headers.update({
                            "Accept": "text/html, */*; q=0.01",
                            "Connection": "keep-alive",
                            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                            "Origin": "https://pares.mcu.es",
                            "Referer": url,
                            "Sec-Fetch-Dest": "empty",
                            "Sec-Fetch-Mode": "cors",
                            "Sec-Fetch-Site": "same-origin",
                            "X-Requested-With": "XMLHttpRequest"
                        })

                        post_data = {
                            "tambloque": "10000",
                            "orderBy": "0",
                        }

                        response = page.request.post(
                            "https://pares.mcu.es/ParesBusquedas20/catalogo/contiene/SearchController.do",
                            headers=headers,
                            data=post_data
                        )

                        self.logger.info(f"POST Response Status: {response.status}")
                    else:
                        headers.update({
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "Cache-Control": "max-age=0",
                            "Connection": "keep-alive",
                            "Sec-Fetch-Dest": "document",
                            "Sec-Fetch-Mode": "navigate",
                            "Sec-Fetch-Site": "none",
                            "Sec-Fetch-User": "?1",
                            "Upgrade-Insecure-Requests": "1"
                        })
                        response = page.goto(url, timeout=60000, wait_until="domcontentloaded")

                    if response and hasattr(response, "ok") and response.ok:
                        html = response.text()
                        self.logger.info(f"Playwright request completado en {time.time() - start_time:.2f}s - URL: {url}")
                        self.logger.debug(f"Status Code: {response.status}, Content Length: {len(html)}")
                        if is_contiene:
                            self.logger.debug(f"Contiene response preview: {html[:200]}")
                        browser.close()
                        return html
                    else:
                        raise Exception(f"Playwright falló con status: {getattr(response, 'status', 'sin respuesta')}")

            except Exception as e:
                self.logger.warning(f"Error Playwright fetching {url}: {e}")
                self.logger.info(f"Reintentando ({attempt}/{max_retries}) en 5s...")
                time.sleep(5)

        self.logger.error(f"Fallo tras {max_retries} intentos con URL: {url}")
        return ""


    def download_images(self, page_id, img_links, max_retries=3):
        self.image_logger.info(f"Iniciando descarga de {len(img_links)} imágenes para page_id: {page_id}")
        img_dir = os.path.join(self.img_folder, page_id)
        os.makedirs(img_dir, exist_ok=True)
    
        last_downloaded_index = self.r.get(f"last_downloaded_image:{page_id}")
        last_downloaded_index = int(last_downloaded_index.decode()) if last_downloaded_index else 0
        self.image_logger.info(f"Último índice descargado para {page_id}: {last_downloaded_index}")
    
        for idx, img_url in enumerate(img_links[last_downloaded_index:], start=last_downloaded_index + 1):
            img_path = os.path.join(img_dir, f"image_{idx}.jpg")
    
            if self.r.sismember(f"images:{page_id}", idx):
                self.image_logger.debug(f"Imagen {idx} ya descargada para {page_id}. Saltando...")
                continue
            
            for attempt in range(1, max_retries + 1):
                self.image_logger.info(f"Descargando imagen {idx} (Intento {attempt}/{max_retries})")
                try:
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        context = browser.new_context(
                            user_agent=self.get_random_user_agent(),
                            proxy={"server": "socks5://127.0.0.1:9050"}
                        )
                        page = context.new_page()
    
                        # Verificar IP por Tor
                        try:
                            ip_check = page.request.get("https://api64.ipify.org", timeout=15000)
                            if ip_check.ok:
                                ip = ip_check.text()
                                self.image_logger.info(f"[{idx}] IP pública actual (esperada Tor): {ip}")
                            else:
                                self.image_logger.warning(f"[{idx}] No se pudo verificar IP (status {ip_check.status})")
                        except Exception as e:
                            self.image_logger.warning(f"[{idx}] No se pudo verificar IP por Playwright: {e}")
    
                        # Intentar descargar imagen
                        start_time = time.time()
                        response = context.request.get(img_url, timeout=30000)
                        if response.ok:
                            with open(img_path, "wb") as f:
                                f.write(response.body())
                            elapsed = time.time() - start_time
                            size = os.path.getsize(img_path)
                            self.image_logger.info(f"Imagen {idx} descargada exitosamente: {img_path} ({size} bytes en {elapsed:.2f}s)")
                            self.r.sadd(f"images:{page_id}", idx)
                            self.r.set(f"last_downloaded_image:{page_id}", str(idx))
                            break
                        else:
                            raise Exception(f"HTTP {response.status}")
                except Exception as e:
                    self.image_logger.warning(f"Fallo al descargar imagen {idx}: {e}")
                    time.sleep(5)
                else:
                    break  # si no hubo error
            else:
                self.image_logger.error(f"No se pudo descargar imagen {idx} después de {max_retries} intentos")
                self.r.sadd(f"failed_images:{page_id}", idx)
    
        # Verificación final
        downloaded_count = len(self.r.smembers(f"images:{page_id}"))
        if downloaded_count == len(img_links):
            self.r.delete(f"last_downloaded_image:{page_id}")
            self.image_logger.info(f"Descarga completada para {page_id}. Limpiado último índice.")


    def retry_failed_image_downloads(self, page_id):
        self.image_logger.info(f"Reintentando descargas fallidas para page_id: {page_id}")
        failed_urls = self.r.smembers(f"failed_images:{page_id}")
        
        if failed_urls:
            failed_count = len(failed_urls)
            self.image_logger.info(f"Reintentando descargar {failed_count} imágenes fallidas para {page_id}")
            print(f"Reintentando descargar {failed_count} imágenes fallidas...")
            # Convertir a lista para pasar a download_images
            self.download_images(page_id, list(failed_urls))
            # Limpiar la lista de imágenes fallidas después del reintento
            self.r.delete(f"failed_images:{page_id}")
            self.image_logger.info(f"Limpiada lista de imágenes fallidas para {page_id}")
        else:
            self.image_logger.info(f"No hay imágenes fallidas para reintentar en {page_id}")

    def verify_images_downloaded(self, page_id, total_images):
        self.image_logger.info(f"Verificando imágenes descargadas para {page_id}. Total esperado: {total_images}")
        downloaded_count = self.r.scard(f"images:{page_id}")
        
        if downloaded_count == total_images:
            self.image_logger.info(f"Verificación exitosa: Todas las imágenes ({total_images}) de {page_id} descargadas")
            print(f"Todas las imágenes ({total_images}) de la página {page_id} han sido descargadas.")
            return True
        else:
            missing_count = total_images - downloaded_count
            self.image_logger.warning(f"Verificación falló: Faltan {missing_count} imágenes para {page_id}")
            print(f"Faltan {missing_count} imágenes para la página {page_id}.")
            
            # Opcional: Listado de imágenes faltantes
            all_indices = set(range(1, total_images + 1))
            downloaded_indices = {int(idx) for idx in self.r.smembers(f"images:{page_id}")}
            missing_indices = all_indices - downloaded_indices
            
            self.image_logger.debug(f"Índices de imágenes faltantes para {page_id}: {missing_indices}")
            print(f"Índices de imágenes faltantes: {missing_indices}")
            
            return False

    def process_contiene(self, url):
        try:
            self.logger.info(f"Procesando URL contiene: {url}")

            # DEBUGGING: Guardar HTML para inspección
            html = self.curl_request(url, is_contiene=True)

            time.sleep(2)
            if not html:
                self.logger.warning(f"No se obtuvo contenido HTML para contiene URL: {url}")
                return

            # DEBUGGING: Mostrar primeros caracteres del HTML
            self.logger.info(f"HTML recibido (primeros 500 chars): {html[:500]}")

            soup = BeautifulSoup(html, 'html.parser')

            # AMPLIADO: Buscar diferentes patrones de enlaces
            patterns_to_search = [
                r'/description/\d+',
                r'description/\d+',
                r'/catalogo/description/\d+',
                r'catalogo/description/\d+'
            ]

            all_desc_links = []
            for pattern in patterns_to_search:
                desc_links = soup.find_all('a', href=re.compile(pattern))
                self.logger.debug(f"Patrón '{pattern}' encontró {len(desc_links)} enlaces")
                all_desc_links.extend(desc_links)

            # Remover duplicados manteniendo orden
            seen = set()
            unique_desc_links = []
            for link in all_desc_links:
                href = link['href']
                if href not in seen:
                    seen.add(href)
                    unique_desc_links.append(link)

            desc_urls = [urljoin(self.base_url, link['href']) for link in unique_desc_links]

            # DEBUGGING: Mostrar todos los enlaces encontrados
            all_links = soup.find_all('a')
            self.logger.info(f"Total de enlaces <a> encontrados en contiene: {len(all_links)}")

            # Mostrar una muestra de enlaces para debugging
            sample_links = all_links[:10]  # Primeros 10 enlaces
            for i, link in enumerate(sample_links):
                href = link.get('href', 'SIN HREF')
                text = link.get_text(strip=True)[:50]  # Primeros 50 caracteres del texto
                self.logger.debug(f"Enlace {i+1}: href='{href}' text='{text}'")

            # NUEVO: Buscar también en JavaScript/JSON embebido
            script_tags = soup.find_all('script')
            self.logger.info(f"Scripts encontrados: {len(script_tags)}")

            for i, script in enumerate(script_tags):
                script_content = script.get_text()
                if 'description' in script_content.lower():
                    self.logger.debug(f"Script {i+1} contiene 'description': {script_content[:200]}")

                    # Buscar patrones de URLs en JavaScript
                    js_desc_matches = re.findall(r'description[/\\](\d+)', script_content)
                    if js_desc_matches:
                        self.logger.info(f"IDs de description encontrados en JavaScript: {js_desc_matches}")
                        for desc_id in js_desc_matches:
                            desc_url = f"{self.base_url}/ParesBusquedas20/catalogo/description/{desc_id}"
                            if desc_url not in desc_urls:
                                desc_urls.append(desc_url)

            if desc_urls:
                self.logger.info(f"Encontrados {len(desc_urls)} enlaces de descripción en contiene: {desc_urls}")
                print(f"Found description links: {desc_urls}")
                for desc_url in desc_urls:
                    # VERIFICAR que no esté ya procesada
                    if not self.is_done(desc_url):
                        self.r.rpush("todo_urls", desc_url)
                        self.redis_logger.debug(f"Añadida URL description desde contiene a Redis: {desc_url}")
                    else:
                        self.logger.debug(f"URL description ya procesada, no se añade: {desc_url}")
            else:
                self.logger.warning(f"No se encontraron enlaces de descripción en contiene URL: {url}")

        except Exception as e:
            self.log_error(f"Error processing contiene URL {url}: {e}")

    def process_archive(self):
        self.logger.info("Iniciando procesamiento del archivo")
        processed_count = 0
        start_time = time.time()
        
        while True:
            url = self.get_next_url()
            if not url:
                self.logger.info("No hay más URLs para procesar")
                break

            if self.is_done(url):
                self.logger.debug(f"URL ya procesada, saltando: {url}")
                print(f"Skipping processed URL: {url}")
                continue

            self.logger.info(f"Procesando URL #{processed_count + 1}: {url}")
            print(f"Processing: {url}")
            
            url_start_time = time.time()
            
            if "description/" in url:
                self.process_description(url)
            elif "contiene/" in url:
                self.process_contiene(url)
            elif "catalogo/find" in url:
                self.process_find(url)
            else:
                self.logger.warning(f"Tipo de URL no reconocido: {url}")
            
            url_elapsed = time.time() - url_start_time
            self.mark_as_done(url)
            processed_count += 1
            
            self.logger.info(f"URL procesada en {url_elapsed:.2f}s. Total procesadas: {processed_count}")
            
            # Log de progreso cada 10 URLs
            if processed_count % 10 == 0:
                total_elapsed = time.time() - start_time
                avg_time_per_url = total_elapsed / processed_count
                self.logger.info(f"Progreso: {processed_count} URLs procesadas en {total_elapsed:.2f}s (Promedio: {avg_time_per_url:.2f}s/URL)")
        
        total_elapsed = time.time() - start_time
        self.logger.info(f"Procesamiento completado. {processed_count} URLs procesadas en {total_elapsed:.2f}s")

    def __del__(self):
        self.logger.info("Destruyendo instancia de ParesFileScraper")
        # Elimina el archivo de cookies cuando se destruye la instancia
        if os.path.exists(self.cookie_file):
            try:
                os.remove(self.cookie_file)
                self.logger.debug(f"Archivo de cookies eliminado: {self.cookie_file}")
            except Exception as e:
                self.logger.error(f"Error eliminando archivo de cookies: {e}")

def initialize_redis(todo_file):
    # Configurar logger para la función de inicialización
    logger = logging.getLogger('ParesFileScraper.Redis.Init')
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    logger.info(f"Inicializando Redis con archivo: {todo_file}")
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    
    # Verifica si la lista 'todo_urls' ya tiene elementos
    current_count = r.llen("todo_urls")
    if current_count > 0:
        logger.info(f"Redis 'todo_urls' ya contiene {current_count} elementos. Ignorando el archivo.")
        print("Redis 'todo_urls' ya contiene datos. Ignorando el archivo.")
        return

    # Añade URLs del archivo si 'todo_urls' está vacío
    added_count = 0
    skipped_count = 0
    
    try:
        with open(todo_file, "r") as f:
            for line_num, line in enumerate(f, 1):
                url = line.strip()
                if url:  # Solo procesar líneas no vacías
                    if not r.sismember("done_urls", url):  # Verifica que no esté procesada
                        r.rpush("todo_urls", url)
                        added_count += 1
                        logger.debug(f"Añadida URL línea {line_num}: {url}")
                    else:
                        skipped_count += 1
                        logger.debug(f"URL ya procesada, saltando línea {line_num}: {url}")
                        
        logger.info(f"Carga completada: {added_count} URLs añadidas, {skipped_count} saltadas")
        print("URLs cargadas en Redis desde 'todo_urls.txt'.")
        
    except FileNotFoundError:
        logger.error(f"Archivo no encontrado: {todo_file}")
        print(f"Error: No se encontró el archivo {todo_file}")
    except Exception as e:
        logger.error(f"Error cargando URLs desde archivo: {e}")
        print(f"Error cargando URLs: {e}")

def run_scraper(skip_download=False):
    # Configurar logger para la función principal
    logger = logging.getLogger('ParesFileScraper.Main')
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    logger.info(f"Iniciando scraper con skip_download={skip_download}")
    start_time = time.time()
    
    try:
        scraper = ParesFileScraper(skip_download=skip_download)
        logger.info("Scraper inicializado exitosamente")
        scraper.process_archive()
        
        elapsed_time = time.time() - start_time
        logger.info(f"Scraper completado exitosamente en {elapsed_time:.2f} segundos")
        
    except KeyboardInterrupt:
        logger.info("Scraper interrumpido por el usuario (Ctrl+C)")
        print("\nScraper interrumpido por el usuario")
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"Error ejecutando scraper después de {elapsed_time:.2f}s: {e}")
        print(f"Error ejecutando scraper: {e}")
        raise
