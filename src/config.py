"""Configuración compartida. Se puede sobreescribir con variables de entorno."""
import os

# User-Agent exigido por data.sec.gov (nombre + mail de contacto).
SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "Criteria Research alanfeld73@gmail.com")
