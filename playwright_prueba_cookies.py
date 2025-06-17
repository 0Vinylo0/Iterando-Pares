from playwright.sync_api import sync_playwright

def get_cookies_from_url(url, browser_name='chromium'):
    with sync_playwright() as p:
        # Selecciona el navegador: chromium, firefox o webkit
        browser_type = getattr(p, browser_name)
        browser = browser_type.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Ir a la URL
        page.goto(url)
        page.wait_for_load_state("networkidle")

        # Extraer cookies
        cookies = context.cookies()

        print(f"\nCookies extraídas desde {browser_name} para {url}:")
        for cookie in cookies:
            print(f"{cookie['name']}={cookie['value']}")

        browser.close()

# 🔁 Prueba con diferentes navegadores
get_cookies_from_url("https://pares.mcu.es/ParesBusquedas20/catalogo/contiene/1235", "chromium")
# También puedes probar con "firefox" o "webkit"
