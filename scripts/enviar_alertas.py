"""Envia por correo las alertas Alto/Critico nuevas.
Uso: python scripts/enviar_alertas.py [--dry-run] [--incluir-historicas]
"""
import sys

from geofire.correo import enviar_alertas

enviar_alertas(dry_run="--dry-run" in sys.argv, incluir_historicas="--incluir-historicas" in sys.argv)
