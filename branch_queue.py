"""Branch Queue — gestor de colas de atención por servicio para una sucursal bancaria.

Cada servicio (``deposito``, ``retiro``, ``gestion_cuenta``) tiene su propia cola
FIFO implementada con ``collections.deque``. Los números de ticket son globales y
secuenciales para toda la sucursal.

Responsabilidades:
    - ``Ticket``: representa un ticket emitido (dato inmutable).
    - ``BranchQueue``: lógica de negocio (colas, contador y operaciones).
    - ``run_cli`` y funciones auxiliares: interacción con el usuario por terminal.

Solo utiliza la biblioteca estándar de Python.
"""

from collections import deque
from dataclasses import dataclass
from datetime import datetime

SERVICE_TYPES = ("deposito", "retiro", "gestion_cuenta")

SERVICE_LABELS = {
    "deposito": "Depósito",
    "retiro": "Retiro",
    "gestion_cuenta": "Gestión de cuenta",
}

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


# ---------------------------------------------------------------------------
# Excepciones del dominio
# ---------------------------------------------------------------------------

class BranchQueueError(Exception):
    """Error base de Branch Queue."""


class InvalidServiceError(BranchQueueError, ValueError):
    """El tipo de servicio no pertenece a los servicios permitidos."""


class InvalidClientNameError(BranchQueueError, ValueError):
    """El nombre del cliente está vacío o no es texto."""


class EmptyQueueError(BranchQueueError, LookupError):
    """Se intentó consultar o atender una cola sin clientes."""


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Ticket:
    """Ticket individual emitido a un cliente.

    Es inmutable (``frozen=True``): una vez emitido, sus datos no cambian.
    """

    number: int
    client_name: str
    service_type: str
    issued_at: datetime


class BranchQueue:
    """Gestiona tres colas FIFO independientes y un contador global de tickets.

    Estructura interna: ``dict[str, deque[Ticket]]``, una ``deque`` por servicio.
    """

    def __init__(self) -> None:
        self._queues: dict[str, deque[Ticket]] = {
            service: deque() for service in SERVICE_TYPES
        }
        self._counter = 0

    # -- Validaciones -------------------------------------------------------

    def _get_queue(self, service_type: str) -> deque:
        """Devuelve la cola del servicio o lanza ``InvalidServiceError``."""
        if not isinstance(service_type, str) or service_type not in self._queues:
            allowed = ", ".join(SERVICE_TYPES)
            raise InvalidServiceError(
                f"Servicio inválido: {service_type!r}. Servicios permitidos: {allowed}."
            )
        return self._queues[service_type]

    @staticmethod
    def _validate_client_name(client_name: str) -> str:
        """Devuelve el nombre sin espacios exteriores o lanza ``InvalidClientNameError``."""
        if not isinstance(client_name, str) or not client_name.strip():
            raise InvalidClientNameError(
                "El nombre del cliente no puede estar vacío ni contener solo espacios."
            )
        return client_name.strip()

    # -- Operaciones ----------------------------------------------------------

    def issue_ticket(self, client_name: str, service_type: str) -> Ticket:
        """Emite un ticket y lo añade al final de la cola de su servicio. O(1).

        Las validaciones se hacen ANTES de incrementar el contador, de modo que
        una entrada inválida no consume ningún número de ticket.
        """
        name = self._validate_client_name(client_name)
        queue = self._get_queue(service_type)

        self._counter += 1
        ticket = Ticket(
            number=self._counter,
            client_name=name,
            service_type=service_type,
            issued_at=datetime.now(),
        )
        queue.append(ticket)
        return ticket

    def call_next(self, service_type: str) -> Ticket:
        """Retira y devuelve el primer ticket de la cola del servicio. O(1).

        Solo accede a la cola del servicio indicado; nunca recorre las demás.
        """
        queue = self._get_queue(service_type)
        if not queue:
            raise EmptyQueueError(
                f"No hay clientes en espera para el servicio {service_type!r}."
            )
        return queue.popleft()

    def peek_next(self, service_type: str) -> Ticket:
        """Devuelve el primer ticket de la cola sin retirarlo. O(1)."""
        queue = self._get_queue(service_type)
        if not queue:
            raise EmptyQueueError(
                f"No hay clientes en espera para el servicio {service_type!r}."
            )
        return queue[0]

    def list_waiting(self) -> dict[str, list[Ticket]]:
        """Devuelve una copia de los tickets pendientes por servicio, en orden FIFO.

        Construir las listas es O(n) en el número total de clientes en espera.
        Las colas originales no se modifican.
        """
        return {service: list(queue) for service, queue in self._queues.items()}

    def stats(self) -> dict[str, int]:
        """Devuelve el número de clientes pendientes por servicio y el total.

        Usa ``len()`` sobre cada ``deque`` (O(1)); con 3 servicios fijos, el
        coste no depende del número de clientes.
        """
        result = {service: len(queue) for service, queue in self._queues.items()}
        result["total"] = sum(result.values())
        return result

    @property
    def last_issued_number(self) -> int:
        """Último número de ticket emitido (0 si aún no se ha emitido ninguno)."""
        return self._counter


# ---------------------------------------------------------------------------
# Interfaz de línea de comandos (CLI)
# ---------------------------------------------------------------------------

MENU = """
========== BRANCH QUEUE ==========
1. Emitir nuevo ticket
2. Llamar al siguiente cliente
3. Consultar siguiente cliente (sin retirarlo)
4. Mostrar clientes en espera
5. Mostrar estadísticas
6. Salir
=================================="""


def format_ticket(ticket: Ticket) -> str:
    """Representación legible de un ticket para la terminal."""
    return (
        f"Ticket #{ticket.number} | {ticket.client_name} | "
        f"{SERVICE_LABELS[ticket.service_type]} | "
        f"emitido {ticket.issued_at.strftime(DATETIME_FORMAT)}"
    )


def parse_service(raw: str) -> str:
    """Convierte la entrada del usuario (número 1-3 o nombre) en un servicio.

    No valida contra la cola: si el texto no corresponde a ningún servicio,
    se devuelve tal cual y ``BranchQueue`` lanzará ``InvalidServiceError``.
    """
    value = raw.strip().lower()
    if value.isdigit():
        index = int(value) - 1
        if 0 <= index < len(SERVICE_TYPES):
            return SERVICE_TYPES[index]
    return value


def ask_service(input_func) -> str:
    options = "  ".join(
        f"{i}) {service}" for i, service in enumerate(SERVICE_TYPES, start=1)
    )
    return parse_service(input_func(f"Servicio [{options}]: "))


def run_cli(queue=None, input_func=input, print_func=print) -> None:
    """Bucle principal del menú. ``input_func``/``print_func`` permiten probarlo."""
    queue = queue if queue is not None else BranchQueue()

    while True:
        print_func(MENU)
        try:
            raw_option = input_func("Elige una opción (1-6): ")
        except (EOFError, KeyboardInterrupt):
            print_func("\nSaliendo de Branch Queue. ¡Hasta luego!")
            return

        try:
            option = int(raw_option.strip())
        except ValueError:
            print_func(f"Opción inválida: {raw_option!r}. Introduce un número del 1 al 6.")
            continue

        try:
            if option == 1:
                name = input_func("Nombre del cliente: ")
                service = ask_service(input_func)
                ticket = queue.issue_ticket(name, service)
                print_func(f"Ticket emitido -> {format_ticket(ticket)}")

            elif option == 2:
                service = ask_service(input_func)
                ticket = queue.call_next(service)
                print_func(f"Atendiendo -> {format_ticket(ticket)}")

            elif option == 3:
                service = ask_service(input_func)
                ticket = queue.peek_next(service)
                print_func(f"Siguiente en espera -> {format_ticket(ticket)}")

            elif option == 4:
                for service, tickets in queue.list_waiting().items():
                    print_func(f"\n[{SERVICE_LABELS[service]}] ({len(tickets)} en espera)")
                    if not tickets:
                        print_func("  (sin clientes en espera)")
                    for ticket in tickets:
                        print_func(f"  {format_ticket(ticket)}")

            elif option == 5:
                stats = queue.stats()
                print_func("\nEstadísticas de clientes en espera:")
                for service in SERVICE_TYPES:
                    print_func(f"  {SERVICE_LABELS[service]:<18} {stats[service]}")
                print_func(f"  {'Total':<18} {stats['total']}")

            elif option == 6:
                print_func("Saliendo de Branch Queue. ¡Hasta luego!")
                return

            else:
                print_func(f"Opción inválida: {option}. Introduce un número del 1 al 6.")

        except BranchQueueError as error:
            print_func(f"Error: {error}")
        except (EOFError, KeyboardInterrupt):
            print_func("\nOperación cancelada. Saliendo de Branch Queue.")
            return


if __name__ == "__main__":
    run_cli()
