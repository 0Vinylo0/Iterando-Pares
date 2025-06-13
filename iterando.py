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
from multiprocessing import Process

class ParesFileScraper:
    def __init__(self, base_url="https://pares.mcu.es"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.proxies = {
            "http": "socks5h://127.0.0.1:9050",
            "https": "socks5h://127.0.0.1:9050"
        }
        self.r = redis.StrictRedis(host='localhost', port=6379, db=0)  # Conexión a Redis
        self.description_file = "description_data.json"
        self.img_folder = "img"
        self.urls_description = self.load_existing_descriptions()
        self.cookie_file = f"cookies_{os.getpid()}.txt"  # Archivo único por proceso

    def load_existing_descriptions(self):
        if os.path.exists(self.description_file):
            with open(self.description_file, "r", encoding='utf-8') as desc_file:
                return json.load(desc_file)
        return {}

    def save_descriptions(self):
        with open(self.description_file, "w", encoding='utf-8') as desc_file:
            json.dump(self.urls_description, desc_file, indent=4, ensure_ascii=False)

    def get_current_ip(self):
        """Obtiene la IP pública visible a través de Tor."""
        try:
            # Cambia la URL por una de las opciones rápidas
            response = self.session.get("https://api64.ipify.org")
            print(f"IP Pública: {response.text.strip()}")
        except Exception as e:
            print(f"Error obteniendo la IP pública: {e}")

    def get_next_url(self):
        # Obtiene una URL de la lista Redis
        url = self.r.blpop("todo_urls", timeout=5)  # Espera hasta 5 segundos
        if url:
            return url[1].decode()  # Decodifica la URL de bytes a string
        return None

    def mark_as_done(self, url):
        # Marca una URL como completada en Redis
        self.r.sadd("done_urls", url)

    def is_done(self, url):
        # Verifica si la URL ya fue procesada
        return self.r.sismember("done_urls", url)

    def get_page(self, url):
        try:
            self.get_current_ip()
            response = self.session.get(url)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            self.log_error(f"Error fetching {url}: {e}")
            return None

    def parse_html_to_json(self, html_content):
        """
        Parsea el contenido HTML y lo convierte a un diccionario JSON con datos sanitizados.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        data = {}

        # Buscar el contenedor principal
        wrapper = soup.find(id="wrapper_ficha")
        if not wrapper:
            return data

        # Buscar la sección del área
        area = wrapper.find(class_="area")
        if not area:
            return data

        # Buscar todas las secciones de información
        infos = area.find_all(class_="info")
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
                    else:
                        data[title] = value

        return data

    def sanitizar_texto(self, texto):
        """
        Sanitiza un texto eliminando caracteres innecesarios como saltos de línea,
        tabulaciones y espacios extra. También separa números y palabras si están juntos.
        """
        # 1. Eliminar caracteres de espacio, saltos de línea y tabulaciones innecesarias
        texto_limpio = re.sub(r'\s+', ' ', texto).strip()

        # 2. Separar palabras y números si están juntos
        texto_limpio = re.sub(r'(\d+)', r' \1 ', texto_limpio).strip()

        return texto_limpio
    
    def process_find(self, url):
        try:
            html = self.curl_request(url, is_contiene=False)
            time.sleep(2)
            if not html:
                return

            soup = BeautifulSoup(html, 'html.parser')
            desc_links = soup.find_all('a', href=re.compile(r'/description/\d+'))
            desc_urls = [urljoin(self.base_url, link['href']) for link in desc_links]

            if desc_urls:
                print(f"Found description links in find: {desc_urls}")
                for desc_url in desc_urls:
                    self.r.rpush("todo_urls", desc_url)  # Añade a Redis
        except Exception as e:
            self.log_error(f"Error processing find URL {url}: {e}")

    def process_description(self, url):
        html_content = self.curl_request(url, is_contiene=False)
        if not html_content:
            return

        match = re.search(r'description/(\d+)', url)
        if match:
            page_id = match.group(1)
            soup = BeautifulSoup(html_content, 'html.parser')
            
            #En caso de que solo queramos el titulo descomentar 

            #title_match = soup.find('h4', string=re.compile(r'Titulo Nombre Atribuido:'))
            #title = title_match.find_next('p').text.strip() if title_match else "none"

            contiene_links = soup.find_all('a', href=re.compile(r'/contiene/\d+'))
            contiene_urls = [urljoin(self.base_url, link['href']) for link in contiene_links]
            if contiene_urls:
                print(f"Found contiene links: {contiene_urls}")
                for contiene_url in contiene_urls:
                    self.r.rpush("todo_urls", contiene_url)  # Añade a Redis

            has_image = False
            img_download_links = []  # Arreglo para almacenar los enlaces de descarga de imágenes
            show_link = soup.find('a', href=re.compile(r'/show/\d+'))
            if show_link:
                has_image = True
                show_url = urljoin(self.base_url, show_link['href'])
                # Obtener cookies desde la página 'show'
                self.get_cookies_from_show(show_url)
                show_content = self.curl_request(show_url, is_contiene=False, referer=url)
                if show_content:
                    dbcodes = re.findall(r'VisorController.do?.*txt_id_imagen=(\d*)&txt_rotar=0&txt_contraste=0&appOrigen=&dbCode=(\d*)', show_content)
                    img_download_links = [
                        f"https://pares.mcu.es/ParesBusquedas20/ViewImage.do?accion=42&txt_zoom=10&txt_contraste=0&txt_polarizado=&txt_brillo=10.0&txt_contrast=1.0&txt_transformacion=-1&txt_descarga=1&dbCode={dbcode[1]}&txt_id_imagen={dbcode[0]}"
                        for dbcode in dbcodes
                    ]
                    print(f"Generated image download links: {img_download_links}")

                    # Descargar cada imagen y guardarla en la carpeta correspondiente
                    self.download_images(page_id, img_download_links)

            description_data = self.parse_html_to_json(html_content)

            # Almacenar todos los datos en self.urls_description
            self.urls_description[page_id] = {
                "url": url,
                "additional_data": description_data,
                "has_image": has_image,
                "image_links": img_download_links,  # Añadir los enlaces de descarga de imágenes
                # Añadir todos los datos parseados
            }

            self.save_descriptions()

    def log_error(self, message):
        print(message)  # Simplificado para esta implementación

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
        return random.choice(user_agents)

    def curl_request(self, url, is_contiene=False):
        try:
            if is_contiene:
                # Realizar una solicitud curl para obtener las cookies primero
                get_cookie_command = [
                    "curl",
                    "-sL",
                    "-x", "socks5h://127.0.0.1:9050",  # Proxy de Tor
                    "-c", self.cookie_file,
                    "-H", f"User-Agent: {self.get_random_user_agent()}",
                    url
                ]
                subprocess.run(get_cookie_command, capture_output=True, text=True)

                # Luego hacer el curl con la cookie obtenida
                command = [
                    "curl",
                    "-sL",
                    "-x", "socks5h://127.0.0.1:9050",  # Proxy de Tor
                    "https://pares.mcu.es/ParesBusquedas20/catalogo/contiene/SearchController.do",
                    "-H", "Accept: text/html, */*; q=0.01",
                    "-H", "Accept-Language: es-ES,es;q=0.9,en;q=0.8",
                    "-H", "Connection: keep-alive",
                    "-H", "Content-Type: application/x-www-form-urlencoded; charset=UTF-8",
                    "-H", f"Cookie: {self.get_cookies()}",
                    "-H", "Origin: https://pares.mcu.es",
                    "-H", f"Referer: {url}",
                    "-H", "Sec-Fetch-Dest: empty",
                    "-H", "Sec-Fetch-Mode: cors",
                    "-H", "Sec-Fetch-Site: same-origin",
                    "-H", f"User-Agent: {self.get_random_user_agent()}",
                    "-H", "X-Requested-With: XMLHttpRequest",
                    "-H", "sec-ch-ua: \"Chromium\";v=\"130\", \"Google Chrome\";v=\"130\", \"Not?A_Brand\";v=\"99\"",
                    "-H", "sec-ch-ua-mobile: ?0",
                    "-H", "sec-ch-ua-platform: \"Windows\"",
                    "--data-raw", "tambloque=10000&orderBy=0"
                ]
            else:
                get_cookie_command = [
                    "curl",
                    "-s",
                    "-x", "socks5h://127.0.0.1:9050",
                    "-c", self.cookie_file,
                    "-H", f"User-Agent: {self.get_random_user_agent()}",
                    url
                ]
                subprocess.run(get_cookie_command, capture_output=True, text=True)

                # 2. Hacer curl con cabecera exacta
                command = [
                    "curl",
                    "-sL",
                    "-x", "socks5h://127.0.0.1:9050",
                    "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "-H", "Accept-Language: es-ES,es;q=0.9,en;q=0.8",
                    "-H", "Cache-Control: max-age=0",
                    "-H", "Connection: keep-alive",
                    "-H", f"Cookie: {self.get_cookies()}",
                    "-H", "Sec-Fetch-Dest: document",
                    "-H", "Sec-Fetch-Mode: navigate",
                    "-H", "Sec-Fetch-Site: none",
                    "-H", "Sec-Fetch-User: ?1",
                    "-H", "Upgrade-Insecure-Requests: 1",
                    "-H", f"User-Agent: {self.get_random_user_agent()}",
                    "-H", 'sec-ch-ua: "Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
                    "-H", "sec-ch-ua-mobile: ?1",
                    "-H", 'sec-ch-ua-platform: "Android"',
                    url
                ]
            result = subprocess.run(command, capture_output=True, text=True)
            # Guardar en el archivo de log
            self.log_error(f"URL: {url}\nReturn Code: {result.returncode}\nOutput Length: {len(result.stdout)}\nOutput Preview: {result.stdout[:500]}\n")
            return result.stdout
        except Exception as e:
            self.log_error(f"Error fetching {url}: {e}")
            return ""

    def get_cookies(self):
        cookies = []
        if os.path.exists(self.cookie_file):
            with open(self.cookie_file, "r") as f:
                for line in f:
                    if not line.startswith("#") and line.strip():
                        parts = line.strip().split("\t")
                        if len(parts) >= 7:
                            cookies.append(f"{parts[5]}={parts[6]}")
        return "; ".join(cookies)

    def download_images(self, page_id, img_links):
        img_dir = os.path.join(self.img_folder, page_id)
        if not os.path.exists(img_dir):
            os.makedirs(img_dir)

        # Verificar el último índice descargado en Redis
        last_downloaded_index = self.r.get(f"last_downloaded_image:{page_id}")
        last_downloaded_index = int(last_downloaded_index.decode()) if last_downloaded_index else 0

        # Comenzar desde el último índice descargado
        for idx, img_url in enumerate(img_links[last_downloaded_index:], start=last_downloaded_index + 1):
            img_path = os.path.join(img_dir, f"image_{idx}.jpg")

            # Verificar si la imagen ya fue descargada
            if self.r.sismember(f"images:{page_id}", idx):
                print(f"Imagen {idx} ya descargada. Saltando...")
                continue

            # Descargar la imagen con reintentos
            for attempt in range(3):  # Reintentar hasta 3 veces
                print(f"Descargando imagen {idx}... (Intento {attempt + 1}/3)")
                command = [
                    "curl",
                    "-s",
                    "-x", "socks5h://127.0.0.1:9050",  # Proxy Tor
                    "-b", self.cookie_file,  # Cookies
                    "-o", img_path,  # Ruta de salida
                    "-H", f"User-Agent: {self.get_random_user_agent()}",
                    "--max-time", "30",  # Tiempo máximo de espera (30 segundos)
                    img_url
                ]
                result = subprocess.run(command)

                if result.returncode == 0:  # Éxito
                    print(f"Imagen {idx} descargada: {img_path}")
                    self.r.sadd(f"images:{page_id}", idx)  # Registrar imagen descargada en Redis
                    
                    # Actualizar el último índice descargado
                    self.r.set(f"last_downloaded_image:{page_id}", str(idx))
                    break
                else:
                    print(f"Fallo al descargar imagen {idx}. Reintentando...")
                    time.sleep(5)  # Esperar antes de reintentar

            else:  # Si después de 3 intentos falla
                print(f"No se pudo descargar la imagen {idx} después de varios intentos.")
                self.r.sadd(f"failed_images:{page_id}", idx)  # Registrar imagen fallida

        # Limpiar el último índice descargado si se completó todo
        if len(self.r.smembers(f"images:{page_id}")) == len(img_links):
            self.r.delete(f"last_downloaded_image:{page_id}")

    def get_cookies_from_show(self, show_url):
        # Genera el archivo de cookies para la sesión actual
        command = [
            "curl",
            "-s",
            "-x", "socks5h://127.0.0.1:9050",  # Proxy de Tor
            "-c", self.cookie_file,
            "-H", f"User-Agent: {self.get_random_user_agent()}",
            show_url
        ]
        subprocess.run(command)

    def retry_failed_image_downloads(self, page_id):
        failed_urls = self.r.smembers(f"failed_images:{page_id}")
        
        if failed_urls:
            print(f"Reintentando descargar {len(failed_urls)} imágenes fallidas...")
            # Convertir a lista para pasar a download_images
            self.download_images(page_id, list(failed_urls))
            # Limpiar la lista de imágenes fallidas después del reintento
            self.r.delete(f"failed_images:{page_id}")

    def verify_images_downloaded(self, page_id, total_images):
        downloaded_count = self.r.scard(f"images:{page_id}")
        
        if downloaded_count == total_images:
            print(f"Todas las imágenes ({total_images}) de la página {page_id} han sido descargadas.")
            return True
        else:
            missing_count = total_images - downloaded_count
            print(f"Faltan {missing_count} imágenes para la página {page_id}.")
            
            # Opcional: Listado de imágenes faltantes
            all_indices = set(range(1, total_images + 1))
            downloaded_indices = {int(idx) for idx in self.r.smembers(f"images:{page_id}")}
            missing_indices = all_indices - downloaded_indices
            
            print(f"Índices de imágenes faltantes: {missing_indices}")
            
            return False

    def process_contiene(self, url):
        try:
            # Realiza una solicitud curl para "contiene"
            html = self.curl_request(url, is_contiene=True)
            time.sleep(2)
            if not html:
                return

            soup = BeautifulSoup(html, 'html.parser')
            desc_links = soup.find_all('a', href=re.compile(r'/description/\d+'))
            desc_urls = [urljoin(self.base_url, link['href']) for link in desc_links]

            if desc_urls:
                print(f"Found description links: {desc_urls}")
                for desc_url in desc_urls:
                    self.r.rpush("todo_urls", desc_url)  # Añade a Redis

        except Exception as e:
            self.log_error(f"Error processing contiene URL {url}: {e}")

    def process_archive(self):
        while True:
            url = self.get_next_url()
            if not url:
                break

            if self.is_done(url):
                print(f"Skipping processed URL: {url}")
                continue

            print(f"Processing: {url}")
            if "description/" in url:
                self.process_description(url)
            elif "contiene/" in url:
                self.process_contiene(url)
            elif "catalogo/find" in url:
                self.process_find(url)
            self.mark_as_done(url)

    def __del__(self):
        # Elimina el archivo de cookies cuando se destruye la instancia
        if os.path.exists(self.cookie_file):
            os.remove(self.cookie_file)

def initialize_redis(todo_file):
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    
    # Verifica si la lista 'todo_urls' ya tiene elementos
    if r.llen("todo_urls") > 0:
        print("Redis 'todo_urls' ya contiene datos. Ignorando el archivo.")
        return

    # Añade URLs del archivo si 'todo_urls' está vacío
    with open(todo_file, "r") as f:
        for line in f:
            url = line.strip()
            if not r.sismember("done_urls", url):  # Verifica que no esté procesada
                r.rpush("todo_urls", url)
    print("URLs cargadas en Redis desde 'todo_urls.txt'.")

def run_scraper():
    scraper = ParesFileScraper()
    scraper.process_archive()
