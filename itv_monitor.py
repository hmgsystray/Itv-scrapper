#!/usr/bin/env python3
"""
Monitor continuo para detectar nuevas citas en ITV Argentona
"""

import os
import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dotenv import load_dotenv

from itv_scraper import ITVScraper
from discord_notifier import DiscordNotifier


class ITVMonitor:
    """Monitor continuo para detectar nuevas citas"""

    def __init__(self, license_plate: str, discord_webhook_url: Optional[str] = None,
                 interval_minutes: int = 5, months_ahead: int = 3, days_limit: int = 15):
        """
        Inicializa el monitor

        Args:
            license_plate: Matrícula del vehículo (requerido)
                          NOTA: El servidor valida las matrículas. Usa una real o de prueba.
            discord_webhook_url: URL del webhook de Discord (opcional)
            interval_minutes: Intervalo entre revisiones en minutos
            months_ahead: Meses a consultar hacia adelante
            days_limit: Solo notificar citas dentro de los próximos N días (default: 15)
        """
        self.license_plate = license_plate
        self.interval_minutes = interval_minutes
        self.months_ahead = months_ahead
        self.days_limit = days_limit
        self.state_file = "monitor_state.json"
        self.last_appointments: List[Dict] = []
        self.last_check: Optional[str] = None
        self.scraper: Optional[ITVScraper] = None  # Se inicializa en el primer check y se reutiliza

        # Inicializar notificador
        self.notifier = DiscordNotifier(discord_webhook_url)

    def _load_state(self) -> None:
        """Carga el estado anterior del monitor"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self.last_appointments = state.get('appointments', [])
                    self.last_check = state.get('last_check')
                    print(f"Estado cargado: {len(self.last_appointments)} citas previas")
        except Exception as e:
            print(f"[AVISO] Error al cargar estado: {e}")

    def _save_state(self, appointments: List[Dict]) -> None:
        """
        Guarda el estado actual del monitor

        Args:
            appointments: Lista de citas a guardar
        """
        try:
            state = {
                'appointments': appointments,
                'last_check': datetime.now().isoformat(),
                'license_plate': self.license_plate
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            print(f"Estado guardado: {len(appointments)} citas")
        except Exception as e:
            print(f"[AVISO] Error al guardar estado: {e}")

    def _filter_appointments_by_date(self, appointments: List[Dict]) -> List[Dict]:
        """
        Filtra las citas para quedarse solo con las que están dentro del límite de días

        Args:
            appointments: Lista de todas las citas

        Returns:
            List[Dict]: Lista de citas filtradas
        """
        if not appointments or self.days_limit <= 0:
            return appointments

        today = datetime.now().date()
        limit_date = today + timedelta(days=self.days_limit)

        filtered = []
        for apt in appointments:
            # Parsear fecha de la cita (formato: "2025-11-07")
            apt_date = datetime.strptime(apt['fecha'], '%Y-%m-%d').date()

            # Solo incluir si está dentro del rango
            if today <= apt_date <= limit_date:
                filtered.append(apt)

        return filtered

    def _get_appointments_hash(self, appointments: List[Dict]) -> str:
        """
        Calcula un hash de las citas para detectar cambios

        Args:
            appointments: Lista de citas

        Returns:
            str: Hash MD5 de las citas
        """
        appointments_str = json.dumps(appointments, sort_keys=True)
        return hashlib.md5(appointments_str.encode()).hexdigest()

    def _detect_new_appointments(self, current_appointments: List[Dict]) -> tuple:
        """
        Detecta si hay nuevas citas comparando con el estado anterior
        Solo considera citas dentro del rango de días configurado

        Args:
            current_appointments: Citas actuales (todas)

        Returns:
            tuple: (hay_nuevas, nuevas_citas_en_rango)
        """
        # Filtrar solo citas dentro del rango de días
        current_in_range = self._filter_appointments_by_date(current_appointments)
        previous_in_range = self._filter_appointments_by_date(self.last_appointments)

        if not self.last_appointments and current_in_range:
            # Primera ejecución con citas en rango
            return True, current_in_range

        if not current_in_range:
            return False, []

        # Comparar hashes de citas en rango
        current_hash = self._get_appointments_hash(current_in_range)
        previous_hash = self._get_appointments_hash(previous_in_range)

        if current_hash != previous_hash:
            # Hay cambios, determinar cuáles son nuevas
            previous_set = {apt['fecha_hora'] for apt in previous_in_range}
            new_appointments = [
                apt for apt in current_in_range
                if apt['fecha_hora'] not in previous_set
            ]

            if new_appointments:
                return True, new_appointments
            else:
                # Hay cambios pero no son nuevas citas (se quitaron algunas)
                print("Cambios detectados pero no son nuevas citas en rango")
                return False, []

        return False, []

    def check_once(self, notify_no_appointments: bool = False) -> List[Dict]:
        """
        Realiza una revisión única

        Args:
            notify_no_appointments: Si notificar cuando no hay citas

        Returns:
            List[Dict]: Lista de citas encontradas
        """
        print("\n" + "="*70)
        print(f"Revision iniciada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)

        try:
            # Crear scraper si no existe, o reutilizar el existente
            if not hasattr(self, 'scraper') or self.scraper is None:
                self.scraper = ITVScraper(license_plate=self.license_plate)
                reuse_guid = False
            else:
                reuse_guid = True

            # Buscar citas (reutilizando GUID si es posible)
            appointments = self.scraper.get_available_dates(
                months_ahead=self.months_ahead,
                reuse_guid=reuse_guid
            )

            # Mostrar resumen de citas
            in_range = self._filter_appointments_by_date(appointments)
            print(f"\nCitas encontradas: {len(appointments)} total, {len(in_range)} en próximos {self.days_limit} días")

            # Detectar nuevas citas (solo en rango de días)
            has_new, new_appointments = self._detect_new_appointments(appointments)

            if has_new and new_appointments:
                print(f"\n¡NUEVAS CITAS DETECTADAS EN PRÓXIMOS {self.days_limit} DÍAS! ({len(new_appointments)})")
                print("="*70)
                for i, apt in enumerate(new_appointments[:10], 1):
                    print(f"{i}. {apt['fecha_hora']} - {apt['precio']} EUR")
                if len(new_appointments) > 10:
                    print(f"... y {len(new_appointments) - 10} más")
                print("="*70)

                # Enviar notificación (sin mostrar matrícula)
                self.notifier.send_new_appointments(new_appointments, show_license_plate=False)

                # Guardar estado
                self._save_state(appointments)
                self.last_appointments = appointments

            elif appointments:
                if in_range:
                    print(f"Hay {len(in_range)} citas en próximos {self.days_limit} días (sin cambios)")
                else:
                    print(f"No hay citas en próximos {self.days_limit} días")

                # Solo guardar estado si es la primera vez
                if not self.last_appointments:
                    self._save_state(appointments)
                    self.last_appointments = appointments

            else:
                print("\nNo se encontraron citas disponibles")

                if notify_no_appointments:
                    self.notifier.send_no_appointments()

            self.last_check = datetime.now().isoformat()
            return appointments

        except Exception as e:
            error_msg = f"Error durante la revision: {str(e)}"
            print(f"\n[ERROR] {error_msg}")
            self.notifier.send_error(error_msg)
            return []

    def start(self, notify_start: bool = True) -> None:
        """
        Inicia el monitor continuo

        Args:
            notify_start: Si enviar notificación de inicio
        """
        print("\n" + "="*70)
        print("  MONITOR ITV ARGENTONA INICIADO")
        print("="*70)
        print(f"\nConfiguracion:")
        if self.license_plate:
            print(f"  Matricula: {self.license_plate}")
        else:
            print(f"  Matricula: Aleatoria (generada en cada check)")
        print(f"  Intervalo: {self.interval_minutes} minutos")
        print(f"  Meses a consultar: {self.months_ahead}")

        if self.notifier.terminal_only:
            print(f"  Notificaciones: Solo terminal")
        else:
            print(f"  Notificaciones: Discord [OK]")

        print(f"\nIniciando monitoreo continuo...")
        print(f"Presiona Ctrl+C para detener\n")

        # Cargar estado anterior
        self._load_state()

        # Enviar notificación de inicio
        if notify_start:
            self.notifier.send_monitor_started(
                interval_minutes=self.interval_minutes,
                days_limit=self.days_limit,
                show_license_plate=False  # No mostrar matrícula
            )

        iteration = 0

        try:
            while True:
                iteration += 1
                print(f"\n{'='*70}")
                print(f"Iteracion #{iteration}")

                # Realizar revisión
                self.check_once(notify_no_appointments=False)

                # Esperar hasta la próxima revisión
                wait_seconds = self.interval_minutes * 60
                print(f"\nProxima revision en {self.interval_minutes} minutos...")
                print(f"({datetime.now().strftime('%H:%M:%S')} -> ", end="", flush=True)

                time.sleep(wait_seconds)

                print(f"{datetime.now().strftime('%H:%M:%S')})")

        except KeyboardInterrupt:
            print("\n\nMonitor detenido por el usuario")
            print("Estado guardado correctamente")

            # Cerrar scraper si existe
            if self.scraper:
                self.scraper.close()

            print("\n¡Hasta pronto!")

        except Exception as e:
            print(f"\n[ERROR] Error critico: {str(e)}")
            self.notifier.send_error(f"Monitor detenido por error: {str(e)}")

            # Cerrar scraper si existe
            if self.scraper:
                self.scraper.close()


def main():
    """Función principal"""
    load_dotenv()

    # Obtener configuración
    license_plate = os.getenv("LICENSE_PLATE")
    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL", "")
    interval = int(os.getenv("MONITOR_INTERVAL_MINUTES", "5"))
    days_limit = int(os.getenv("DAYS_LIMIT", "15"))

    # Validar configuración
    if not license_plate:
        print("[ERROR] No se ha configurado LICENSE_PLATE en el archivo .env")
        print("\nPasos:")
        print("1. Copia config.example.env a .env (si aún no lo has hecho)")
        print("2. Edita .env y configura LICENSE_PLATE=TU_MATRICULA")
        print("\nNOTA: El servidor valida las matrículas. Usa tu matrícula real")
        print("      o una de prueba conocida (ej: 6784BDR)")
        return

    # Informar sobre modo de notificación
    if not discord_webhook:
        print("\n[AVISO] Discord webhook no configurado")
        print("Las notificaciones se mostraran solo por terminal")
        print("\nPara recibir notificaciones en Discord:")
        print("1. Ve a los ajustes del canal donde quieres recibir notificaciones")
        print("2. Integraciones -> Webhooks -> Nuevo Webhook")
        print("3. Copia la URL del webhook y añádela al archivo .env")
        print("")

    # Crear y iniciar monitor
    monitor = ITVMonitor(
        license_plate=license_plate,
        discord_webhook_url=discord_webhook if discord_webhook else None,
        interval_minutes=interval,
        days_limit=days_limit
    )

    monitor.start(notify_start=True)


if __name__ == "__main__":
    main()
