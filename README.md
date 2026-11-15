# Branch Queue — Gestor de Cola por Servicio

Gestor de colas de atención al cliente para una sucursal bancaria, escrito en Python 3 con la biblioteca estándar. Gestiona tres servicios, cada uno con su propia cola FIFO, y numera los tickets de forma global y secuencial.

## 1. Problema que resuelve

En una sucursal, los clientes de depósitos, retiros y gestión de cuenta los atienden agentes distintos. Si todos esperan en una única lista, el agente de depósitos tiene que recorrerla para encontrar a «su» siguiente cliente. Branch Queue da a cada servicio su propia cola:

- Cada cliente recibe un **número de ticket único y global** (1, 2, 3…), sea cual sea el servicio.
- Dentro de cada servicio se respeta estrictamente el **orden de llegada** (FIFO: *First In, First Out*).
- Atender a un cliente de un servicio **no afecta** a las otras colas.

## 2. Estructura de archivos

```
branch-queue/
├── branch_queue.py        # Modelo (Ticket, BranchQueue), excepciones y CLI
├── test_branch_queue.py   # Pruebas unitarias con unittest
├── README.md              # Esta documentación
└── .gitignore
```

## 3. Requisitos previos

- Python 3.9 o superior (probado con Python 3.14.6).
- Nada más: solo se usa la biblioteca estándar (`collections`, `dataclasses`, `datetime`, `unittest`). No hay `requirements.txt` porque no hay dependencias externas.

## 4. Cómo ejecutar el programa

```bash
python branch_queue.py
```

El módulo también se puede importar sin que se abra el menú, gracias al bloque `if __name__ == "__main__":`:

```python
from branch_queue import BranchQueue

queue = BranchQueue()
ticket = queue.issue_ticket("Ana", "deposito")
print(ticket.number)                 # 1
print(queue.call_next("deposito"))   # Ticket(number=1, client_name='Ana', ...)
```

## 5. Opciones del menú

| Opción | Acción | Qué pide |
|---|---|---|
| 1 | Emitir un nuevo ticket | Nombre del cliente y servicio |
| 2 | Llamar al siguiente cliente (lo retira de la cola) | Servicio |
| 3 | Consultar el siguiente cliente sin retirarlo | Servicio |
| 4 | Mostrar los clientes en espera, agrupados por servicio | — |
| 5 | Mostrar estadísticas (por servicio y total) | — |
| 6 | Salir | — |

El servicio se puede indicar por número (`1`, `2`, `3`) o por nombre (`deposito`, `retiro`, `gestion_cuenta`).

Las entradas incorrectas no cierran el programa: una opción no numérica o fuera de rango, un servicio inexistente, un nombre vacío o una cola vacía muestran un mensaje y el menú vuelve a aparecer. `Ctrl+C` o el fin de la entrada (`Ctrl+Z`/`Ctrl+D`) cierran el programa limpiamente.

## 6. Ejemplo de funcionamiento

Salida real, resumida (el menú se repite entre operaciones):

```
Elige una opción (1-6): Opción inválida: 'x'. Introduce un número del 1 al 6.
Ticket emitido -> Ticket #1 | Ana | Depósito | emitido 2026-11-15 22:55:33
Ticket emitido -> Ticket #2 | Bruno | Retiro | emitido 2026-11-15 22:55:33
Ticket emitido -> Ticket #3 | Carla | Gestión de cuenta | emitido 2026-11-15 22:55:33
Ticket emitido -> Ticket #4 | David | Depósito | emitido 2026-11-15 22:55:33
Siguiente en espera -> Ticket #1 | Ana | Depósito | emitido 2026-11-15 22:55:33
Atendiendo -> Ticket #1 | Ana | Depósito | emitido 2026-11-15 22:55:33
Atendiendo -> Ticket #2 | Bruno | Retiro | emitido 2026-11-15 22:55:33
Error: No hay clientes en espera para el servicio 'retiro'.

[Depósito] (1 en espera)
  Ticket #4 | David | Depósito | emitido 2026-11-15 22:55:33

[Retiro] (0 en espera)
  (sin clientes en espera)

[Gestión de cuenta] (1 en espera)
  Ticket #3 | Carla | Gestión de cuenta | emitido 2026-11-15 22:55:33

Estadísticas de clientes en espera:
  Depósito           1
  Retiro             0
  Gestión de cuenta  1
  Total              2
```

## 7. Arquitectura: tres colas independientes

```
            BranchQueue
            ├── _counter: int  (global, empieza en 0)
            └── _queues: dict[str, deque[Ticket]]
                 ├── "deposito"       -> deque([#1 Ana, #4 David])
                 ├── "retiro"         -> deque([#2 Bruno])
                 └── "gestion_cuenta" -> deque([#3 Carla])
```

Las responsabilidades están separadas:

- **`Ticket`** (`dataclass` inmutable): guarda `number`, `client_name`, `service_type` e `issued_at`.
- **`BranchQueue`**: lógica de negocio. Valida, numera, encola y desencola. No lee ni escribe en la terminal.
- **CLI** (`run_cli`, `format_ticket`, `parse_service`): pide datos al usuario, llama a `BranchQueue` y muestra resultados o errores.

Operaciones de `BranchQueue`:

| Método | Qué hace |
|---|---|
| `issue_ticket(client_name, service_type)` | Valida, incrementa el contador, crea el `Ticket` con `datetime.now()` y lo añade con `append()` |
| `call_next(service_type)` | Retira y devuelve el primero con `popleft()` |
| `peek_next(service_type)` | Devuelve el primero (`queue[0]`) sin retirarlo |
| `list_waiting()` | Devuelve `{servicio: [tickets...]}` con copias de las colas, en orden FIFO |
| `stats()` | Devuelve `{servicio: len(cola), ..., "total": suma}` |

Errores controlados (todos heredan de `BranchQueueError`):

- `InvalidServiceError`: el servicio no es uno de los tres permitidos.
- `InvalidClientNameError`: el nombre está vacío o solo tiene espacios.
- `EmptyQueueError`: se llama a `call_next()` o `peek_next()` sobre una cola vacía.

Las validaciones se hacen **antes** de incrementar el contador, así que una entrada inválida no consume ningún número de ticket.

## 8. Por qué `collections.deque`

`deque` (*double-ended queue*) está pensada para añadir y quitar elementos por los dos extremos en O(1).

Una `list` de Python es un array contiguo. `list.pop(0)` obliga a desplazar todos los elementos restantes una posición, lo que cuesta O(n). Con `deque.popleft()` no se desplaza nada.

## 9. Complejidad algorítmica

*n* = clientes en espera. El número de servicios es fijo (3), así que recorrer los servicios cuenta como coste constante.

| Operación | Tres `deque` por servicio | Una lista compartida |
|---|---|---|
| Emitir ticket (`issue_ticket`) | O(1) | O(1) amortizado (`append`) |
| Llamar siguiente (`call_next`) | O(1) (`popleft`) | O(n): buscar el primero del servicio y eliminarlo desplazando el resto |
| Consultar siguiente (`peek_next`) | O(1) (`queue[0]`) | O(n) en el peor caso: buscar el primero del servicio |
| Estadísticas (`stats`) | O(3) = O(1): tres `len()` | O(n): recorrer la lista para agrupar |
| Listado completo (`list_waiting`) | O(n) | O(n) |

Hay que separar dos costes. **Desencolar** un cliente cuesta O(1). **Construir el listado completo** de espera cuesta O(n) en cualquier estructura, porque hay que copiar cada ticket. Por eso `list_waiting()` es O(n) aunque las colas sean `deque`.

## 10. Concurrencia y sincronización (explicación conceptual)

El programa es de un solo hilo y **no implementa** concurrencia. Aun así, conviene entender qué pasaría en un sistema real con varios agentes.

Supón que dos agentes de depósitos llaman a `call_next("deposito")` a la vez. La operación crítica tiene tres pasos:

1. Comprobar la cola y obtener el primer ticket.
2. Retirarlo con `popleft()`.
3. Devolverlo al agente.

Si estos pasos se intercalan entre dos hilos, pueden ocurrir dos cosas:

- Ambos agentes «ven» al mismo cliente (paso 1) antes de que ninguno lo retire, así que **los dos llaman a la misma persona**.
- Los dos comprueban que la cola no está vacía cuando solo queda un cliente. Uno lo retira y el otro ejecuta `popleft()` sobre una cola vacía, lo que produce `IndexError`.

En CPython, cada llamada individual a `deque.append()` o `deque.popleft()` es *thread-safe*. Pero `deque` **no ofrece transacciones compuestas**: la secuencia «comprobar si está vacía y después extraer» no es atómica. La solución es que la sección crítica completa la ejecute un solo hilo cada vez, por ejemplo con `threading.Lock`:

```python
import threading

class ConcurrentBranchQueue(BranchQueue):
    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()

    def call_next(self, service_type):
        with self._lock:          # nadie más entra hasta salir del bloque
            return super().call_next(service_type)
```

`issue_ticket()` necesitaría la misma protección, porque `self._counter += 1` tampoco es atómico: dos hilos podrían leer el mismo valor y emitir dos tickets con el mismo número. Para producción también se podría usar `queue.Queue`, que incluye su propio bloqueo, o una cola en una base de datos con transacciones.

## 11. Ejecución de las pruebas

```bash
python -m unittest -v
python -m py_compile branch_queue.py
```

`test_branch_queue.py` contiene 12 pruebas:

| # | Prueba | Verifica |
|---|---|---|
| 1 | `test_global_sequential_numbering` | Numeración global 1, 2, 3, 4 entre servicios distintos |
| 2 | `test_fifo_within_service` | Orden FIFO dentro de un servicio |
| 3 | `test_calling_one_service_does_not_affect_others` | Independencia de las colas |
| 4 | `test_peek_does_not_remove` | `peek_next()` no retira el ticket |
| 5 | `test_list_waiting_all_services_fifo_and_non_destructive` | Listado completo, ordenado, y sin efectos sobre las colas |
| 6 | `test_stats_counts_and_total` | Recuentos individuales y total |
| 7 | `test_empty_queue_raises_descriptive_errors` | `EmptyQueueError` en colas vacías |
| 8 | `test_invalid_service_rejected_without_consuming_number` | Servicio inválido rechazado sin consumir número |
| 9 | `test_invalid_client_names` | Nombres vacíos o solo con espacios |
| 10 | `test_initial_state` | Tres colas vacías y estadísticas a cero al inicio |
| — | `CliTests` (2 pruebas) | La CLI no se cae ante entradas incorrectas y sale limpiamente |

**Fuera del alcance de las pruebas:** el comportamiento con varios hilos. Las pruebas son secuenciales y no demuestran ni la presencia ni la ausencia de condiciones de carrera.

## 12. Limitaciones

- Sin persistencia: al cerrar el programa se pierden las colas y el contador.
- Un solo proceso y un solo hilo, sin sincronización (ver sección 10).
- Sin autenticación ni asignación automática de agentes.
- Los tres servicios están fijados en el código (`SERVICE_TYPES`).
