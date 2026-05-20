"""Interfaz comun para acceder a los datos del cuadro medico.

Cualquier implementacion (fichero local, API interna, BD SQL Server) debe
respetar este contrato. El agente solo conoce esta interfaz.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel, Field


class Profesional(BaseModel):
    id: str
    nombre: str
    especialidad: str
    centro: str
    direccion: str
    poblacion: str
    provincia: str
    codigo_postal: str
    telefono: Optional[str] = None
    cuadros: list[str] = Field(default_factory=list)
    reserva_online: bool = False
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    # Solo se rellena cuando la busqueda usa proximidad (cerca_de_lat/lng).
    distancia_km: Optional[float] = None


class DoctorCentro(BaseModel):
    nombre: str
    especialidades: list[str] = Field(default_factory=list)
    reserva_online: bool = False
    # Campos XWM para construir la URL de reserva online.
    # prof: código numérico del profesional (posiciones 0-4 del ref de 18 dígitos).
    # ref:  slug completo + número de 18 dígitos (ej. "dr-daniel-martin-casola-008140000089120040").
    prof: Optional[str] = None
    ref: Optional[str] = None


class Centro(BaseModel):
    id: str
    nombre: str
    direccion: str
    poblacion: str
    provincia: str
    codigo_postal: str
    telefono: Optional[str] = None
    horario: Optional[str] = None
    especialidades: list[str] = Field(default_factory=list)
    cuadros: list[str] = Field(default_factory=list)
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    reserva_online: bool = False
    preferente: bool = False
    profesionales: list[DoctorCentro] = Field(default_factory=list)
    # Campos XWM para la reserva online.
    # consul: código del consultorio (5 dígitos, ej. "89120").
    # fact:   código del facturador (ej. "2651").
    consul: Optional[str] = None
    fact: Optional[str] = None


class FiltroBusqueda(BaseModel):
    cuadro: str = "Cuadro completo"
    tipo_servicio: str = "Médicos y hospitales"
    provincia: Optional[str] = None
    poblacion: Optional[str] = None
    codigo_postal: Optional[str] = None
    especialidad: Optional[str] = None
    nombre: Optional[str] = None
    reserva_online: Optional[bool] = None
    # Proximidad geografica: cuando se proporcionan, sustituyen al filtro de
    # provincia (busqueda por radio real ignorando limites administrativos).
    cerca_de_lat: Optional[float] = None
    cerca_de_lng: Optional[float] = None
    radio_km: Optional[float] = None  # default aplicado en el repositorio si hay coords


class GuiaMedicaRepository(ABC):
    """Contrato de acceso a datos. Toda implementacion debe respetar esta interfaz."""

    @abstractmethod
    def buscar_profesionales(self, filtro: FiltroBusqueda) -> list[Profesional]:
        """Devuelve los profesionales que cumplen los filtros."""

    @abstractmethod
    def obtener_centro(self, id_centro: str) -> Optional[Centro]:
        """Devuelve la ficha completa de un centro por su id."""

    @abstractmethod
    def listar_especialidades(self) -> list[str]:
        """Devuelve el catalogo cerrado de especialidades validas."""

    @abstractmethod
    def listar_provincias(self) -> list[str]:
        """Devuelve el catalogo de provincias validas."""
