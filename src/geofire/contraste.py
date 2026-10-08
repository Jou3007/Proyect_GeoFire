"""Paletas y relacion de contraste WCAG 2.x (RNF-05: legibilidad bajo luz solar directa)."""


def _canal(c):
    c = c / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminancia(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _canal(r) + 0.7152 * _canal(g) + 0.0722 * _canal(b)


def ratio(color_a, color_b):
    """Relacion de contraste entre dos colores (1 a 21). AA exige 4.5 para texto normal; AAA, 7."""
    la, lb = sorted((luminancia(color_a), luminancia(color_b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# (primer plano, fondo) que se usan en pantalla
PARES_NORMAL = {
    "texto": ("#1b2a22", "#f3f6f1"),
    "texto secundario": ("#55645c", "#f3f6f1"),
    "texto secundario en tarjeta": ("#55645c", "#ffffff"),
    "tarjeta verde": ("#ffffff", "#0f6b4f"),
    "nota en tarjeta verde": ("#e3f2ea", "#0f6b4f"),
    "enlace/etiqueta verde": ("#0f6b4f", "#e6f2ea"),
}
PARES_ALTO_CONTRASTE = {
    "texto": ("#000000", "#ffffff"),
    "texto secundario": ("#1a1a1a", "#ffffff"),
    "tarjeta verde": ("#ffffff", "#003d24"),
    "nota en tarjeta verde": ("#ffffff", "#003d24"),
    "etiqueta critica": ("#ffffff", "#8b0000"),
    "etiqueta alta": ("#ffffff", "#8a3300"),
    "etiqueta media": ("#000000", "#ffd400"),
    "etiqueta baja": ("#ffffff", "#005a26"),
    "enlace": ("#003d24", "#ffffff"),
}
