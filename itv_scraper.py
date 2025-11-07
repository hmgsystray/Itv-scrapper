#!/usr/bin/env python3
"""
Scraper ligero para obtener citas en la ITV de Argentona usando requests
"""

import os
import re
import time
import json
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


class ITVArgentona:
    """Scraper ligero para citas de ITV Argentona"""

    def __init__(self, license_plate, save_html=True):
        """
        Inicializa el scraper

        Args:
            license_plate (str): Matrícula del vehículo sin espacios
            save_html (bool): Guardar HTML para análisis
        """
        self.license_plate = license_plate.replace(" ", "").replace("-", "").upper()
        self.save_html = save_html
        # URL directa con matrícula y código de estación B08 (Argentona)
        self.booking_url = f"https://aibs.appluscorp.com/Reserva/ReservarMatricula?language=es&AppCentro=B08&Matricula={self.license_plate}"
        self.base_url = "https://aibs.appluscorp.com"

        # Crear sesión con headers realistas
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

    def _save_html(self, content, name):
        """Guarda HTML para análisis"""
        if self.save_html:
            os.makedirs("output", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"output/{name}_{timestamp}.html"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"💾 HTML guardado: {filepath}")
            return filepath
        return None

    def _extract_appointments_from_html(self, html_content):
        """
        Extrae citas del HTML usando BeautifulSoup

        Args:
            html_content (str): Contenido HTML

        Returns:
            list: Lista de citas encontradas
        """
        appointments = []
        soup = BeautifulSoup(html_content, 'html.parser')

        # Estrategia 1: Buscar elementos con clases relacionadas con citas
        selectors = [
            {'class': re.compile(r'.*cita.*', re.I)},
            {'class': re.compile(r'.*disponible.*', re.I)},
            {'class': re.compile(r'.*appointment.*', re.I)},
            {'class': re.compile(r'.*slot.*', re.I)},
            {'class': re.compile(r'.*horario.*', re.I)},
            {'class': re.compile(r'.*fecha.*', re.I)},
        ]

        for selector in selectors:
            elements = soup.find_all(attrs=selector)
            for elem in elements:
                text = elem.get_text(strip=True)
                if text and len(text) > 3:  # Filtrar elementos vacíos
                    appointments.append({
                        'text': text,
                        'type': 'class_match',
                        'class': elem.get('class', []),
                        'html': str(elem)[:200]
                    })

        # Estrategia 2: Buscar botones con fechas/horas
        buttons = soup.find_all(['button', 'a'])
        for button in buttons:
            text = button.get_text(strip=True)
            # Buscar patrones de fecha/hora
            if text and (any(char.isdigit() for char in text) or
                        any(month in text.lower() for month in
                            ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                             'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'])):

                # Evitar botones de navegación
                if not any(skip in text.lower() for skip in ['menu', 'inicio', 'cerrar', 'cancelar', 'volver']):
                    appointments.append({
                        'text': text,
                        'type': 'button',
                        'href': button.get('href', ''),
                        'onclick': button.get('onclick', '')
                    })

        # Estrategia 3: Buscar calendarios (FullCalendar, etc)
        calendar_elements = soup.find_all(['td', 'div'], attrs={
            'data-date': True,
            'data-time': True
        })
        for elem in calendar_elements:
            appointments.append({
                'text': elem.get_text(strip=True),
                'type': 'calendar',
                'date': elem.get('data-date'),
                'time': elem.get('data-time')
            })

        # Estrategia 4: Buscar en tablas
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if cells:
                    row_text = ' | '.join([cell.get_text(strip=True) for cell in cells if cell.get_text(strip=True)])
                    if row_text and any(char.isdigit() for char in row_text):
                        appointments.append({
                            'text': row_text,
                            'type': 'table_row'
                        })

        # Estrategia 5: Buscar con regex en todo el texto
        text_content = soup.get_text()

        # Patrón: dd/mm/yyyy o dd-mm-yyyy
        date_pattern = r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b'
        dates_found = re.findall(date_pattern, text_content)

        # Patrón: "15 de enero de 2024"
        spanish_date_pattern = r'\b(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})\b'
        spanish_dates = re.findall(spanish_date_pattern, text_content, re.IGNORECASE)

        # Patrón: Horas (HH:MM)
        time_pattern = r'\b(\d{1,2}:\d{2})\b'
        times_found = re.findall(time_pattern, text_content)

        for date in dates_found[:20]:  # Limitar resultados
            appointments.append({
                'text': date,
                'type': 'regex_date'
            })

        for date in spanish_dates[:20]:
            appointments.append({
                'text': date,
                'type': 'regex_spanish_date'
            })

        # Deduplicar
        seen = set()
        unique_appointments = []
        for apt in appointments:
            key = apt['text']
            if key and key not in seen and len(key) > 3:
                seen.add(key)
                unique_appointments.append(apt)

        return unique_appointments

    def search_appointments(self):
        """
        Busca citas disponibles para la matrícula

        Returns:
            list: Lista de citas disponibles
        """
        try:
            print(f"🚗 Buscando citas para matrícula: {self.license_plate}")
            print(f"🌐 Accediendo directamente a: {self.booking_url}")

            # Hacer petición GET directa con la matrícula en la URL
            response = self.session.get(self.booking_url)
            response.raise_for_status()

            print(f"✓ Respuesta recibida (código {response.status_code})")
            print(f"✓ URL final (después de redirects): {response.url}")
            self._save_html(response.text, "01_reserva_matricula")

            # Analizar la página
            soup = BeautifulSoup(response.text, 'html.parser')

            # Buscar guidSesion en la página
            guid_match = re.search(r'guidSesion["\s=:]+([a-f0-9\-]{36})', response.text, re.IGNORECASE)
            if guid_match:
                guid_sesion = guid_match.group(1)
                print(f"🔑 guidSesion encontrado: {guid_sesion}")
            else:
                print("⚠️  No se encontró guidSesion en la página")

            # Buscar todos los scripts externos
            print("\n📜 Scripts externos encontrados:")
            external_scripts = soup.find_all('script', src=True)
            for script in external_scripts[:5]:  # Mostrar primeros 5
                print(f"   - {script.get('src')}")

            # Buscar scripts que puedan contener endpoints de citas
            scripts = soup.find_all('script')
            api_endpoints = []

            print("\n🔍 Analizando scripts inline...")
            for script in scripts:
                script_text = script.string if script.string else ''
                # Buscar URLs de API relacionadas con reservas
                urls = re.findall(r'["\']/(Reserva/\w+)["\']', script_text)
                api_endpoints.extend(urls)

                # Buscar también endpoints con fetch o ajax
                fetch_urls = re.findall(r'(?:fetch|ajax).*?["\']([^"\']+)["\']', script_text)
                api_endpoints.extend(fetch_urls)

            if api_endpoints:
                unique_endpoints = list(set(api_endpoints))
                print(f"\n🔗 Endpoints API encontrados ({len(unique_endpoints)}):")
                for endpoint in unique_endpoints[:10]:  # Mostrar primeros 10
                    print(f"   - {endpoint}")

            # Buscar formularios
            forms = soup.find_all('form')
            print(f"\n📝 Formularios encontrados: {len(forms)}")
            for i, form in enumerate(forms, 1):
                action = form.get('action', 'No action')
                method = form.get('method', 'GET').upper()
                print(f"   Formulario #{i}: {method} → {action}")

            # Buscar pasos del proceso de reserva
            print("\n🔢 Buscando pasos del proceso...")
            steps_text = ['contacto', 'vehículo', 'estación', 'fecha', 'hora', 'datos', 'pago']
            for step_word in steps_text:
                if step_word in response.text.lower():
                    matches = re.findall(rf'[^<>]*{step_word}[^<>]*', response.text.lower())
                    if matches:
                        print(f"   ✓ '{step_word}' encontrado en la página")

            # Buscar citas en la respuesta
            print("\n🔍 Extrayendo citas disponibles...")
            appointments = self._extract_appointments_from_html(response.text)

            print(f"\n📊 Total de elementos encontrados: {len(appointments)}")

            # Mostrar resumen por tipo
            if appointments:
                types = {}
                for apt in appointments:
                    apt_type = apt.get('type', 'unknown')
                    types[apt_type] = types.get(apt_type, 0) + 1

                print(f"📈 Resumen por tipo:")
                for apt_type, count in types.items():
                    print(f"   - {apt_type}: {count}")
            else:
                print("\n💡 No se encontraron citas en esta página")
                print("   Parece que estás en el paso de 'Datos de Contacto'")
                print("   Las citas se mostrarán en un paso posterior")

            return appointments

        except requests.RequestException as e:
            print(f"❌ Error de conexión: {str(e)}")
            return []
        except Exception as e:
            print(f"❌ Error general: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def close(self):
        """Cierra la sesión"""
        self.session.close()
        print("🔒 Sesión cerrada")


def main():
    """Función principal"""
    load_dotenv()

    # Obtener configuración
    license_plate = os.getenv("LICENSE_PLATE")

    if not license_plate:
        print("❌ Error: No se ha configurado LICENSE_PLATE en el archivo .env")
        print("💡 Copia config.example.env a .env y configura tu matrícula")
        return

    # Crear scraper y buscar citas
    print("\n" + "="*70)
    print("  ITV ARGENTONA SCRAPER (requests version)")
    print("="*70 + "\n")

    scraper = ITVArgentona(license_plate=license_plate, save_html=True)
    appointments = scraper.search_appointments()
    scraper.close()

    # Mostrar resultados
    print("\n" + "="*70)
    print("📋 RESULTADOS DE LA BÚSQUEDA")
    print("="*70)

    if appointments:
        print(f"\n✓ Se encontraron {len(appointments)} elementos:\n")
        for i, apt in enumerate(appointments[:20], 1):  # Mostrar máximo 20
            print(f"{i}. [{apt.get('type', 'N/A')}] {apt.get('text', 'N/A')}")

        if len(appointments) > 20:
            print(f"\n... y {len(appointments) - 20} más")
    else:
        print("\n⚠️  No se encontraron citas disponibles")
        print("💡 Revisa los archivos HTML en la carpeta 'output' para análisis")

    print("\n" + "="*70)


if __name__ == "__main__":
    main()
