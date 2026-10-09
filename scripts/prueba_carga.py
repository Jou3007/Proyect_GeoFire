"""Prueba de carga del visor (cap. 12.12): N usuarios inician sesion y abren el Mapa visor a la vez, con un navegador real.
Mide, por usuario, el tiempo hasta ver la aplicacion tras iniciar sesion y hasta que el mapa esta dibujado.

Uso (dentro de la red de Docker, con la app arriba):
  GEOFIRE_URL=http://web:8501 GEOFIRE_EMAIL=... GEOFIRE_PASSWORD=... python scripts/prueba_carga.py 10 25 50
Requiere: pip install playwright && playwright install --with-deps chromium
"""
import asyncio
import json
import os
import statistics
import sys
import time

from playwright.async_api import async_playwright

URL = os.getenv("GEOFIRE_URL", "http://web:8501")
EMAIL, CLAVE = os.environ["GEOFIRE_EMAIL"], os.environ["GEOFIRE_PASSWORD"]
SALIDA = os.getenv("GEOFIRE_SALIDA", "/tmp/prueba_carga.json")
ESPERA_MS = 120_000


async def usuario(browser, n, resultados):
    ctx = await browser.new_context(viewport={"width": 1366, "height": 900})
    page = await ctx.new_page()
    t0 = time.time()
    try:
        await page.goto(URL, timeout=ESPERA_MS)
        await page.locator("input[type=password]").wait_for(timeout=ESPERA_MS)
        await page.get_by_label("Correo institucional").fill(EMAIL)
        await page.locator("input[type=password]").fill(CLAVE)
        await page.keyboard.press("Enter")
        await page.get_by_role("link", name="Mapa visor").wait_for(timeout=ESPERA_MS)
        t_login = time.time() - t0
        t1 = time.time()
        await page.get_by_role("link", name="Mapa visor").click()
        await page.frame_locator("iframe").first.locator(".leaflet-container").wait_for(timeout=ESPERA_MS)
        resultados.append({"ok": True, "login_s": round(t_login, 2), "mapa_s": round(time.time() - t1, 2)})
    except Exception as e:  # tiempo agotado, error de la pagina, etc.
        resultados.append({"ok": False, "error": type(e).__name__, "t": round(time.time() - t0, 1)})
    finally:
        await ctx.close()


def resumen(valores):
    v = sorted(valores)
    return {"promedio": round(statistics.mean(v), 2), "mediana": round(statistics.median(v), 2),
            "p95": round(v[min(len(v) - 1, int(0.95 * len(v)))], 2), "maximo": round(v[-1], 2)} if v else {}


async def escenario(n):
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        resultados = []
        t0 = time.time()
        await asyncio.gather(*(usuario(browser, i, resultados) for i in range(n)))
        total = time.time() - t0
        await browser.close()
    ok = [r for r in resultados if r["ok"]]
    return {
        "usuarios": n, "exitosos": len(ok), "errores": n - len(ok), "errores_pct": round(100 * (n - len(ok)) / n, 1),
        "duracion_total_s": round(total, 1), "login": resumen([r["login_s"] for r in ok]), "mapa": resumen([r["mapa_s"] for r in ok]),
        "tipos_de_error": sorted({r["error"] for r in resultados if not r["ok"]}),
    }


async def main():
    out = []
    for n in (int(x) for x in sys.argv[1:] or ["10"]):
        print(f"--- {n} usuarios simultaneos ---", flush=True)
        r = await escenario(n)
        print(json.dumps(r, ensure_ascii=False), flush=True)
        out.append(r)
        await asyncio.sleep(5)
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


asyncio.run(main())
