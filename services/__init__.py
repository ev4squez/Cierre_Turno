"""Capa de servicios (logica de negocio).

Cada modulo expone funciones que reciben/entregan datos planos
(dicts, escalares) y usan ``database.db.get_session()`` para acceder
a la DB. La UI nunca toca SQLAlchemy directamente.
"""