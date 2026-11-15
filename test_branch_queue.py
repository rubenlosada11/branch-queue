"""Pruebas unitarias de Branch Queue (solo biblioteca estándar: unittest)."""

import unittest
from datetime import datetime

from branch_queue import (
    SERVICE_TYPES,
    BranchQueue,
    EmptyQueueError,
    InvalidClientNameError,
    InvalidServiceError,
    Ticket,
    run_cli,
)


class BranchQueueTests(unittest.TestCase):
    def setUp(self):
        self.queue = BranchQueue()

    # Prueba 1 — Numeración global
    def test_global_sequential_numbering(self):
        t1 = self.queue.issue_ticket("Cliente A", "deposito")
        t2 = self.queue.issue_ticket("Cliente B", "retiro")
        t3 = self.queue.issue_ticket("Cliente C", "gestion_cuenta")
        t4 = self.queue.issue_ticket("Cliente D", "deposito")

        self.assertEqual([t.number for t in (t1, t2, t3, t4)], [1, 2, 3, 4])
        self.assertIsInstance(t1, Ticket)
        self.assertEqual(t1.client_name, "Cliente A")
        self.assertEqual(t1.service_type, "deposito")
        self.assertIsInstance(t1.issued_at, datetime)

    # Prueba 2 — FIFO por servicio
    def test_fifo_within_service(self):
        first = self.queue.issue_ticket("Ana", "deposito")
        self.queue.issue_ticket("Bruno", "retiro")
        second = self.queue.issue_ticket("Carla", "deposito")

        self.assertEqual(self.queue.call_next("deposito"), first)
        self.assertEqual(self.queue.call_next("deposito"), second)

    # Prueba 3 — Independencia entre colas
    def test_calling_one_service_does_not_affect_others(self):
        self.queue.issue_ticket("Ana", "deposito")
        retiro = self.queue.issue_ticket("Bruno", "retiro")
        gestion = self.queue.issue_ticket("Carla", "gestion_cuenta")

        self.queue.call_next("deposito")

        waiting = self.queue.list_waiting()
        self.assertEqual(waiting["deposito"], [])
        self.assertEqual(waiting["retiro"], [retiro])
        self.assertEqual(waiting["gestion_cuenta"], [gestion])

    # Prueba 4 — Peek no retira
    def test_peek_does_not_remove(self):
        ticket = self.queue.issue_ticket("Ana", "retiro")

        self.assertEqual(self.queue.peek_next("retiro"), ticket)
        self.assertEqual(self.queue.peek_next("retiro"), ticket)
        self.assertEqual(self.queue.stats()["retiro"], 1)
        self.assertEqual(self.queue.call_next("retiro"), ticket)

    # Prueba 5 — Listado
    def test_list_waiting_all_services_fifo_and_non_destructive(self):
        a = self.queue.issue_ticket("Ana", "deposito")
        b = self.queue.issue_ticket("Bruno", "deposito")
        c = self.queue.issue_ticket("Carla", "retiro")

        waiting = self.queue.list_waiting()
        self.assertEqual(set(waiting), set(SERVICE_TYPES))
        self.assertEqual(waiting["deposito"], [a, b])
        self.assertEqual(waiting["retiro"], [c])
        self.assertEqual(waiting["gestion_cuenta"], [])

        # Modificar el resultado no debe alterar las colas internas.
        waiting["deposito"].clear()
        self.assertEqual(self.queue.stats()["deposito"], 2)
        self.assertEqual(self.queue.call_next("deposito"), a)

    # Prueba 6 — Estadísticas
    def test_stats_counts_and_total(self):
        for name in ("A", "B", "C"):
            self.queue.issue_ticket(name, "deposito")
        for name in ("D", "E"):
            self.queue.issue_ticket(name, "retiro")
        self.queue.issue_ticket("F", "gestion_cuenta")

        self.assertEqual(
            self.queue.stats(),
            {"deposito": 3, "retiro": 2, "gestion_cuenta": 1, "total": 6},
        )

        self.queue.call_next("deposito")
        self.assertEqual(self.queue.stats()["deposito"], 2)
        self.assertEqual(self.queue.stats()["total"], 5)

    # Prueba 7 — Cola vacía
    def test_empty_queue_raises_descriptive_errors(self):
        with self.assertRaisesRegex(EmptyQueueError, "No hay clientes.*deposito"):
            self.queue.call_next("deposito")
        with self.assertRaisesRegex(EmptyQueueError, "No hay clientes.*retiro"):
            self.queue.peek_next("retiro")

        # Una cola que se vacía tras atender vuelve a producir el error.
        self.queue.issue_ticket("Ana", "gestion_cuenta")
        self.queue.call_next("gestion_cuenta")
        with self.assertRaises(EmptyQueueError):
            self.queue.call_next("gestion_cuenta")

    # Prueba 8 — Servicio inválido
    def test_invalid_service_rejected_without_consuming_number(self):
        with self.assertRaisesRegex(InvalidServiceError, "prestamo"):
            self.queue.issue_ticket("Ana", "prestamo")
        for bad in ("", "Deposito", None, 1):
            with self.assertRaises(InvalidServiceError):
                self.queue.issue_ticket("Ana", bad)
        with self.assertRaises(InvalidServiceError):
            self.queue.call_next("prestamo")
        with self.assertRaises(InvalidServiceError):
            self.queue.peek_next("prestamo")

        self.assertEqual(self.queue.last_issued_number, 0)
        self.assertEqual(self.queue.issue_ticket("Ana", "deposito").number, 1)

    # Prueba 9 — Datos inválidos
    def test_invalid_client_names(self):
        for bad in ("", "   ", "\t\n", None):
            with self.assertRaises(InvalidClientNameError):
                self.queue.issue_ticket(bad, "deposito")

        self.assertEqual(self.queue.last_issued_number, 0)
        self.assertEqual(self.queue.stats()["total"], 0)
        # Los espacios exteriores de un nombre válido se eliminan.
        self.assertEqual(self.queue.issue_ticket("  Ana  ", "retiro").client_name, "Ana")

    # Prueba 10 — Estado inicial
    def test_initial_state(self):
        waiting = self.queue.list_waiting()
        self.assertEqual(set(waiting), {"deposito", "retiro", "gestion_cuenta"})
        self.assertTrue(all(tickets == [] for tickets in waiting.values()))
        self.assertEqual(
            self.queue.stats(),
            {"deposito": 0, "retiro": 0, "gestion_cuenta": 0, "total": 0},
        )
        self.assertEqual(self.queue.last_issued_number, 0)


class CliTests(unittest.TestCase):
    """Verifica que la CLI no se cae ante entradas incorrectas."""

    def run_session(self, inputs, queue=None):
        answers = iter(inputs)
        output = []

        def fake_input(_prompt=""):
            try:
                return next(answers)
            except StopIteration:
                raise EOFError

        run_cli(queue or BranchQueue(), fake_input, lambda *a: output.append(" ".join(map(str, a))))
        return "\n".join(output)

    def test_full_session_with_invalid_inputs(self):
        queue = BranchQueue()
        out = self.run_session(
            [
                "abc",                 # opción no numérica
                "9",                   # opción fuera de rango
                "1", "   ", "1",       # nombre vacío
                "1", "Ana", "prestamo",  # servicio inexistente
                "1", "Ana", "1",       # emisión correcta (deposito por número)
                "1", "Bruno", "retiro",  # emisión correcta (por nombre)
                "3", "1",              # peek deposito
                "2", "3",              # cola vacía gestion_cuenta
                "4", "5",
                "2", "deposito",
                "6",
            ],
            queue,
        )
        self.assertIn("Opción inválida: 'abc'", out)
        self.assertIn("Opción inválida: 9", out)
        self.assertIn("no puede estar vacío", out)
        self.assertIn("Servicio inválido: 'prestamo'", out)
        self.assertIn("Ticket emitido -> Ticket #1 | Ana | Depósito", out)
        self.assertIn("Siguiente en espera -> Ticket #1 | Ana", out)
        self.assertIn("No hay clientes en espera para el servicio 'gestion_cuenta'", out)
        self.assertIn("(sin clientes en espera)", out)
        self.assertIn("Atendiendo -> Ticket #1 | Ana", out)
        self.assertIn("Saliendo de Branch Queue", out)
        self.assertEqual(queue.stats()["total"], 1)

    def test_end_of_input_exits_cleanly(self):
        out = self.run_session([])
        self.assertIn("Saliendo de Branch Queue", out)


if __name__ == "__main__":
    unittest.main()
