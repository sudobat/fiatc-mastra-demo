"""Implementacion del repositorio que lee de un fichero JSON local."""
from __future__ import annotations

import json
import math
import unicodedata
from pathlib import Path
from typing import Optional

from app.repositories.base import (
    Centro,
    FiltroBusqueda,
    GuiaMedicaRepository,
    Profesional,
)


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distancia esferica entre dos puntos lat/lng en kilometros."""
    R = 6371.0
    a1, a2 = math.radians(lat1), math.radians(lat2)
    da = math.radians(lat2 - lat1)
    do = math.radians(lng2 - lng1)
    h = math.sin(da / 2) ** 2 + math.cos(a1) * math.cos(a2) * math.sin(do / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))

_REEMPLAZO_UNICODE = "�"  # carácter de sustitución generado por el scraping con encoding incorrecto


def _normalizar(texto: str) -> str:
    """Elimina acentos, convierte a minúsculas, limpia puntuación y caracteres de reemplazo."""
    s = unicodedata.normalize("NFD", texto.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace(".", " ").replace("/", " ").replace("-", " ")
    s = s.replace(_REEMPLAZO_UNICODE, "")
    return s


def _coincide_especialidad(filtro: str, especialidad: str) -> bool:
    """Coincidencia flexible entre el filtro del usuario y el nombre FIATC.

    Permite que "Traumatología" encuentre "Traumat.Y Ortopedia", que
    "ortopeda" encuentre "Traumat.Y Ortopedia", etc.
    """
    f = _normalizar(filtro)
    e = _normalizar(especialidad)
    if f == e or f in e or e in f:
        return True
    # Comparación por prefijo de 7 chars de cada palabra significativa (≥5 letras)
    PREFIJO = 7
    tokens_f = [w[:PREFIJO] for w in f.split() if len(w) >= 5]
    tokens_e = [w[:PREFIJO] for w in e.split() if len(w) >= 5]
    return any(tf in tokens_e for tf in tokens_f)


def _dedup_centros(centros: list["Centro"]) -> list["Centro"]:
    """Funde entradas que apuntan al mismo centro fisico (el scraping de FIATC
    repite el mismo centro con ids distintos al recorrerlo desde varias paginas).

    Clave de identidad: (latitud, longitud) redondeadas a 5 decimales (~1 m).
    Si no hay coordenadas, se cae a (nombre normalizado, direccion normalizada).
    Las especialidades se unen, manteniendo el primer centro como canonico.
    """
    vistos: dict = {}
    for c in centros:
        if c.latitud is not None and c.longitud is not None:
            clave = ("c", round(c.latitud, 5), round(c.longitud, 5))
        else:
            clave = ("n", _normalizar(c.nombre), _normalizar(c.direccion or ""))
        if clave in vistos:
            existente = vistos[clave]
            for esp in c.especialidades:
                if esp not in existente.especialidades:
                    existente.especialidades.append(esp)
            # Heredar profesionales del duplicado que los tenga
            if c.profesionales and not existente.profesionales:
                existente.profesionales.extend(c.profesionales)
            if c.reserva_online:
                existente.reserva_online = True
        else:
            # Copia con sus propias listas para no mutar el repositorio
            vistos[clave] = c.model_copy(update={
                "especialidades": list(c.especialidades),
                "profesionales": list(c.profesionales),
            })
    return list(vistos.values())


def _coincide_nombre(filtro: str, nombre_centro: str) -> bool:
    """Búsqueda tolerante a errores de encoding: todos los tokens del filtro deben
    aparecer en el nombre del centro; los que fallen se reintenta con prefijo de 4 chars
    para cubrir caracteres corruptos del scraping (ej. "avancada" ≈ "avan"+<fffd>+"ada").
    """
    f = _normalizar(filtro)
    n = _normalizar(nombre_centro)
    # Coincidencia directa
    if f in n or n in f:
        return True
    tokens = [t for t in f.split() if len(t) > 3]
    if not tokens:
        return f in n
    # Todos los tokens deben coincidir; si falla la coincidencia exacta, se prueba prefijo-4
    for t in tokens:
        if t in n:
            continue
        if len(t) >= 4 and t[:4] in n:
            continue
        return False
    return True


class FicheroLocalGuiaMedicaRepository(GuiaMedicaRepository):
    def __init__(self, ruta_fichero: Path) -> None:
        # Resuelve la ruta relativa a la cwd del backend
        self._ruta = Path(ruta_fichero).resolve()
        if not self._ruta.exists():
            # Intentar resolver relativa al directorio del modulo
            alternativa = (Path(__file__).parent.parent.parent.parent / ruta_fichero).resolve()
            if alternativa.exists():
                self._ruta = alternativa
            else:
                raise FileNotFoundError(
                    f"No se encuentra el fichero del cuadro medico: {ruta_fichero}"
                )
        with self._ruta.open("r", encoding="utf-8") as f:
            datos = json.load(f)
        self._profesionales: list[Profesional] = [Profesional(**p) for p in datos.get("profesionales", [])]
        self._centros: dict[str, Centro] = {
            c["id"]: Centro(**c) for c in datos.get("centros", [])
        }
        self._especialidades: list[str] = datos.get("especialidades", [])
        self._provincias: list[str] = datos.get("provincias", [])
        # Índice lat/lng → profesionales mergeados de TODOS los duplicados.
        # Deduplicamos por nombre y usamos OR en reserva_online para que si
        # cualquier duplicado tiene ccita=True, el doctor lo refleje.
        _merge: dict[tuple, dict[str, "Profesional"]] = {}
        for c_obj in self._centros.values():
            if c_obj.latitud and c_obj.longitud and c_obj.profesionales:
                key = (round(c_obj.latitud, 5), round(c_obj.longitud, 5))
                bucket = _merge.setdefault(key, {})
                for p in c_obj.profesionales:
                    if p.nombre not in bucket:
                        bucket[p.nombre] = p.model_copy()
                    elif p.reserva_online and not bucket[p.nombre].reserva_online:
                        bucket[p.nombre] = bucket[p.nombre].model_copy(
                            update={"reserva_online": True}
                        )
        self._profs_por_latlng: dict[tuple, list] = {
            key: list(profs.values()) for key, profs in _merge.items()
        }
        # Índice rápido: ¿tiene reserva_online algún profesional en este lat/lng?
        self._reserva_por_latlng: dict[tuple, bool] = {
            key: any(p.reserva_online for p in profs)
            for key, profs in self._profs_por_latlng.items()
        }

    def buscar_profesionales(self, filtro: FiltroBusqueda) -> list[Profesional]:
        # Con datos reales del scraping, profesionales está vacío: buscamos en centros.
        if self._profesionales:
            return self._filtrar_profesionales(filtro)
        return self._buscar_en_centros(filtro)

    def _filtrar_profesionales(self, filtro: FiltroBusqueda) -> list[Profesional]:
        resultado = self._profesionales
        if filtro.provincia:
            resultado = [p for p in resultado if p.provincia.lower() == filtro.provincia.lower()]
        if filtro.poblacion:
            resultado = [p for p in resultado if p.poblacion.lower() == filtro.poblacion.lower()]
        if filtro.codigo_postal:
            resultado = [p for p in resultado if p.codigo_postal == filtro.codigo_postal]
        if filtro.especialidad:
            resultado = [p for p in resultado if _coincide_especialidad(filtro.especialidad, p.especialidad)]
        if filtro.nombre:
            resultado = [p for p in resultado if _coincide_nombre(filtro.nombre, p.nombre) or _coincide_nombre(filtro.nombre, p.centro)]
        if filtro.reserva_online is True:
            resultado = [p for p in resultado if p.reserva_online]
        if filtro.cuadro and filtro.cuadro.lower() != "cuadro completo":
            resultado = [p for p in resultado if filtro.cuadro in p.cuadros]
        return resultado

    def _buscar_en_centros(self, filtro: FiltroBusqueda) -> list[Profesional]:
        """Convierte centros en resultados de tipo Profesional para el agente.

        Si el filtro incluye coordenadas (`cerca_de_lat`/`cerca_de_lng`), se
        ignora el filtro de provincia y se calcula la distancia haversine a
        cada centro para ordenar y filtrar por radio (default 30 km).
        """
        centros = list(self._centros.values())
        modo_proximidad = filtro.cerca_de_lat is not None and filtro.cerca_de_lng is not None

        # En modo proximidad, NO filtramos por provincia (la idea es saltar
        # limites administrativos cuando el usuario busca cerca de una zona).
        if filtro.provincia and not modo_proximidad:
            centros = [c for c in centros if c.provincia.lower() == filtro.provincia.lower()]
        if filtro.poblacion:
            p = _normalizar(filtro.poblacion)
            centros = [c for c in centros if p in _normalizar(c.poblacion)]
        if filtro.codigo_postal and not modo_proximidad:
            centros = [c for c in centros if c.codigo_postal == filtro.codigo_postal]
        if filtro.nombre:
            centros = [c for c in centros if _coincide_nombre(filtro.nombre, c.nombre)]

        # Deduplicar entradas que apuntan al mismo centro fisico (scraping repetido)
        centros = _dedup_centros(centros)

        # Calcular distancias y filtrar por radio si estamos en modo proximidad
        distancias: dict[str, float] = {}
        if modo_proximidad:
            radio = filtro.radio_km or 30.0
            con_coords = []
            for c in centros:
                if c.latitud is not None and c.longitud is not None:
                    d = _haversine_km(filtro.cerca_de_lat, filtro.cerca_de_lng, c.latitud, c.longitud)
                    if d <= radio:
                        distancias[c.id] = d
                        con_coords.append(c)
            # Primero los del CP exacto solicitado, luego el resto; dentro de cada grupo, por distancia
            cp_ref = filtro.codigo_postal or ""
            con_coords.sort(key=lambda c: (c.codigo_postal != cp_ref, distancias[c.id]))
            centros = con_coords

        # Expandir por especialidad: un centro con N especialidades genera N entradas
        resultado: list[Profesional] = []
        for centro in centros:
            # reserva_online: True si el centro o algún profesional mergeado lo tiene
            tiene_reserva = centro.reserva_online
            if not tiene_reserva and centro.latitud and centro.longitud:
                key = (round(centro.latitud, 5), round(centro.longitud, 5))
                tiene_reserva = self._reserva_por_latlng.get(key, False)

            if filtro.reserva_online is True and not tiene_reserva:
                continue

            especialidades = centro.especialidades or [""]
            for esp in especialidades:
                if filtro.especialidad and not _coincide_especialidad(filtro.especialidad, esp):
                    continue
                resultado.append(Profesional(
                    id=f"{centro.id}",
                    nombre=centro.nombre,
                    especialidad=esp,
                    centro=centro.nombre,
                    direccion=centro.direccion,
                    poblacion=centro.poblacion,
                    provincia=centro.provincia,
                    codigo_postal=centro.codigo_postal,
                    telefono=centro.telefono or "",
                    cuadros=centro.cuadros,
                    reserva_online=tiene_reserva,
                    latitud=centro.latitud,
                    longitud=centro.longitud,
                    distancia_km=round(distancias[centro.id], 1) if centro.id in distancias else None,
                ))

        return resultado

    def obtener_centro(self, id_centro: str) -> Optional[Centro]:
        c = self._centros.get(id_centro)
        if c is None:
            return None
        if c.latitud and c.longitud:
            key = (round(c.latitud, 5), round(c.longitud, 5))
            if key in self._profs_por_latlng:
                return c.model_copy(update={"profesionales": self._profs_por_latlng[key]})
        return c

    def listar_especialidades(self) -> list[str]:
        return list(self._especialidades)

    def listar_provincias(self) -> list[str]:
        return list(self._provincias)
