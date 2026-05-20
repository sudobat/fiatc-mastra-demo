"""
Batería de 100 preguntas para validar el agente Guía Médica FIATC.

Uso:
    python tests/bateria_100_preguntas.py
    python tests/bateria_100_preguntas.py --url http://localhost:8000
    python tests/bateria_100_preguntas.py --pausa 3.0   # segundos entre peticiones

Genera:
    tests/resultados_bateria.json   — detalle de cada pregunta
    tests/resumen_bateria.txt       — resumen legible
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Definición de las 100 preguntas
# ---------------------------------------------------------------------------

@dataclass
class Caso:
    id: int
    categoria: str
    pregunta: str
    # Palabras clave que DEBEN aparecer en la respuesta (al menos una)
    palabras_clave: list[str] = field(default_factory=list)
    # Si es True, "no encontré resultados" se considera válido
    sin_resultado_ok: bool = False
    # Herramienta que esperamos ver usada (vacío = no se valida)
    herramienta_esperada: str = ""

CASOS: list[Caso] = [
    # ------------------------------------------------------------------
    # A. Búsqueda específica: especialidad + provincia (25 preguntas)
    # ------------------------------------------------------------------
    Caso(1,  "A-especialidad_provincia", "Busco un cardiólogo en Barcelona",
         ["barcelona", "cardiolog", "teléfono", "centro", "calle"]),
    Caso(2,  "A-especialidad_provincia", "Necesito un pediatra en Madrid",
         ["madrid", "pediatr", "teléfono", "centro"]),
    Caso(3,  "A-especialidad_provincia", "¿Hay dermatólogos en Valencia?",
         ["valenci", "dermatol", "centro"]),
    Caso(4,  "A-especialidad_provincia", "Quiero ver a un traumatólogo en Sevilla",
         ["sevilla", "traumat", "centro"]),
    Caso(5,  "A-especialidad_provincia", "¿Dónde hay un neurólogo en Zaragoza?",
         ["zaragoza", "neurol", "centro"]),
    Caso(6,  "A-especialidad_provincia", "Necesito un ginecólogo en Baleares",
         ["balear", "ginec", "centro"]),
    Caso(7,  "A-especialidad_provincia", "¿Hay oftalmólogos en Málaga?",
         ["málaga", "malaga", "oftalm", "centro"]),
    Caso(8,  "A-especialidad_provincia", "Busco otorrinolaringólogo en Vizcaya",
         ["vizcaya", "otorrin", "centro"]),
    Caso(9,  "A-especialidad_provincia", "¿Dónde hay un psiquiatra en Barcelona?",
         ["barcelona", "psiquiat", "centro"]),
    Caso(10, "A-especialidad_provincia", "Busco reumatólogo en Sevilla",
         ["sevilla", "reumatol", "centro"]),
    Caso(11, "A-especialidad_provincia", "¿Hay endocrinólogos en Valencia?",
         ["valenci", "endocrin", "centro"]),
    Caso(12, "A-especialidad_provincia", "Necesito un nefrólogo en Madrid",
         ["madrid", "nefrol", "centro"]),
    Caso(13, "A-especialidad_provincia", "Busco oncólogo en Barcelona",
         ["barcelona", "oncol", "centro"]),
    Caso(14, "A-especialidad_provincia", "¿Hay rehabilitación en Málaga?",
         ["málaga", "malaga", "rehabilitac", "centro"]),
    Caso(15, "A-especialidad_provincia", "Busco neumólogo en Zaragoza",
         ["zaragoza", "neumon", "neumol", "centro"]),
    Caso(16, "A-especialidad_provincia", "Necesito un urólogo en Baleares",
         ["balear", "urol", "centro"]),
    Caso(17, "A-especialidad_provincia", "¿Hay neurocirujanos en Madrid?",
         ["madrid", "neurocirug", "centro"], sin_resultado_ok=True),
    Caso(18, "A-especialidad_provincia", "Busco alergólogo en Vizcaya",
         ["vizcaya", "alergo", "alergo", "centro"]),
    Caso(19, "A-especialidad_provincia", "¿Dónde hay fisioterapia en Barcelona?",
         ["barcelona", "fisioter", "centro"]),
    Caso(20, "A-especialidad_provincia", "Necesito un hematólogo en Sevilla",
         ["sevilla", "hemato", "centro"], sin_resultado_ok=True),
    Caso(21, "A-especialidad_provincia", "¿Hay geriatras en Valencia?",
         ["valenci", "geriatra", "geriatr", "centro"], sin_resultado_ok=True),
    Caso(22, "A-especialidad_provincia", "Busco un podólogo en Madrid",
         ["madrid", "podol", "centro"]),
    Caso(23, "A-especialidad_provincia", "¿Hay logopedas en Málaga?",
         ["málaga", "malaga", "logoped", "centro"], sin_resultado_ok=True),
    Caso(24, "A-especialidad_provincia", "Necesito urgencias 24 horas en Madrid",
         ["madrid", "urgenci", "centro"]),
    Caso(25, "A-especialidad_provincia", "¿Hay centros con urgencias en Barcelona?",
         ["barcelona", "urgenci", "centro"]),

    # ------------------------------------------------------------------
    # B. Síntoma → especialidad + búsqueda (20 preguntas)
    # ------------------------------------------------------------------
    Caso(26, "B-sintoma", "Me duele mucho la rodilla, ¿qué especialista necesito en Barcelona?",
         ["traumat", "centro", "barcelona"]),
    Caso(27, "B-sintoma", "Tengo problemas de visión, ¿adónde debo ir en Madrid?",
         ["oftalm", "centro", "madrid"]),
    Caso(28, "B-sintoma", "Mi hijo tiene fiebre alta y lleva días malo, estoy en Sevilla",
         ["pediatr", "centro", "sevilla"]),
    Caso(29, "B-sintoma", "Me duele el pecho con frecuencia, ¿a qué especialista voy en Madrid?",
         ["cardiol", "centro", "madrid"]),
    Caso(30, "B-sintoma", "Tengo sarpullido en la piel desde hace semanas, busco médico en Valencia",
         ["dermatol", "centro", "valenci"]),
    Caso(31, "B-sintoma", "Me duele la cabeza constantemente y tengo mareos, estoy en Zaragoza",
         ["neurol", "centro", "zaragoza"]),
    Caso(32, "B-sintoma", "Tengo pitidos en los oídos y problemas de audición en Vizcaya",
         ["otorrin", "centro", "vizcaya"]),
    Caso(33, "B-sintoma", "Creo que tengo alergia al polen, ¿a quién voy en Barcelona?",
         ["alergo", "centro", "barcelona"]),
    Caso(34, "B-sintoma", "Me cuesta respirar cuando hago ejercicio, estoy en Baleares",
         ["cardiol", "neumol", "neumon", "centro", "balear"]),
    Caso(35, "B-sintoma", "Tengo problemas de tiroides, ¿dónde me pueden atender en Madrid?",
         ["endocrin", "centro", "madrid"]),
    Caso(36, "B-sintoma", "Llevo meses con insomnio y mucha ansiedad en Barcelona",
         ["psicol", "psiquiat", "centro", "barcelona"]),
    Caso(37, "B-sintoma", "Tengo dolor fuerte en las articulaciones de las manos, estoy en Sevilla",
         ["reumatol", "centro", "sevilla"]),
    Caso(38, "B-sintoma", "Mi hijo tiene retraso en el habla, busco especialista en Barcelona",
         ["logoped", "centro", "barcelona"], sin_resultado_ok=True),
    Caso(39, "B-sintoma", "Tengo varices muy pronunciadas, ¿qué especialista necesito en Valencia?",
         ["angiolog", "vasc", "ciruj", "centro", "valenci"]),
    Caso(40, "B-sintoma", "Me han mandado hacer una resonancia magnética en Madrid",
         ["resonanci", "rmn", "centro", "madrid"]),
    Caso(41, "B-sintoma", "Tengo diabetes y necesito control nutricional en Málaga",
         ["endocrin", "nutric", "dietét", "centro", "málaga", "malaga"]),
    Caso(42, "B-sintoma", "Tengo dolor de espalda crónico, ¿rehabilitación o traumatólogo en Zaragoza?",
         ["rehabilitac", "traumat", "centro", "zaragoza"]),
    Caso(43, "B-sintoma", "Necesito hacerme una mamografía en Sevilla",
         ["mamograf", "centro", "sevilla"]),
    Caso(44, "B-sintoma", "Tengo cálculos renales, ¿qué especialista en Baleares?",
         ["urol", "centro", "balear"]),
    Caso(45, "B-sintoma", "Me han detectado un soplo en el corazón en Vizcaya",
         ["cardiol", "centro", "vizcaya"]),

    # ------------------------------------------------------------------
    # C. Listados y navegación (10 preguntas)
    # ------------------------------------------------------------------
    Caso(46, "C-listados", "¿Qué especialidades están disponibles en el cuadro médico?",
         ["cardiolog", "pediatr", "dermatol", "especialidad"]),
    Caso(47, "C-listados", "¿En qué provincias tenéis cobertura?",
         ["barcelona", "madrid", "valenci", "provincia"]),
    Caso(48, "C-listados", "Muéstrame centros médicos en Madrid",
         ["madrid", "centro", "teléfono"]),
    Caso(49, "C-listados", "¿Qué especialidades hay disponibles en Vizcaya?",
         ["vizcaya", "especialidad", "cardiolog", "pediatr"]),
    Caso(50, "C-listados", "¿Hay dentistas u odontólogos en el cuadro médico?",
         ["odontol", "dental", "dent", "centro"], sin_resultado_ok=True),
    Caso(51, "C-listados", "¿Qué servicios de urgencias hay en Barcelona?",
         ["barcelona", "urgenci", "centro"]),
    Caso(52, "C-listados", "Dime los centros que tienen cardiología en Sevilla",
         ["sevilla", "cardiol", "centro"]),
    Caso(53, "C-listados", "¿Cuántas especialidades tiene el cuadro médico?",
         ["especialidad", "disponib"]),
    Caso(54, "C-listados", "¿Hay hospitales en el cuadro médico?",
         ["hospital", "hospit", "centro"], sin_resultado_ok=True),
    Caso(55, "C-listados", "Muéstrame centros en Baleares con traumatología",
         ["balear", "traumat", "centro"]),

    # ------------------------------------------------------------------
    # D. Búsqueda por población concreta (10 preguntas)
    # ------------------------------------------------------------------
    Caso(56, "D-poblacion", "Busco médico de medicina general en Hospitalet de Llobregat",
         ["hospitalet", "llobregat", "medicina general", "centro"], sin_resultado_ok=True),
    Caso(57, "D-poblacion", "¿Hay pediatras en Terrassa?",
         ["terrassa", "pediatr", "centro"], sin_resultado_ok=True),
    Caso(58, "D-poblacion", "Necesito un cardiólogo en Bilbao",
         ["bilbao", "vizcaya", "cardiol", "centro"]),
    Caso(59, "D-poblacion", "¿Hay centros médicos en Marbella?",
         ["marbella", "málaga", "malaga", "centro"], sin_resultado_ok=True),
    Caso(60, "D-poblacion", "Busco especialista en Palma de Mallorca",
         ["palma", "mallorca", "balear", "centro"]),
    Caso(61, "D-poblacion", "Necesito médico en Alcalá de Henares",
         ["alcalá", "alcala", "madrid", "centro"], sin_resultado_ok=True),
    Caso(62, "D-poblacion", "¿Hay traumatólogos en Sabadell?",
         ["sabadell", "barcelona", "traumat", "centro"], sin_resultado_ok=True),
    Caso(63, "D-poblacion", "Busco dermatólogo en Esplugues de Llobregat",
         ["esplugues", "llobregat", "barcelona", "dermatol", "centro"], sin_resultado_ok=True),
    Caso(64, "D-poblacion", "Necesito oftalmólogo en Getafe",
         ["getafe", "madrid", "oftalm", "centro"], sin_resultado_ok=True),
    Caso(65, "D-poblacion", "¿Hay neurólogos en Zaragoza capital?",
         ["zaragoza", "neurol", "centro"]),

    # ------------------------------------------------------------------
    # E. Preguntas complejas o multicriterio (5 preguntas)
    # ------------------------------------------------------------------
    Caso(66, "E-compleja", "Necesito un ginecólogo y también un pediatra, estoy en Sevilla",
         ["sevilla", "ginec", "pediatr", "centro"]),
    Caso(67, "E-compleja", "¿Hay algún centro en Madrid que tenga tanto neurología como psiquiatría?",
         ["madrid", "neurol", "psiquiat", "centro"]),
    Caso(68, "E-compleja", "Busco un cardiólogo urgente en Barcelona, preferiblemente con teléfono",
         ["barcelona", "cardiol", "centro", "teléfono"]),
    Caso(69, "E-compleja", "Tengo que operarme de la rodilla, ¿qué tipo de cirujano necesito en Valencia?",
         ["traumat", "ciruj", "centro", "valenci"]),
    Caso(70, "E-compleja", "Mi madre necesita un geriatra y yo un alergólogo, los dos en Barcelona",
         ["barcelona", "geriatra", "geriatr", "alergo", "centro"], sin_resultado_ok=True),

    # ------------------------------------------------------------------
    # F. Preguntas vagas o poco específicas (≥10 preguntas)
    # ------------------------------------------------------------------
    Caso(71, "F-vaga", "Quiero ir al médico",
         ["provincia", "especialidad", "dónde", "donde", "ubicac", "ayud"]),
    Caso(72, "F-vaga", "Me encuentro mal",
         ["especialidad", "síntoma", "sintoma", "médico", "medico", "ayud", "cuéntame"]),
    Caso(73, "F-vaga", "Necesito un especialista",
         ["especialidad", "provincia", "síntoma", "sintoma", "ayud"]),
    Caso(74, "F-vaga", "¿Podéis ayudarme?",
         ["especialidad", "médico", "medico", "guía", "guia", "buscar", "ayud"]),
    Caso(75, "F-vaga", "Tengo dolor",
         ["dónde", "donde", "qué", "que", "síntoma", "sintoma", "zona", "tipo"]),
    Caso(76, "F-vaga", "Busco médico cerca de casa",
         ["provincia", "ciudad", "población", "poblacion", "dónde", "donde"]),
    Caso(77, "F-vaga", "Quiero una consulta médica",
         ["especialidad", "provincia", "especialista", "ayud"]),
    Caso(78, "F-vaga", "¿Qué puedo hacer?",
         ["especialidad", "médico", "medico", "síntoma", "sintoma", "ayud", "buscar"]),
    Caso(79, "F-vaga", "Necesito atención médica urgente",
         ["urgenci", "provincia", "dónde", "donde", "centro"]),
    Caso(80, "F-vaga", "Tengo un problema de salud",
         ["síntoma", "sintoma", "especialidad", "cuéntame", "cuentame", "ayud"]),
    Caso(81, "F-vaga", "Me duele algo",
         ["dónde", "donde", "qué", "que", "zona", "síntoma", "sintoma"]),
    Caso(82, "F-vaga", "Necesito ayuda",
         ["especialidad", "médico", "medico", "buscar", "ayud"]),

    # ------------------------------------------------------------------
    # G. Fuera de dominio / edge cases (18 preguntas)
    # ------------------------------------------------------------------
    Caso(83, "G-fuera_dominio", "¿Cuánto cuesta una consulta de cardiología?",
         ["precio", "coste", "tarifa", "asegur", "fiatc", "guía médica", "guia medica",
          "no dispongo", "no tengo", "no puedo"], sin_resultado_ok=True),
    Caso(84, "G-fuera_dominio", "¿Cómo puedo darme de alta como asegurado?",
         ["asegur", "fiatc", "no", "alta", "contrato"], sin_resultado_ok=True),
    Caso(85, "G-fuera_dominio", "Quiero cancelar mi seguro",
         ["asegur", "fiatc", "no", "cancelar", "baja"], sin_resultado_ok=True),
    Caso(86, "G-fuera_dominio", "¿Aceptáis nuevos asegurados?",
         ["asegur", "fiatc", "no", "contrat"], sin_resultado_ok=True),
    Caso(87, "G-fuera_dominio", "¿Cuál es el número de teléfono de atención al cliente de FIATC?",
         ["atención al cliente", "atencion al cliente", "fiatc", "no dispongo",
          "no tengo", "teléfono"], sin_resultado_ok=True),
    Caso(88, "G-fuera_dominio", "¿Tenéis cobertura en el extranjero?",
         ["extranjero", "no", "fiatc", "guía médica", "guia medica"], sin_resultado_ok=True),
    Caso(89, "G-fuera_dominio", "Busco médico en Las Palmas de Gran Canaria",
         ["canaria", "las palmas", "no", "disponib", "cobertura", "provincia"], sin_resultado_ok=True),
    Caso(90, "G-fuera_dominio", "¿Hay veterinarios en el cuadro médico?",
         ["veterinar", "no", "animales", "médico", "human"], sin_resultado_ok=True),
    Caso(91, "G-fuera_dominio", "Necesito un abogado",
         ["abogado", "jurídic", "juridic", "no", "médico", "medico", "salud"], sin_resultado_ok=True),
    Caso(92, "G-fuera_dominio", "¿Cómo es el proceso de reembolso de gastos médicos?",
         ["reembolso", "asegur", "fiatc", "no", "guía médica"], sin_resultado_ok=True),
    Caso(93, "G-fuera_dominio", "¿Aceptáis el seguro de la Seguridad Social?",
         ["seguridad social", "no", "fiatc", "asegur"], sin_resultado_ok=True),
    Caso(94, "G-fuera_dominio", "Busco médico en Lugo",
         ["lugo", "no", "disponib", "cobertura", "provincia"], sin_resultado_ok=True),
    Caso(95, "G-fuera_dominio", "¿Hay médicos en Ceuta?",
         ["ceuta", "no", "disponib", "cobertura"], sin_resultado_ok=True),
    Caso(96, "G-fuera_dominio", "¿Cuál es la diferencia entre vuestros planes de seguro?",
         ["plan", "seguro", "no", "fiatc", "guía médica"], sin_resultado_ok=True),
    Caso(97, "G-fuera_dominio", "¿Tenéis aplicación móvil?",
         ["aplicación", "app", "móvil", "no", "fiatc"], sin_resultado_ok=True),
    Caso(98, "G-fuera_dominio", "¿Puedo pedir cita online?",
         ["cita", "online", "reserva", "teléfono", "centro"]),
    Caso(99, "G-fuera_dominio", "¿Qué es FIATC?",
         ["fiatc", "seguro", "asegur", "médico", "guía", "guia"]),
    Caso(100, "G-fuera_dominio", "Busco médico en Tenerife",
         ["tenerife", "canaria", "no", "disponib", "cobertura", "provincia"], sin_resultado_ok=True),
]

assert len(CASOS) == 100, f"Se esperaban 100 casos, hay {len(CASOS)}"

# ---------------------------------------------------------------------------
# Resultado de cada prueba
# ---------------------------------------------------------------------------

@dataclass
class Resultado:
    id: int
    categoria: str
    pregunta: str
    ok: bool
    motivo_fallo: str
    respuesta: str
    herramientas_usadas: list[str]
    tiempo_s: float

# ---------------------------------------------------------------------------
# Ejecución de la batería
# ---------------------------------------------------------------------------

def llamar_api(url_base: str, pregunta: str, timeout: float = 60.0) -> dict:
    with httpx.Client(timeout=timeout) as client:
        r = client.post(
            f"{url_base}/chat",
            json={"mensaje": pregunta, "historial": []},
        )
        r.raise_for_status()
        return r.json()


def validar(caso: Caso, respuesta: str) -> tuple[bool, str]:
    if not respuesta or len(respuesta.strip()) < 20:
        return False, "Respuesta vacía o demasiado corta"

    respuesta_lower = respuesta.lower()

    # Detectar respuesta de error del propio agente
    if "no he podido completar la consulta" in respuesta_lower:
        return False, "El agente superó el límite de iteraciones"

    # Si no hay palabras clave definidas, basta con que haya respuesta
    if not caso.palabras_clave:
        return True, ""

    encontradas = [kw for kw in caso.palabras_clave if kw.lower() in respuesta_lower]
    if not encontradas:
        return False, f"Ninguna palabra clave encontrada ({caso.palabras_clave[:5]})"

    return True, ""


def ejecutar_bateria(url_base: str, pausa: float) -> list[Resultado]:
    resultados: list[Resultado] = []
    total = len(CASOS)

    print(f"\nIniciando batería de {total} preguntas contra {url_base}")
    print(f"Pausa entre peticiones: {pausa}s\n")
    print(f"{'ID':>3}  {'Cat':<25}  {'OK':>3}  {'t(s)':>5}  Pregunta")
    print("-" * 90)

    for caso in CASOS:
        inicio = time.monotonic()
        ok = False
        motivo = ""
        respuesta_texto = ""
        herramientas: list[str] = []

        try:
            datos = llamar_api(url_base, caso.pregunta)
            respuesta_texto = datos.get("respuesta", "")
            herramientas = datos.get("herramientas_usadas", [])
            ok, motivo = validar(caso, respuesta_texto)
        except httpx.HTTPStatusError as exc:
            motivo = f"HTTP {exc.response.status_code}"
        except httpx.TimeoutException:
            motivo = "Timeout"
        except Exception as exc:
            motivo = f"Error: {exc}"

        tiempo = round(time.monotonic() - inicio, 1)
        icono = "OK " if ok else "FAL"
        print(f"{caso.id:>3}  {caso.categoria:<25}  {icono}  {tiempo:>5}  {caso.pregunta[:55]}")
        if not ok:
            print(f"     => {motivo}")
            if respuesta_texto:
                print(f"     => Respuesta: {respuesta_texto[:120]}...")

        resultados.append(Resultado(
            id=caso.id,
            categoria=caso.categoria,
            pregunta=caso.pregunta,
            ok=ok,
            motivo_fallo=motivo,
            respuesta=respuesta_texto,
            herramientas_usadas=herramientas,
            tiempo_s=tiempo,
        ))

        if caso.id < total:
            time.sleep(pausa)

    return resultados


# ---------------------------------------------------------------------------
# Informe final
# ---------------------------------------------------------------------------

def generar_informe(resultados: list[Resultado], dir_tests: Path) -> None:
    total = len(resultados)
    pasados = sum(1 for r in resultados if r.ok)
    fallados = total - pasados

    # Agrupar por categoría
    por_categoria: dict[str, list[Resultado]] = {}
    for r in resultados:
        cat = r.categoria.split("-")[0]
        por_categoria.setdefault(cat, []).append(r)

    # Herramientas más usadas
    from collections import Counter
    uso_herramientas: Counter = Counter()
    for r in resultados:
        uso_herramientas.update(r.herramientas_usadas)

    tiempo_total = sum(r.tiempo_s for r in resultados)
    tiempo_medio = tiempo_total / total if total else 0

    lineas = [
        "=" * 70,
        f"INFORME BATERÍA 100 PREGUNTAS — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 70,
        f"Total preguntas : {total}",
        f"Pasadas         : {pasados} ({pasados/total*100:.1f}%)",
        f"Falladas        : {fallados} ({fallados/total*100:.1f}%)",
        f"Tiempo total    : {tiempo_total:.0f}s  |  Tiempo medio/preg: {tiempo_medio:.1f}s",
        "",
        "RESULTADOS POR CATEGORÍA",
        "-" * 70,
    ]
    for prefijo, rs in sorted(por_categoria.items()):
        ok_n = sum(1 for r in rs if r.ok)
        lineas.append(f"  {prefijo:<3}  {ok_n:>2}/{len(rs):<2}  ({ok_n/len(rs)*100:.0f}%)")

    lineas += [
        "",
        "HERRAMIENTAS USADAS",
        "-" * 70,
    ]
    if uso_herramientas:
        for tool, cnt in uso_herramientas.most_common():
            lineas.append(f"  {tool:<40} {cnt:>4}x")
    else:
        lineas.append("  (ninguna)")

    if fallados:
        lineas += [
            "",
            "DETALLE DE FALLOS",
            "-" * 70,
        ]
        for r in resultados:
            if not r.ok:
                lineas.append(f"  #{r.id:>3} [{r.categoria}]")
                lineas.append(f"       P: {r.pregunta[:70]}")
                lineas.append(f"       F: {r.motivo_fallo}")
                if r.respuesta:
                    lineas.append(f"       R: {r.respuesta[:120]}")
                lineas.append("")

    lineas.append("=" * 70)
    texto = "\n".join(lineas)

    # Imprimir en consola
    print("\n" + texto)

    # Guardar resumen
    ruta_txt = dir_tests / "resumen_bateria.txt"
    ruta_txt.write_text(texto, encoding="utf-8")
    print(f"\nResumen guardado en: {ruta_txt}")

    # Guardar JSON detallado
    ruta_json = dir_tests / "resultados_bateria.json"
    ruta_json.write_text(
        json.dumps([asdict(r) for r in resultados], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Detalle JSON en   : {ruta_json}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Batería 100 preguntas Guía Médica FIATC")
    parser.add_argument("--url", default="http://localhost:8000", help="URL base del backend")
    parser.add_argument("--pausa", type=float, default=2.0, help="Segundos entre peticiones")
    args = parser.parse_args()

    # Verificar que el backend está vivo
    try:
        with httpx.Client(timeout=5) as c:
            c.get(f"{args.url}/health").raise_for_status()
    except Exception as exc:
        print(f"ERROR: No se puede conectar con el backend en {args.url}: {exc}")
        sys.exit(1)

    dir_tests = Path(__file__).parent
    resultados = ejecutar_bateria(args.url, args.pausa)
    generar_informe(resultados, dir_tests)


if __name__ == "__main__":
    main()
