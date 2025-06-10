# Proyecto Iterando-Pares
## Scraper Web Avanzado para Portal de Archivos Españoles

---

**Autor:** Andrés Del Pino Muñoz 
**Fecha de Entrega:** 12-06-25

---

## Índice

1. [Descripción del proyecto](#1-descripción-del-proyecto)
2. [Introducción teórica](#2-introducción-teórica)
3. [Configuración de la red](#3-configuración-de-la-red)
4. [Herramientas utilizadas](#4-herramientas-utilizadas)
5. [Desarrollo del proyecto con detalle](#5-desarrollo-del-proyecto-con-detalle)
6. [Conclusiones y dificultades encontradas](#6-conclusiones-y-dificultades-encontradas)
7. [Referencias utilizadas](#7-referencias-utilizadas)

---

## 1. Descripción del proyecto

El proyecto "Iterando-Pares" es un sistema de scraping web avanzado desarrollado en Python para extraer datos e imágenes de forma masiva del Portal de Archivos Españoles (PARES). El sistema está diseñado para procesar unidades documentales históricas de manera eficiente y anónima, utilizando tecnologías como TOR para el enmascaramiento de IP, Redis como base de datos temporal y un sistema sofisticado de manejo de cookies.

<a href="https://www.python.org" target="_blank" rel="noreferrer"> <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/python/python-original.svg" alt="python" width="40" height="40"/>
<a href="https://www.linux.org/" target="_blank" rel="noreferrer"> <img src="https://raw.githubusercontent.com/devicons/devicon/master/icons/linux/linux-original.svg" alt="linux" width="40" height="40"/>
<a href="https://www.torproject.org/es/" target="_blank" rel="noreferrer"> <img src="https://raw.githubusercontent.com/TheTorProject/tor-media/25a7a48199a00da805fdc8de2a2f662b170bcead/Tor%20Logo/Purple.svg" alt="tor" width="40" height="40"/> <a href="https://redis.io/es/" target="_blank" rel="noreferrer"> <img src="https://raw.githubusercontent.com/devicons/devicon/ca28c779441053191ff11710fe24a9e6c23690d6/icons/redis/redis-original-wordmark.svg" alt="tor" width="40" height="40"/>

El scraper es capaz de procesar dos tipos de URLs principales:
- URLs de descripción: `https://pares.mcu.es/ParesBusquedas20/catalogo/description/[ID]`
- URLs de contenido: `https://pares.mcu.es/ParesBusquedas20/catalogo/contiene/[ID]`

### Características principales:
- Procesamiento recursivo de enlaces
- Descarga automática de imágenes históricas
- Sistema de recuperación ante errores
- Procesamiento en paralelo con múltiples procesos
- Interfaz web local para visualización de resultados
- Compatibilidad con Docker para facilitar el despliegue

## 2. Introducción teórica

### Web Scraping
El web scraping es una técnica de extracción de datos que permite obtener información de sitios web de forma automatizada. En el contexto de archivos históricos, esta técnica resulta fundamental para la digitalización masiva y preservación del patrimonio documental.

### Anonimización de tráfico con TOR
The Onion Router (TOR) es una red de comunicación anónima que permite ocultar la identidad del usuario mediante el enrutamiento del tráfico a través de múltiples servidores proxy. En proyectos de scraping masivo, TOR previene el bloqueo por parte de los servidores de destino y garantiza la privacidad del proceso de extracción.

### Bases de datos temporales con Redis
Redis es un sistema de almacenamiento de datos en memoria que actúa como base de datos, caché y broker de mensajes. Su velocidad y eficiencia lo convierten en la herramienta ideal para manejar estados temporales en procesos de scraping, permitiendo el seguimiento de URLs procesadas y pendientes.

### Gestión de cookies y sesiones web
Las cookies son pequeños archivos de datos que los sitios web almacenan en el navegador del usuario para mantener el estado de la sesión. En scraping web, la gestión adecuada de cookies es crucial para simular el comportamiento de un navegador real y acceder a contenido que requiere autenticación o mantenimiento de sesión.

## 3. Configuración de la red

### Mapa de red del sistema

```
[Cliente/Scraper] → [TOR Proxy] → [Internet] → [PARES Server]
       ↓
[Redis Database] ← [Procesamiento] → [Sistema de archivos local]
       ↓
[Interfaz Web Local] ← [Visualización de resultados]
```

### Componentes de red:

**TOR Proxy Configuration:**
- Puerto SOCKS5: 127.0.0.1:9050
- Puerto de control: 9051
- Configuración de autenticación con contraseña hash

**Redis Database:**
- Host: localhost
- Puerto: 6379
- Sin autenticación (entorno local)

**Servidor web local:**
- Puerto: Variable (definido por el navegador)
- Protocolo: file:// para index.html local

### Flujo de datos:
1. El scraper obtiene URLs desde Redis
2. Las peticiones se enrutan a través de TOR
3. Se extraen datos y se almacenan temporalmente en Redis
4. Las imágenes se descargan al sistema de archivos local
5. Los metadatos se exportan a JSON para visualización web

## 4. Herramientas utilizadas

### Lenguajes de programación:
- **Python 3.8+**: Lenguaje principal del proyecto
- **HTML/CSS/JavaScript**: Para la interfaz de visualización local

### Librerías de Python:
- **requests**: Realización de peticiones HTTP
- **beautifulsoup4**: Parsing y extracción de datos HTML
- **redis**: Interface con la base de datos Redis
- **multiprocessing**: Procesamiento en paralelo
- **urllib**: Manipulación de URLs

### Herramientas de sistema:
- **TOR**: Red de anonimización
- **Redis**: Base de datos en memoria
- **Docker**: Containerización (versión alternativa)

### Herramientas de desarrollo:
- **Git**: Control de versiones
- **GitHub**: Repositorio de código
- **Firefox**: Navegador para visualización (configuración específica requerida)

## 5. Desarrollo del proyecto con detalle

### Arquitectura del sistema

El proyecto está estructurado en varios componentes principales:

#### 5.1 Clase ParesFileScraper (main.py)
Esta es la clase central que maneja todo el proceso de scraping:

```python
class ParesFileScraper:
    def __init__(self):
        # Configuración de TOR proxy
        self.proxies = {'http': 'socks5h://127.0.0.1:9050', 
                       'https': 'socks5h://127.0.0.1:9050'}
        # Conexión a Redis
        self.redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
```

**Funcionalidades principales:**
- **Procesamiento de URLs**: Distingue entre URLs de tipo 'description' y 'contiene'
- **Extracción de metadatos**: Obtiene títulos, fechas, descripciones y enlaces
- **Descarga de imágenes**: Sistema robusto con manejo de cookies
- **Gestión de errores**: Reintento automático y logging de fallos

#### 5.2 Sistema de gestión de URLs (controller.py)
Controlador principal que coordina todo el proceso:

```python
def initialize_redis_with_urls(file_path):
    # Carga URLs iniciales desde archivo
    # Limpia Redis de ejecuciones anteriores
    # Configura las colas de procesamiento
```

**Características:**
- Inicialización desde archivo todo_urls.txt
- Procesamiento en paralelo con múltiples workers
- Monitoreo de progreso en tiempo real

#### 5.3 Sistema de limpieza (delete.py)
Script para reiniciar el estado del sistema:

```python
def clean_redis():
    # Elimina todas las claves de URLs
    # Limpia cachés de imágenes
    # Resetea contadores
```

### 5.4 Proceso de iteración y extracción

El sistema implementa un algoritmo de iteración sofisticado:

1. **Inicialización**: Se cargan las URLs semilla desde todo_urls.txt
2. **Procesamiento iterativo**: Para cada URL:
   - Se extrae el contenido HTML
   - Se identifican nuevos enlaces relacionados
   - Se añaden a la cola de Redis si no están procesados
   - Se extraen metadatos y enlaces a imágenes
3. **Descarga de imágenes**: Sistema asíncrono con manejo de cookies
4. **Persistencia**: Los datos se almacenan en JSON estructurado

### 5.5 Interfaz de visualización

El sistema incluye una interfaz web local (index.html) que permite:
- Navegación interactiva por los datos extraídos
- Visualización de imágenes descargadas
- Búsqueda y filtrado de documentos
- Exportación de resultados

## 6. Conclusiones y dificultades encontradas

### Logros alcanzados:
- **Scraping masivo eficiente**: El sistema puede procesar miles de documentos automáticamente
- **Anonimización exitosa**: TOR permite evitar bloqueos y mantener la privacidad
- **Robustez del sistema**: Manejo de errores y recuperación automática
- **Escalabilidad**: Procesamiento en paralelo y arquitectura modular
- **Usabilidad**: Interfaz intuitiva para visualización de resultados

### Dificultades técnicas encontradas:

#### 6.1 Iteración del programa
**Problema**: El sistema debe manejar una estructura de datos compleja donde cada documento puede contener enlaces a otros documentos, creando un grafo de dependencias.

**Algoritmo utilizado**: **Búsqueda en Anchura (BFS)**  
La búsqueda en anchura (BFS) explora primero los documentos más cercanos al punto de inicio, nivel por nivel. Utiliza una cola (en este caso, Redis) para procesar primero los enlaces recién descubiertos antes de pasar a los siguientes. Esto garantiza una exploración ordenada y evita visitar dos veces el mismo documento.

**Ventajas de BFS en este contexto**:
- Evita ciclos y duplicados mediante `done_urls`
- Prioriza enlaces más cercanos al punto de entrada
- Asegura una cobertura amplia y sistemática del portal

  ![](https://miro.medium.com/v2/resize:fit:640/format:webp/1*xNoSauTOrUxzNc5yD7aehQ.png)

**Solución implementada**: 
- Uso de Redis como cola de URLs pendientes (todo_urls) y conjunto de URLs procesadas (done_urls)
- Algoritmo de iteración que evita ciclos infinitos mediante verificación de estados
- Procesamiento breadth-first para optimizar el descubrimiento de contenido

**Detalles técnicos**:
```python
def process_url(self, url):
    if self.redis_client.sismember('done_urls', url):
        return  # URL ya procesada
    
    # Procesar y extraer nuevos enlaces
    new_urls = self.extract_links(content)
    for new_url in new_urls:
        if not self.redis_client.sismember('done_urls', new_url):
            self.redis_client.lpush('todo_urls', new_url)
```

#### 6.2 Inyección de cookies
**Problema**: El portal PARES requiere cookies específicas para acceder a las imágenes de alta resolución, y estas cookies deben mantenerse a lo largo de la sesión.

**Solución implementada**:
- Sistema de extracción automática de cookies desde las páginas principales
- Mantenimiento de sesiones persistentes con requests.Session()
- Inyección inteligente de cookies en cada petición de descarga

**Detalles técnicos**:
```python
def extract_and_set_cookies(self, page_url):
    response = self.session.get(page_url, proxies=self.proxies)
    # Extracción automática de cookies de la respuesta
    cookies = response.cookies
    # Las cookies se mantienen automáticamente en la sesión
    return cookies
```

#### 6.3 Uso de TOR
**Problema**: La integración con TOR presenta varios desafíos:
- Latencia elevada en las conexiones
- Necesidad de configuración específica del proxy SOCKS5
- Gestión de reconexiones cuando cambian los circuitos TOR

**Soluciones implementadas**:
- Configuración de proxy SOCKS5 mediante socks5h://127.0.0.1:9050
- Sistema de reintentos con backoff exponencial para manejar desconexiones
- Configuración de timeouts adecuados para compensar la latencia de TOR
- Rotación periódica de circuitos para evitar bloqueos

**Configuración TOR**:
```python
proxies = {
    'http': 'socks5h://127.0.0.1:9050',
    'https': 'socks5h://127.0.0.1:9050'
}

# Configuración de timeouts apropiados
response = requests.get(url, proxies=proxies, timeout=30)
```

### Mejoras futuras identificadas:
- Implementación de un sistema de logs más robusto con archivos
- Adición de notificaciones automáticas al completar procesos largos
- Optimización del uso de memoria para datasets muy grandes
- Implementación de resumption automática tras interrupciones

## 7. Referencias utilizadas

### Documentación técnica:
1. **TOR Project Documentation** - https://www.torproject.org/
   - Configuración de proxy SOCKS5
   - Gestión de circuitos y anonimización

2. **Redis Documentation** - https://redis.io/docs/latest/
   - Comandos de bases de datos en memoria
   - Gestión de estructuras de datos temporales

3. **Beautiful Soup Documentation** - https://www.crummy.com/software/BeautifulSoup/bs4/doc/
   - Parsing de HTML y extracción de datos
   - Navegación por árboles DOM

4. **Requests Documentation** - https://docs.python-requests.org/
   - Gestión de sesiones HTTP
   - Manejo de cookies y headers

### Recursos especializados:
5. **Stem Library for TOR** - https://stem.torproject.org/
   - Control programático de TOR
   - Gestión de circuitos y configuración

6. **Web Scraping with Beautiful Soup & Requests** - https://blog.apify.com/web-scraping-with-beautiful-soup/
   - Técnicas avanzadas de scraping
   - Mejores prácticas para extracción de datos

7. **Handling Cookies in Web Scraping** - https://scrapfly.io/blog/how-to-handle-cookies-in-web-scraping/
   - Gestión avanzada de cookies
   - Mantenimiento de sesiones web

### Fuentes gubernamentales:
8. **Portal de Archivos Españoles (PARES)** - http://pares.mcu.es/
   - Documentación oficial del portal
   - Estructura de URLs y metadatos

### Herramientas de desarrollo:
9. **Python Multiprocessing Documentation** - https://docs.python.org/3/library/multiprocessing.html
   - Procesamiento en paralelo
   - Gestión de procesos múltiples

10. **Docker Documentation** - https://docs.docker.com/
    - Containerización de aplicaciones
    - Despliegue simplificado

---

*Documento generado para la presentación del proyecto "Iterando-Pares" - Scraper Web Avanzado*
