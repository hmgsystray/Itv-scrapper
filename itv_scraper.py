#!/usr/bin/env python3
"""
Scraper completo que navega por todo el flujo de reserva de ITV Argentona
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
    """Scraper completo para citas de ITV Argentona con navegación multi-paso"""

    def __init__(self, license_plate, save_html=True):
        """
        Inicializa el scraper

        Args:
            license_plate (str): Matrícula del vehículo sin espacios
            save_html (bool): Guardar HTML para análisis
        """
        self.license_plate = license_plate.replace(" ", "").replace("-", "").upper()
        self.save_html = save_html
        self.base_url = "https://aibs.appluscorp.com"
        self.guid_sesion = None

        # Crear sesión con headers realistas
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.applusiteuve.com/'
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

    def _extract_guid_sesion(self, text):
        """Extrae el guidSesion del HTML"""
        match = re.search(r'guidSesion["\s=:]+([a-f0-9\-]{36})', text, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _extract_appointments_from_html(self, html_content):
        """Extrae citas del HTML"""
        appointments = []
        soup = BeautifulSoup(html_content, 'html.parser')

        # Buscar elementos relacionados con fechas y horas
        # Estrategia 1: Buscar calendarios, slots, horarios
        selectors = [
            ('[class*="disponible"]', 'disponible'),
            ('[class*="slot"]', 'slot'),
            ('[class*="horario"]', 'horario'),
            ('[class*="fecha"]', 'fecha'),
            ('[data-fecha]', 'data-fecha'),
            ('[data-hora]', 'data-hora'),
            ('.appointment', 'appointment'),
            ('.time-slot', 'time-slot'),
        ]

        for selector, type_name in selectors:
            try:
                elements = soup.select(selector)
                for elem in elements:
                    text = elem.get_text(strip=True)
                    if text and len(text) > 3:
                        appointments.append({
                            'text': text,
                            'type': type_name,
                            'fecha': elem.get('data-fecha', ''),
                            'hora': elem.get('data-hora', ''),
                        })
            except:
                pass

        # Estrategia 2: Buscar botones con fechas
        buttons = soup.find_all(['button', 'a', 'div'], class_=True)
        for button in buttons:
            text = button.get_text(strip=True)
            classes = ' '.join(button.get('class', []))

            # Detectar si contiene fecha/hora
            if any(word in text.lower() for word in ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                                                       'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']):
                appointments.append({
                    'text': text,
                    'type': 'button_fecha',
                    'classes': classes
                })
            elif re.search(r'\d{1,2}:\d{2}', text):
                appointments.append({
                    'text': text,
                    'type': 'button_hora',
                    'classes': classes
                })

        # Deduplicar
        seen = set()
        unique = []
        for apt in appointments:
            key = apt['text']
            if key and key not in seen:
                seen.add(key)
                unique.append(apt)

        return unique

    def _navegar_siguiente_paso(self, actual_view_name, post_data=None):
        """Navega al siguiente paso del proceso"""
        if not self.guid_sesion:
            print("⚠️  No hay guidSesion para navegar")
            return None

        url = f"{self.base_url}/Reserva/NavegarAVistaSiguiente"
        params = {
            'guidSesion': self.guid_sesion,
            'actualViewName': actual_view_name
        }

        try:
            if post_data:
                # POST con datos
                response = self.session.post(url, params=params, data=post_data)
            else:
                # GET simple
                response = self.session.get(url, params=params)

            if response.status_code != 200:
                print(f"   ⚠️  Código de respuesta: {response.status_code}")
                # Guardar respuesta de error para análisis
                self._save_html(response.text, f"error_{actual_view_name}")

            response.raise_for_status()
            return response
        except Exception as e:
            print(f"⚠️  Error al navegar desde {actual_view_name}: {e}")
            return None

    def _analizar_paso_vehiculo(self, html):
        """Analiza el paso de vehículo para extraer opciones"""
        soup = BeautifulSoup(html, 'html.parser')

        # Buscar inputs, selects, radios, checkboxes
        inputs = soup.find_all(['input', 'select'])
        print(f"   📋 Campos encontrados: {len(inputs)}")

        datos = {}
        for inp in inputs:
            name = inp.get('name')
            value = inp.get('value')
            inp_type = inp.get('type', 'text')

            if name:
                # Si es radio/checkbox y está checked, usar su valor
                if inp_type in ['radio', 'checkbox']:
                    if inp.get('checked'):
                        datos[name] = value
                # Si es select, tomar la primera opción
                elif inp.name == 'select':
                    options = inp.find_all('option')
                    if options:
                        datos[name] = options[0].get('value', '')
                # Si tiene valor, usarlo
                elif value:
                    datos[name] = value

        if datos:
            print(f"   ✓ Datos del vehículo detectados: {list(datos.keys())}")
        return datos

    def search_appointments(self):
        """
        Busca citas disponibles navegando por todo el flujo

        Returns:
            list: Lista de citas disponibles
        """
        try:
            print("\n" + "="*70)
            print("🚗 SCRAPER ITV ARGENTONA - Navegación Automática")
            print("="*70)
            print(f"Matrícula: {self.license_plate}")
            print(f"Estación: Argentona (B08)")
            print("="*70 + "\n")

            # PASO 1: Acceder con la matrícula
            print("📍 PASO 1/5: Iniciando con matrícula...")
            url_step1 = f"{self.base_url}/Reserva/ReservarMatricula?language=es&AppCentro=B08&Matricula={self.license_plate}"

            response = self.session.get(url_step1)
            response.raise_for_status()

            print(f"✓ Respuesta recibida (código {response.status_code})")
            self._save_html(response.text, "paso1_datos_contacto")

            # Extraer guidSesion
            self.guid_sesion = self._extract_guid_sesion(response.text)
            if self.guid_sesion:
                print(f"✓ guidSesion: {self.guid_sesion}\n")
            else:
                print("❌ No se pudo obtener guidSesion")
                return []

            # PASO 2: Navegar desde Datos_Contacto a Eleccion_Vehiculo
            print("📍 PASO 2/5: Datos de contacto → Vehículo...")
            response = self._navegar_siguiente_paso('Datos_Contacto')
            if response:
                print(f"✓ Navegado a vehículo")
                self._save_html(response.text, "paso2_vehiculo")

                # Analizar el paso de vehículo
                datos_vehiculo = self._analizar_paso_vehiculo(response.text)
            else:
                print("⚠️  No se pudo navegar al paso de vehículo")
                return []

            time.sleep(0.5)

            # PASO 3: Navegar desde Eleccion_Vehiculo a Eleccion_Estacion
            print("📍 PASO 3/5: Vehículo → Estación...")
            # Intentar con los datos del vehículo si los hay
            if datos_vehiculo:
                print(f"   📤 Enviando datos del vehículo...")
                response = self._navegar_siguiente_paso('Eleccion_Vehiculo', post_data=datos_vehiculo)
            else:
                # Intentar sin datos
                response = self._navegar_siguiente_paso('Eleccion_Vehiculo')

            if response:
                print(f"✓ Navegado a estación")
                self._save_html(response.text, "paso3_estacion")
            else:
                print("⚠️  No se pudo navegar al paso de estación")
                print("💡 El servidor podría requerir seleccionar un tipo de vehículo específico")
                print("💡 Revisa output/paso2_vehiculo_*.html para ver las opciones")
                return []

            time.sleep(0.5)

            # PASO 4: Navegar desde Eleccion_Estacion - ¡AQUÍ ESTÁN LAS FECHAS!
            print("📍 PASO 4/4: Estación → FECHAS DISPONIBLES...")
            response = self._navegar_siguiente_paso('Eleccion_Estacion')
            if response:
                print(f"✓ ¡Llegamos al calendario de fechas disponibles!")
                html_file = self._save_html(response.text, "paso4_FECHAS_DISPONIBLES")
                print(f"✓ HTML completo guardado en: {html_file}")
            else:
                print("⚠️  No se pudo llegar al paso de fechas")
                return []

            time.sleep(1)

            # PASO 5: Extraer citas disponibles del HTML
            print("\n📍 ANALIZANDO FECHAS DISPONIBLES...")
            print("="*70)

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extraer TODO el texto visible de la página
            texto_visible = soup.get_text()

            # Buscar patrones de fechas en el texto
            import re
            # Patrón dd/mm/yyyy
            fechas_formato1 = re.findall(r'\b(\d{1,2}/\d{1,2}/\d{4})\b', texto_visible)
            # Patrón "5 de febrero de 2025"
            fechas_formato2 = re.findall(r'\b(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})\b', texto_visible, re.IGNORECASE)
            # Patrón de horas HH:MM
            horas_encontradas = re.findall(r'\b(\d{1,2}:\d{2})\b', texto_visible)

            print(f"📅 Fechas encontradas (dd/mm/yyyy): {len(fechas_formato1)}")
            if fechas_formato1:
                for fecha in list(set(fechas_formato1))[:10]:
                    print(f"   • {fecha}")

            print(f"\n📅 Fechas encontradas (formato texto): {len(fechas_formato2)}")
            if fechas_formato2:
                for fecha in list(set(fechas_formato2))[:10]:
                    print(f"   • {fecha}")

            print(f"\n🕐 Horas encontradas: {len(horas_encontradas)}")
            if horas_encontradas:
                for hora in list(set(horas_encontradas))[:20]:
                    print(f"   • {hora}")

            # Buscar elementos específicos de calendario
            print(f"\n🔍 Buscando elementos de calendario...")

            # Buscar divs/botones con clases relacionadas con calendario
            elementos_calendario = soup.find_all(class_=re.compile(r'(calendar|dia|fecha|disponible|slot|time)', re.I))
            print(f"   Elementos con clases de calendario: {len(elementos_calendario)}")

            # Buscar elementos con data-fecha o similar
            elementos_data = soup.find_all(attrs={'data-fecha': True}) + \
                           soup.find_all(attrs={'data-date': True}) + \
                           soup.find_all(attrs={'data-dia': True})
            print(f"   Elementos con data-fecha: {len(elementos_data)}")

            # Extraer citas con el método mejorado
            appointments = self._extract_appointments_from_html(response.text)

            # Combinar todo en una lista de citas
            citas_encontradas = []

            # De las fechas regex
            for fecha in set(fechas_formato1):
                citas_encontradas.append({'text': fecha, 'type': 'fecha_dd_mm_yyyy'})
            for fecha in set(fechas_formato2):
                citas_encontradas.append({'text': fecha, 'type': 'fecha_texto'})

            # De los elementos DOM
            citas_encontradas.extend(appointments)

            print(f"\n📊 TOTAL CITAS/FECHAS DETECTADAS: {len(citas_encontradas)}")
            print("="*70)

            if citas_encontradas:
                print("\n✅ Muestra de citas encontradas:")
                for i, cita in enumerate(citas_encontradas[:15], 1):
                    print(f"{i}. {cita.get('text', 'N/A')} [tipo: {cita.get('type', 'N/A')}]")
                if len(citas_encontradas) > 15:
                    print(f"... y {len(citas_encontradas) - 15} más")
            else:
                print("\n⚠️  No se detectaron citas con los métodos automáticos")
                print(f"💡 Abre el archivo: {html_file}")
                print("💡 Y busca cómo se ven las fechas disponibles en el HTML")
                print("💡 Luego dime la estructura y ajustaré el extractor")

            return citas_encontradas

        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def close(self):
        """Cierra la sesión"""
        self.session.close()


def main():
    """Función principal"""
    load_dotenv()

    license_plate = os.getenv("LICENSE_PLATE", "3332FSS")

    print("\n" + "╔" + "="*68 + "╗")
    print("║" + " "*15 + "ITV ARGENTONA SCRAPER v2.0" + " "*27 + "║")
    print("╚" + "="*68 + "╝\n")

    scraper = ITVArgentona(license_plate=license_plate, save_html=True)
    appointments = scraper.search_appointments()
    scraper.close()

    if appointments:
        print("\n" + "="*70)
        print(f"✅ Se encontraron {len(appointments)} posibles citas:")
        print("="*70)
        for i, apt in enumerate(appointments[:10], 1):
            print(f"{i}. {apt.get('text', 'N/A')} (tipo: {apt.get('type', 'N/A')})")
        print("="*70 + "\n")


if __name__ == "__main__":
    main()
