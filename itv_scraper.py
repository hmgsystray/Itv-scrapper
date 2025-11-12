#!/usr/bin/env python3
"""
Scraper optimizado para estaciones ITV usando endpoint de API REST
Usa el endpoint GetFechasHorasDisponibles para obtener disponibilidad directamente en JSON
"""

import os
import re
import random
import string
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable, Any
from functools import wraps
from dotenv import load_dotenv
from requests.exceptions import (
    ConnectionError,
    Timeout,
    RequestException,
    HTTPError
)
from http.client import RemoteDisconnected

# Import configuration
try:
    from config import (
        REQUEST_TIMEOUT_SECONDS,
        MAX_RETRIES,
        RETRY_BACKOFF_FACTOR,
        RETRY_BACKOFF_MAX
    )
except ImportError:
    # Fallback values if config.py is not available
    REQUEST_TIMEOUT_SECONDS = 60
    MAX_RETRIES = 3
    RETRY_BACKOFF_FACTOR = 1
    RETRY_BACKOFF_MAX = 10


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


def retry_on_network_error(max_retries: int = MAX_RETRIES,
                           backoff_factor: float = RETRY_BACKOFF_FACTOR,
                           backoff_max: float = RETRY_BACKOFF_MAX):
    """
    Decorator to retry a function on network errors with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Factor for exponential backoff (e.g., 1 = 1s, 2s, 4s, 8s...)
        backoff_max: Maximum backoff time in seconds

    Returns:
        Decorated function that retries on network errors
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)

                except HTTPError as e:
                    # Don't retry on HTTP errors (400, 404, 500, etc.)
                    # These indicate application-level issues, not network issues
                    print(f"[ERROR] HTTP error: {e}")
                    raise

                except (ConnectionError, Timeout, RemoteDisconnected, RequestException) as e:
                    last_exception = e

                    if attempt < max_retries - 1:
                        # Calculate backoff time with exponential growth
                        backoff_time = min(backoff_factor * (2 ** attempt), backoff_max)

                        print(f"[WARNING] Network error on attempt {attempt + 1}/{max_retries}: {type(e).__name__}")
                        print(f"[INFO] Retrying in {backoff_time:.1f} seconds...")

                        time.sleep(backoff_time)
                    else:
                        print(f"[ERROR] All {max_retries} attempts failed")

            # If all retries failed, raise the last exception
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


class ITVScraper:
    """Scraper optimizado que usa el endpoint de API REST para estaciones ITV de Applus+"""

    def __init__(self, license_plate: Optional[str] = None, station_code: str = "B08"):
        """
        Inicializa el scraper

        Args:
            license_plate: Matrícula del vehículo sin espacios. Si es None, genera una aleatoria.
            station_code: Código de la estación ITV (ej: B08=Argentona, B01=Barcelona)
        """
        if license_plate is None:
            self.license_plate = generate_random_license_plate()
            print(f"[INFO] Usando matrícula generada aleatoriamente: {self.license_plate}")
        else:
            self.license_plate = license_plate.replace(" ", "").replace("-", "").upper()

        self.station_code = station_code
        self.base_url = "https://aibs.appluscorp.com"
        self.guid_sesion: Optional[str] = None
        self._guid_has_navigated: bool = False  # Flag para trackear si el GUID actual navegó el flujo

        # Crear sesión con headers realistas
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Referer': 'https://www.applusiteuve.com/'
        })

    @retry_on_network_error()
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
            'AppCentro': self.station_code,
            'Matricula': self.license_plate
        }

        try:
            response = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()

            # Extraer guidSesion del HTML
            match = re.search(r'guidSesion["\s=:]+([a-f0-9\-]{36})', response.text, re.IGNORECASE)
            if not match:
                raise Exception("No se pudo obtener guidSesion del servidor")

            return match.group(1)

        except Exception as e:
            print(f"[ERROR] Failed to get GUID session: {type(e).__name__}: {e}")
            raise

    @retry_on_network_error()
    def _navigate_to_dates_page(self) -> None:
        """
        Navega por el flujo necesario para poder acceder al endpoint de fechas

        Raises:
            Exception: Si alguna navegación falla
        """
        try:
            # Paso 1: Navegar a Eleccion_Estacion
            response = self.session.get(
                f"{self.base_url}/Reserva/NavegarAVistaSiguiente",
                params={
                    'guidSesion': self.guid_sesion,
                    'actualViewName': 'Datos_Contacto'
                },
                timeout=REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()

            # Paso 2: Navegar a página de fechas
            response = self.session.get(
                f"{self.base_url}/Reserva/NavegarAVistaSiguiente",
                params={
                    'guidSesion': self.guid_sesion,
                    'actualViewName': 'Eleccion_Estacion'
                },
                timeout=REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()

            # Pequeño delay para dar tiempo al servidor a procesar la sesión
            time.sleep(1.5)

        except Exception as e:
            print(f"[ERROR] Navigation failed: {type(e).__name__}: {e}")
            raise

    @retry_on_network_error()
    def _fetch_available_dates_api(self, mes: int, anyo: int) -> Dict:
        """
        Fetch available dates from API endpoint with retry on network errors

        Args:
            mes: Month (1-12)
            anyo: Year (YYYY)

        Returns:
            Dict: JSON response with available dates

        Raises:
            HTTPError: On HTTP errors (400, 500, etc.)
            ConnectionError, Timeout, etc.: On network errors (will be retried)
        """
        response = self.session.get(
            f"{self.base_url}/Reserva/GetFechasHorasDisponibles",
            params={
                'guidSesion': self.guid_sesion,
                'mes': f"{mes:02d}",
                'anyo': str(anyo)
            },
            timeout=REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        return response.json()

    def get_available_dates(self, month: Optional[int] = None, year: Optional[int] = None,
                           months_ahead: Optional[int] = None, days_limit: Optional[int] = None,
                           reuse_guid: bool = False) -> List[Dict]:
        """
        Obtiene las fechas y horas disponibles del endpoint de API

        Args:
            month: Mes a consultar (1-12). Si None, usa mes actual
            year: Año a consultar. Si None, usa año actual
            months_ahead: Número de meses adicionales a consultar. Si None, se calcula automáticamente
                         basado en days_limit. Si days_limit también es None, default: 1 (2 meses total)
            days_limit: Si se especifica, calcula automáticamente months_ahead para cubrir
                       solo los próximos N días. Ej: days_limit=15 → consulta 1-2 meses máximo
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
            self._guid_has_navigated = False  # Nuevo GUID, necesita navegar

        # Navegar por el flujo si el GUID actual no ha navegado aún
        if not self._guid_has_navigated:
            print("Navegando por el flujo del portal...")
            self._navigate_to_dates_page()
            print("[OK] Flujo completado")
            self._guid_has_navigated = True
        else:
            print(f"Reutilizando guidSesion existente: {self.guid_sesion}")

        # Determinar meses a consultar
        now = datetime.now()
        start_month = month or now.month
        start_year = year or now.year

        # Calcular months_ahead automáticamente si se especifica days_limit
        if months_ahead is None:
            if days_limit is not None and days_limit > 0:
                # Calcular fecha límite
                limit_date = now + timedelta(days=days_limit)

                # Calcular cuántos meses diferentes abarca el rango
                start_date = datetime(start_year, start_month, 1)
                months_to_check = 0
                temp_date = start_date

                while temp_date.year < limit_date.year or \
                      (temp_date.year == limit_date.year and temp_date.month <= limit_date.month):
                    months_to_check += 1
                    if temp_date.month == 12:
                        temp_date = datetime(temp_date.year + 1, 1, 1)
                    else:
                        temp_date = datetime(temp_date.year, temp_date.month + 1, 1)

                # months_ahead = meses adicionales después del actual
                months_ahead = max(0, months_to_check - 1)
                print(f"[INFO] Calculado automáticamente: consultar {months_to_check} mes(es) para cubrir próximos {days_limit} días")
            else:
                # Default: consultar 2 meses (mes actual + 1 adicional)
                months_ahead = 1

        all_appointments = []

        # Consultar múltiples meses
        current_date = datetime(start_year, start_month, 1)

        for i in range(months_ahead + 1):
            mes = current_date.month
            anyo = current_date.year

            print(f"\nConsultando {anyo}-{mes:02d}...")

            # Llamar al endpoint de API con retry y timeout
            try:
                data = self._fetch_available_dates_api(mes, anyo)

                # Extraer citas disponibles
                appointments = self._extract_available_appointments(data)
                all_appointments.extend(appointments)
                print(f"  [OK] Encontradas {len(appointments)} citas disponibles")

            except HTTPError as e:
                # Error 500 = GUID inválido o sesión expirada, necesitamos regenerar
                if e.response.status_code == 500:
                    print(f"[WARNING] Error 500 en {anyo}-{mes:02d} - GUID posiblemente expirado, regenerando...")
                    self.guid_sesion = None
                    self._guid_has_navigated = False  # Resetear flag

                    # Reintentar UNA vez con GUID nuevo
                    try:
                        print(f"  Reintentando {anyo}-{mes:02d} con GUID nuevo...")
                        self.guid_sesion = self._get_guid_sesion()
                        self._navigate_to_dates_page()
                        self._guid_has_navigated = True  # Marcar como navegado

                        data = self._fetch_available_dates_api(mes, anyo)
                        appointments = self._extract_available_appointments(data)
                        all_appointments.extend(appointments)
                        print(f"  [OK] Encontradas {len(appointments)} citas disponibles (tras regenerar GUID)")
                    except Exception as retry_error:
                        print(f"  [ERROR] Reintento falló: {type(retry_error).__name__}")
                        continue
                else:
                    # Otros errores HTTP (400, 404, etc.)
                    print(f"[ERROR] HTTP {e.response.status_code} fetching {anyo}-{mes:02d}")
                    if e.response.status_code in [401, 403]:
                        self.guid_sesion = None
                        self._guid_has_navigated = False

            except (ConnectionError, Timeout, RemoteDisconnected, RequestException) as e:
                print(f"[ERROR] Network error fetching {anyo}-{mes:02d}: {type(e).__name__}: {e}")
                self.guid_sesion = None
                self._guid_has_navigated = False
                continue

            except Exception as e:
                print(f"[ERROR] Unexpected error fetching {anyo}-{mes:02d}: {type(e).__name__}: {e}")
                continue

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
    print("  ITV SCRAPER - Optimizado con API REST")
    print("="*70)

    scraper = ITVScraper(license_plate=license_plate)

    print(f"Estación: {scraper.station_code}")
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
