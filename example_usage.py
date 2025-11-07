#!/usr/bin/env python3
"""
Ejemplo de uso avanzado del scraper de ITV Argentona
"""

from itv_scraper import ITVArgentona
import sys


def example_basic():
    """Ejemplo básico de uso"""
    print("=== Ejemplo Básico ===\n")

    scraper = ITVArgentona(
        license_plate="1234ABC",
        headless=False,  # Mostrar navegador
        take_screenshots=True
    )

    appointments = scraper.search_appointments()

    if appointments:
        print(f"\n✓ Se encontraron {len(appointments)} citas")
        for apt in appointments:
            print(f"  - {apt}")
    else:
        print("\n⚠️  No se encontraron citas")


def example_multiple_plates():
    """Ejemplo de búsqueda para múltiples matrículas"""
    print("=== Búsqueda para Múltiples Matrículas ===\n")

    plates = ["1234ABC", "5678DEF", "9012GHI"]

    for plate in plates:
        print(f"\n🚗 Buscando para {plate}...")

        scraper = ITVArgentona(
            license_plate=plate,
            headless=True,
            take_screenshots=False  # Desactivar capturas para búsquedas masivas
        )

        appointments = scraper.search_appointments()

        if appointments:
            print(f"✓ Citas disponibles para {plate}: {len(appointments)}")
        else:
            print(f"⚠️  No hay citas para {plate}")


def example_with_notification():
    """Ejemplo con notificación cuando se encuentran citas"""
    print("=== Ejemplo con Notificación ===\n")

    scraper = ITVArgentona(
        license_plate="1234ABC",
        headless=True,
        take_screenshots=True
    )

    appointments = scraper.search_appointments()

    if appointments:
        # Aquí podrías enviar un email, telegram, etc.
        print("\n🔔 ¡NOTIFICACIÓN!")
        print(f"Se encontraron {len(appointments)} citas disponibles")
        print("(Aquí podrías integrar envío de email/telegram/etc)")

        # Ejemplo de estructura para enviar notificación
        notification_data = {
            'title': 'Citas disponibles en ITV Argentona',
            'message': f'Se encontraron {len(appointments)} citas para tu vehículo',
            'appointments': appointments
        }
        print(f"\nDatos para notificación: {notification_data}")
    else:
        print("\n⚠️  No hay citas disponibles aún")


def main():
    """Función principal con menú de ejemplos"""
    print("╔════════════════════════════════════════════════╗")
    print("║   Ejemplos de Uso - ITV Argentona Scraper      ║")
    print("╚════════════════════════════════════════════════╝\n")

    print("Selecciona un ejemplo:")
    print("1. Ejemplo básico (con navegador visible)")
    print("2. Búsqueda para múltiples matrículas")
    print("3. Ejemplo con notificación")
    print("0. Salir\n")

    choice = input("Opción: ").strip()

    if choice == "1":
        example_basic()
    elif choice == "2":
        example_multiple_plates()
    elif choice == "3":
        example_with_notification()
    elif choice == "0":
        print("👋 Hasta luego!")
        sys.exit(0)
    else:
        print("❌ Opción no válida")


if __name__ == "__main__":
    main()
