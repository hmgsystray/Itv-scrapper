#!/usr/bin/env python3
"""
Monitor continuo para detectar nuevas citas en ITV Argentona
"""

import os
import json
import time
import hashlib
from datetime import datetime
from dotenv import load_dotenv
from itv_scraper import ITVArgentona
from discord_notifier import DiscordNotifier


class ITVMonitor:
    """Monitor continuo para detectar nuevas citas"""

    def __init__(self, license_plate, discord_webhook_url, interval_minutes=5):
        """
        Inicializa el monitor

        Args:
            license_plate (str): Matrícula del vehículo
            discord_webhook_url (str): URL del webhook de Discord
            interval_minutes (int): Intervalo entre revisiones en minutos
        """
        self.license_plate = license_plate
        self.interval_minutes = interval_minutes
        self.state_file = "monitor_state.json"
        self.last_appointments = []
        self.last_check = None

        # Inicializar notificador de Discord
        self.notifier = DiscordNotifier(discord_webhook_url)

    def _load_state(self):
        """Carga el estado anterior del monitor"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self.last_appointments = state.get('appointments', [])
                    self.last_check = state.get('last_check')
                    print(f"📂 Estado cargado: {len(self.last_appointments)} citas previas")
        except Exception as e:
            print(f"⚠️  Error al cargar estado: {e}")

    def _save_state(self, appointments):
        """Guarda el estado actual del monitor"""
        try:
            state = {
                'appointments': appointments,
                'last_check': datetime.now().isoformat(),
                'license_plate': self.license_plate
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            print(f"💾 Estado guardado: {len(appointments)} citas")
        except Exception as e:
            print(f"⚠️  Error al guardar estado: {e}")

    def _get_appointments_hash(self, appointments):
        """
        Calcula un hash de las citas para detectar cambios

        Args:
            appointments (list): Lista de citas

        Returns:
            str: Hash MD5 de las citas
        """
        # Crear una representación string de las citas
        appointments_str = json.dumps(appointments, sort_keys=True)
        return hashlib.md5(appointments_str.encode()).hexdigest()

    def _detect_new_appointments(self, current_appointments):
        """
        Detecta si hay nuevas citas comparando con el estado anterior

        Args:
            current_appointments (list): Citas actuales

        Returns:
            tuple: (hay_nuevas, nuevas_citas)
        """
        if not self.last_appointments and current_appointments:
            # Primera ejecución con citas
            return True, current_appointments

        if not current_appointments:
            return False, []

        # Comparar hashes
        current_hash = self._get_appointments_hash(current_appointments)
        previous_hash = self._get_appointments_hash(self.last_appointments)

        if current_hash != previous_hash:
            # Hay cambios, determinar cuáles son nuevas
            previous_texts = {apt.get('text', '') for apt in self.last_appointments}
            new_appointments = [
                apt for apt in current_appointments
                if apt.get('text', '') not in previous_texts
            ]

            if new_appointments:
                return True, new_appointments
            else:
                # Hay cambios pero no son nuevas citas (quizás se quitaron algunas)
                print("ℹ️  Cambios detectados pero no son nuevas citas")
                return False, []

        return False, []

    def check_once(self, notify_no_appointments=False):
        """
        Realiza una revisión única

        Args:
            notify_no_appointments (bool): Si notificar cuando no hay citas

        Returns:
            list: Lista de citas encontradas
        """
        print("\n" + "="*70)
        print(f"🔍 Revisión iniciada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)

        try:
            # Crear scraper
            scraper = ITVArgentona(
                license_plate=self.license_plate,
                save_html=True
            )

            # Buscar citas
            appointments = scraper.search_appointments()
            scraper.close()

            # Detectar nuevas citas
            has_new, new_appointments = self._detect_new_appointments(appointments)

            if has_new and new_appointments:
                print(f"\n🎉 ¡NUEVAS CITAS DETECTADAS! ({len(new_appointments)})")
                print("="*70)
                for i, apt in enumerate(new_appointments, 1):
                    print(f"{i}. {apt.get('text', 'N/A')}")
                print("="*70)

                # Enviar notificación
                self.notifier.send_new_appointments(new_appointments, self.license_plate)

                # Guardar estado
                self._save_state(appointments)
                self.last_appointments = appointments

            elif appointments:
                print(f"\n✓ Se encontraron {len(appointments)} citas (sin cambios)")

                # Solo guardar estado si es la primera vez
                if not self.last_appointments:
                    self._save_state(appointments)
                    self.last_appointments = appointments

            else:
                print("\nℹ️  No se encontraron citas disponibles")

                if notify_no_appointments:
                    self.notifier.send_no_appointments(self.license_plate)

            self.last_check = datetime.now()
            return appointments

        except Exception as e:
            error_msg = f"Error durante la revisión: {str(e)}"
            print(f"\n❌ {error_msg}")
            self.notifier.send_error(error_msg)
            return []

    def start(self, notify_start=True):
        """
        Inicia el monitor continuo

        Args:
            notify_start (bool): Si enviar notificación de inicio
        """
        print("\n" + "╔" + "="*68 + "╗")
        print("║" + " "*15 + "MONITOR ITV ARGENTONA INICIADO" + " "*23 + "║")
        print("╚" + "="*68 + "╝")
        print(f"\n📋 Configuración:")
        print(f"   • Matrícula: {self.license_plate}")
        print(f"   • Intervalo: {self.interval_minutes} minutos")
        print(f"   • Scraper: requests (ligero y rápido)")

        if self.notifier.terminal_only:
            print(f"   • Notificaciones: Solo terminal 📟")
        else:
            print(f"   • Notificaciones: Discord ✓")

        print(f"\n🚀 Iniciando monitoreo continuo...")
        print(f"   Presiona Ctrl+C para detener\n")

        # Cargar estado anterior
        self._load_state()

        # Enviar notificación de inicio
        if notify_start:
            self.notifier.send_monitor_started(self.license_plate, self.interval_minutes)

        iteration = 0

        try:
            while True:
                iteration += 1
                print(f"\n{'='*70}")
                print(f"Iteración #{iteration}")

                # Realizar revisión
                self.check_once(notify_no_appointments=False)

                # Esperar hasta la próxima revisión
                wait_seconds = self.interval_minutes * 60
                next_check = datetime.now()
                next_check = next_check.replace(second=0, microsecond=0)

                print(f"\n⏰ Próxima revisión en {self.interval_minutes} minutos...")
                print(f"   ({datetime.now().strftime('%H:%M:%S')} → ", end="")

                time.sleep(wait_seconds)

                print(f"{datetime.now().strftime('%H:%M:%S')})")

        except KeyboardInterrupt:
            print("\n\n🛑 Monitor detenido por el usuario")
            print("💾 Estado guardado correctamente")
            print("\n👋 ¡Hasta pronto!")

        except Exception as e:
            print(f"\n❌ Error crítico: {str(e)}")
            self.notifier.send_error(f"Monitor detenido por error: {str(e)}")


def main():
    """Función principal"""
    load_dotenv()

    # Obtener configuración
    license_plate = os.getenv("LICENSE_PLATE")
    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL", "")
    interval = int(os.getenv("MONITOR_INTERVAL_MINUTES", "5"))

    # Validar configuración
    if not license_plate:
        print("❌ Error: No se ha configurado LICENSE_PLATE en el archivo .env")
        return

    # Informar sobre modo de notificación
    if not discord_webhook:
        print("\n⚠️  Discord webhook no configurado")
        print("📋 Las notificaciones se mostrarán solo por terminal")
        print("💡 Para recibir notificaciones en Discord:")
        print("   1. Ve a los ajustes del canal donde quieres recibir notificaciones")
        print("   2. Integraciones → Webhooks → Nuevo Webhook")
        print("   3. Copia la URL del webhook y añádela al archivo .env")
        print("")

    # Crear y iniciar monitor
    monitor = ITVMonitor(
        license_plate=license_plate,
        discord_webhook_url=discord_webhook if discord_webhook else None,
        interval_minutes=interval
    )

    monitor.start(notify_start=True)


if __name__ == "__main__":
    main()
