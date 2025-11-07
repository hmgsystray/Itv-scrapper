#!/usr/bin/env python3
"""
Scraper para obtener citas en la ITV de Argentona (Applus+)
"""

import os
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv


class ITVArgentona:
    """Scraper para citas de ITV Argentona"""

    def __init__(self, license_plate, headless=True, take_screenshots=True):
        """
        Inicializa el scraper

        Args:
            license_plate (str): Matrícula del vehículo sin espacios
            headless (bool): Ejecutar navegador en modo headless
            take_screenshots (bool): Tomar capturas de pantalla
        """
        self.license_plate = license_plate.replace(" ", "").replace("-", "").upper()
        self.headless = headless
        self.take_screenshots = take_screenshots
        self.booking_url = "https://aibs.appluscorp.com/?MenuActivo=mrNuevaReserva"
        self.driver = None

    def _setup_driver(self):
        """Configura el driver de Selenium"""
        chrome_options = Options()

        if self.headless:
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")

        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # User agent para evitar detección
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)

        # Eliminar propiedades de webdriver
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def _take_screenshot(self, name):
        """Toma una captura de pantalla"""
        if self.take_screenshots and self.driver:
            os.makedirs("screenshots", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"screenshots/{name}_{timestamp}.png"
            self.driver.save_screenshot(filepath)
            print(f"📸 Captura guardada: {filepath}")

    def search_appointments(self):
        """
        Busca citas disponibles para la matrícula

        Returns:
            list: Lista de citas disponibles
        """
        try:
            print(f"🚗 Buscando citas para matrícula: {self.license_plate}")

            # Configurar driver
            self._setup_driver()

            # Navegar a la página de reservas
            print(f"🌐 Accediendo a {self.booking_url}")
            self.driver.get(self.booking_url)
            time.sleep(2)

            self._take_screenshot("01_pagina_inicial")

            # Buscar el campo de matrícula
            print("🔍 Buscando campo de matrícula...")
            wait = WebDriverWait(self.driver, 10)

            # Intentar diferentes selectores para el input de matrícula
            plate_input = None
            selectors = [
                "input[placeholder*='matrícula']",
                "input[name='matricula']",
                "input[id*='matricula']",
                "input[type='text']"
            ]

            for selector in selectors:
                try:
                    plate_input = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    print(f"✓ Campo encontrado con selector: {selector}")
                    break
                except:
                    continue

            if not plate_input:
                print("❌ No se pudo encontrar el campo de matrícula")
                self._take_screenshot("error_campo_no_encontrado")
                return []

            # Ingresar matrícula
            print(f"⌨️  Ingresando matrícula: {self.license_plate}")
            plate_input.clear()
            plate_input.send_keys(self.license_plate)
            time.sleep(1)

            self._take_screenshot("02_matricula_ingresada")

            # Buscar botón de continuar/buscar
            print("🔍 Buscando botón de búsqueda...")
            button = None
            button_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button.btn-primary",
                "a.btn-primary",
                "button:contains('Continuar')",
                "button:contains('Buscar')",
                "button:contains('Siguiente')"
            ]

            for selector in button_selectors:
                try:
                    button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if button.is_displayed() and button.is_enabled():
                        print(f"✓ Botón encontrado con selector: {selector}")
                        break
                except:
                    continue

            if button:
                print("👆 Haciendo click en el botón...")
                button.click()
                time.sleep(3)

                self._take_screenshot("03_despues_de_buscar")

                # Esperar a que cargue la siguiente página
                print("⏳ Esperando carga de citas disponibles...")
                time.sleep(3)

                # Intentar extraer información de citas
                appointments = self._extract_appointments()

                return appointments
            else:
                print("❌ No se pudo encontrar el botón de búsqueda")
                self._take_screenshot("error_boton_no_encontrado")
                return []

        except Exception as e:
            print(f"❌ Error durante la búsqueda: {str(e)}")
            self._take_screenshot("error_general")
            return []
        finally:
            self.close()

    def _extract_appointments(self):
        """
        Extrae información de citas disponibles de la página

        Returns:
            list: Lista de diccionarios con información de citas
        """
        appointments = []

        try:
            # Capturar el HTML de la página
            page_source = self.driver.page_source

            # Buscar elementos que puedan contener citas
            # Esto dependerá de la estructura real de la página
            date_elements = self.driver.find_elements(By.CSS_SELECTOR, "[class*='fecha'], [class*='date'], .appointment-date")
            time_elements = self.driver.find_elements(By.CSS_SELECTOR, "[class*='hora'], [class*='time'], .appointment-time")

            if date_elements or time_elements:
                print(f"✓ Encontrados {len(date_elements)} elementos de fecha")
                print(f"✓ Encontrados {len(time_elements)} elementos de hora")

                for i, elem in enumerate(date_elements[:10]):  # Limitar a 10 primeras
                    try:
                        appointments.append({
                            'index': i + 1,
                            'text': elem.text,
                            'html': elem.get_attribute('outerHTML')[:200]
                        })
                    except:
                        pass

            # Si no encontramos elementos específicos, guardar info de la página
            if not appointments:
                print("ℹ️  No se encontraron citas con los selectores estándar")
                print("📄 Guardando HTML de la página para análisis...")

                # Guardar el HTML para análisis manual
                os.makedirs("output", exist_ok=True)
                with open("output/page_content.html", "w", encoding="utf-8") as f:
                    f.write(page_source)
                print("✓ HTML guardado en output/page_content.html")

                # Buscar cualquier elemento que pueda ser relevante
                all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                all_divs = self.driver.find_elements(By.CSS_SELECTOR, "[class*='cita'], [class*='appointment'], [class*='reserv']")

                print(f"ℹ️  Elementos encontrados en la página:")
                print(f"   - {len(all_buttons)} botones")
                print(f"   - {len(all_divs)} divs relacionados con citas/reservas")

        except Exception as e:
            print(f"⚠️  Error al extraer citas: {str(e)}")

        return appointments

    def close(self):
        """Cierra el navegador"""
        if self.driver:
            print("🔒 Cerrando navegador...")
            self.driver.quit()


def main():
    """Función principal"""
    load_dotenv()

    # Obtener configuración
    license_plate = os.getenv("LICENSE_PLATE")
    headless = os.getenv("HEADLESS", "true").lower() == "true"
    screenshot = os.getenv("SCREENSHOT", "true").lower() == "true"

    if not license_plate:
        print("❌ Error: No se ha configurado LICENSE_PLATE en el archivo .env")
        print("💡 Copia config.example.env a .env y configura tu matrícula")
        return

    # Crear scraper y buscar citas
    scraper = ITVArgentona(
        license_plate=license_plate,
        headless=headless,
        take_screenshots=screenshot
    )

    appointments = scraper.search_appointments()

    # Mostrar resultados
    print("\n" + "="*50)
    print("📋 RESULTADOS DE LA BÚSQUEDA")
    print("="*50)

    if appointments:
        print(f"\n✓ Se encontraron {len(appointments)} citas disponibles:\n")
        for apt in appointments:
            print(f"{apt['index']}. {apt['text']}")
    else:
        print("\n⚠️  No se encontraron citas disponibles o hubo un error")
        print("💡 Revisa las capturas en la carpeta 'screenshots' para más información")
        print("💡 Revisa el HTML en 'output/page_content.html' para análisis detallado")

    print("\n" + "="*50)


if __name__ == "__main__":
    main()
