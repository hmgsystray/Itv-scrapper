#!/usr/bin/env python3
"""
Scraper optimizado para ITV Argentona usando endpoint de API REST
Usa el endpoint GetFechasHorasDisponibles para obtener disponibilidad directamente en JSON
"""

import os
import re
import random
import string
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dotenv import load_dotenv


def generate_random_license_plate() -> str:
    """
    Genera una matrícula aleatoria con formato español válido

    Formato: 4 dígitos + 3 letras consonantes (ej: 1234BCF)
    Se evitan vocales para prevenir combinaciones ofensivas

    Returns:
        str: Matrícula aleatoria válida
    """
    # Dígitos: 4 números aleatorios
    digits = ''.join(random.choices(string.digits, k=4))

    # Letras: 3 consonantes aleatorias (sin Ñ, Q para simplicidad)
    consonants = 'BCDFGHJKLMNPRSTVWXYZ'
    letters = ''.join(random.choices(consonants, k=3))

    return f"{digits}{letters}"


class ITVScraper:
    """Scraper optimizado que usa el endpoint de API REST de ITV Argentona"""

    def __init__(self, license_plate: Optional[str] = None):
        """
        Inicializa el scraper

        Args:
            license_plate: Matrícula del vehículo sin espacios. Si es None, genera una aleatoria.
        """
        if license_plate is None:
            self.license_plate = generate_random_license_plate()
            print(f"[INFO] Usando matrícula generada aleatoriamente: {self.license_plate}")
        else:
            self.license_plate = license_plate.replace(" ", "").replace("-", "").upper()

        self.base_url = "https://aibs.appluscorp.com"
        self.guid_sesion: Optional[str] = None

        # Crear sesión con headers realistas
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Referer': 'https://www.applusiteuve.com/'
        })

    def _get_guid_sesion(self) -> str:
        """
        Obtiene el guidSesion necesario para las peticiones

        Returns:
            str: GUID de sesión

        Raises:
            Exception: Si no se puede obtener el GUID
        """
        url = f"{self.base_url}/Reserva/ReservarMatricula"
        params = {
            'language': 'es',
            'AppCentro': 'B08',
            'Matricula': self.license_plate
        }

        response = self.session.get(url, params=params)
        response.raise_for_status()

        # Extraer guidSesion del HTML
        match = re.search(r'guidSesion["\s=:]+([a-f0-9\-]{36})', response.text, re.IGNORECASE)
        if not match:
            raise Exception("No se pudo obtener guidSesion del servidor")

        return match.group(1)

    def _navigate_to_dates_page(self) -> None:
        """
        Navega por el flujo necesario para poder acceder al endpoint de fechas

        Raises:
            Exception: Si alguna navegación falla
        """
        # Paso 1: Navegar a Eleccion_Estacion
        response = self.session.get(
            f"{self.base_url}/Reserva/NavegarAVistaSiguiente",
            params={
                'guidSesion': self.guid_sesion,
                'actualViewName': 'Datos_Contacto'
            }
        )
        response.raise_for_status()

        # Paso 2: Navegar a página de fechas
        response = self.session.get(
            f"{self.base_url}/Reserva/NavegarAVistaSiguiente",
            params={
                'guidSesion': self.guid_sesion,
                'actualViewName': 'Eleccion_Estacion'
            }
        )
        response.raise_for_status()

    def get_available_dates(self, month: Optional[int] = None, year: Optional[int] = None,
                           months_ahead: int = 3, reuse_guid: bool = False) -> List[Dict]:
        """
        Obtiene las fechas y horas disponibles del endpoint de API

        Args:
            month: Mes a consultar (1-12). Si None, usa mes actual
            year: Año a consultar. Si None, usa año actual
            months_ahead: Número de meses adicionales a consultar (default: 3)
            reuse_guid: Si True, reutiliza el GUID existente sin regenerar (default: False)

        Returns:
            List[Dict]: Lista de citas disponibles con formato:
                {
                    'fecha': '2025-11-07',
                    'hora': '09:00',
                    'precio': 40.6,
                    'fecha_hora': '2025-11-07 09:00'
                }
        """
        # Obtener o reutilizar guidSesion
        if not reuse_guid or self.guid_sesion is None:
            print(f"Obteniendo guidSesion para matrícula {self.license_plate}...")
            self.guid_sesion = self._get_guid_sesion()
            print(f"[OK] guidSesion: {self.guid_sesion}")

            # Navegar por el flujo (necesario solo la primera vez para establecer sesión)
            print("Navegando por el flujo del portal...")
            self._navigate_to_dates_page()
            print("[OK] Flujo completado")
        else:
            print(f"Reutilizando guidSesion existente: {self.guid_sesion}")

        # Determinar meses a consultar
        now = datetime.now()
        start_month = month or now.month
        start_year = year or now.year

        all_appointments = []

        # Consultar múltiples meses
        current_date = datetime(start_year, start_month, 1)

        for i in range(months_ahead + 1):
            mes = current_date.month
            anyo = current_date.year

            print(f"\nConsultando {anyo}-{mes:02d}...")

            # Llamar al endpoint de API
            response = self.session.get(
                f"{self.base_url}/Reserva/GetFechasHorasDisponibles",
                params={
                    'guidSesion': self.guid_sesion,
                    'mes': f"{mes:02d}",
                    'anyo': str(anyo)
                }
            )

            if response.status_code != 200:
                print(f"[AVISO] Error al obtener fechas de {anyo}-{mes:02d}: {response.status_code}")
                # Si falla, invalidar el GUID para regenerar en próximo intento
                if response.status_code == 500:
                    self.guid_sesion = None
                continue

            # Parsear JSON
            data = response.json()

            # Extraer citas disponibles
            appointments = self._extract_available_appointments(data)
            all_appointments.extend(appointments)

            print(f"  [OK] Encontradas {len(appointments)} citas disponibles")

            # Avanzar al siguiente mes
            if current_date.month == 12:
                current_date = datetime(current_date.year + 1, 1, 1)
            else:
                current_date = datetime(current_date.year, current_date.month + 1, 1)

        return all_appointments

    def _extract_available_appointments(self, data: Dict) -> List[Dict]:
        """
        Extrae las citas disponibles del JSON de respuesta

        Args:
            data: JSON de respuesta del endpoint GetFechasHorasDisponibles

        Returns:
            List[Dict]: Lista de citas disponibles
        """
        appointments = []

        for dia in data.get('dias', []):
            # Saltar días sin disponibilidad
            if not dia.get('Seleccionable'):
                continue

            fecha = dia['FechaString']  # "2025-11-07"

            for hora in dia.get('horas', []):
                if hora.get('Disponible'):
                    appointments.append({
                        'fecha': fecha,
                        'hora': hora['Hora'],
                        'precio': hora['Precio'],
                        'fecha_hora': f"{fecha} {hora['Hora']}"
                    })

        return appointments

    def close(self):
        """Cierra la sesión HTTP"""
        self.session.close()


def main():
    """Función principal para testing"""
    load_dotenv()

    # Por defecto, usar matrícula aleatoria (no es necesario tener una real)
    license_plate = None  # None = genera matrícula aleatoria

    # Si prefieres usar una matrícula específica del .env (opcional):
    # license_plate = os.getenv("LICENSE_PLATE")

    print("\n" + "="*70)
    print("  ITV ARGENTONA SCRAPER - Optimizado con API REST")
    print("="*70)
    print(f"Estación: ITV Argentona (B08)")
    print("="*70 + "\n")

    scraper = ITVScraper(license_plate=license_plate)

    print(f"Matrícula usada: {scraper.license_plate}")
    print("="*70 + "\n")

    try:
        # Obtener citas de los próximos 3 meses
        appointments = scraper.get_available_dates(months_ahead=3)

        print("\n" + "="*70)
        print(f"  RESULTADOS")
        print("="*70)
        print(f"Total de citas disponibles: {len(appointments)}")

        if appointments:
            print("\nPrimeras 20 citas disponibles:")
            for i, apt in enumerate(appointments[:20], 1):
                print(f"{i:2d}. {apt['fecha_hora']} - {apt['precio']}€")

            if len(appointments) > 20:
                print(f"\n... y {len(appointments) - 20} citas más")
        else:
            print("\n[AVISO] No se encontraron citas disponibles en los próximos 3 meses")

        print("="*70 + "\n")

    except Exception as e:
        print(f"\n[ERROR] Error: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
