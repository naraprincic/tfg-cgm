"""Modelos: las tablas de la base de datos escritas como clases de Python."""

from datetime import date, datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    Float,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Valores iniciales de la configuración (HU-001, criterio 4).
RANGO_MIN_INICIAL = 70   # mg/dL
RANGO_MAX_INICIAL = 180  # mg/dL
ZONA_HORARIA_INICIAL = "America/Argentina/Buenos_Aires"


def ahora_utc() -> datetime:
    """Fecha y hora actual en UTC (así se guarda en la base, sin ambigüedad)."""
    return datetime.now(timezone.utc)


def como_utc(momento: datetime) -> datetime:
    """Asegura que una fecha leída de la base tenga zona horaria (UTC)."""
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


class Usuario(Base):
    """Persona titular de los datos. Todo lo demás (mediciones, eventos...) le pertenece."""

    __tablename__ = "usuario"

    id_usuario: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    # Nunca se guarda la contraseña: solo su hash (bcrypt, factor de costo 12).
    contrasena_hash: Mapped[str] = mapped_column(String(60))
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    # Consentimiento expreso para tratar datos de salud (Ley 25.326, art. 5).
    fecha_consentimiento: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Relación uno a uno con Configuracion.
    configuracion: Mapped["Configuracion"] = relationship(
        back_populates="usuario", cascade="all, delete-orphan", uselist=False
    )


class Configuracion(Base):
    """Preferencias del usuario: rango objetivo de glucosa y zona horaria."""

    __tablename__ = "configuracion"

    id_configuracion: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario", ondelete="CASCADE"), unique=True
    )
    rango_min: Mapped[int] = mapped_column(Integer, default=RANGO_MIN_INICIAL)
    rango_max: Mapped[int] = mapped_column(Integer, default=RANGO_MAX_INICIAL)
    zona_horaria: Mapped[str] = mapped_column(String(64), default=ZONA_HORARIA_INICIAL)

    usuario: Mapped[Usuario] = relationship(back_populates="configuracion")


class ControlAcceso(Base):
    """Intentos fallidos de inicio de sesión (apartado Seguridad): luego de cinco intentos consecutivos la cuenta se bloquea durante 15 minutos."""

    __tablename__ = "control_acceso"

    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario", ondelete="CASCADE"), primary_key=True
    )
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Sesion(Base):
    """Sesión iniciada (HU-002 / HU-003)."""

    __tablename__ = "sesion"

    id_sesion: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    ultimo_uso: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)


class Importacion(Base):
    """Cada archivo procesado (HU-005 / HU-006). Agrupa las mediciones que aportó."""

    __tablename__ = "importacion"
    # Permite que medicion referencie el par (id_importacion, id_usuario): así una medición no puede quedar asociada a la importación de otra persona (ver DER).
    __table_args__ = (UniqueConstraint("id_importacion", "id_usuario"),)

    id_importacion: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario", ondelete="CASCADE"), index=True
    )
    nombre_archivo: Mapped[str] = mapped_column(String(255))
    formato: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fecha_importacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    estado: Mapped[str] = mapped_column(String(15))  # completada | rechazada
    motivo_rechazo: Mapped[str | None] = mapped_column(Text, nullable=True)
    filas_glucosa: Mapped[int] = mapped_column(Integer, default=0)
    mediciones_incorporadas: Mapped[int] = mapped_column(Integer, default=0)
    filas_invalidas: Mapped[int] = mapped_column(Integer, default=0)
    filas_duplicadas: Mapped[int] = mapped_column(Integer, default=0)
    filas_en_conflicto: Mapped[int] = mapped_column(Integer, default=0)
    dias: Mapped[int] = mapped_column(Integer, default=0)
    # Para poder reproducir el procesamiento: formato de fecha confirmado y zona horaria aplicada.
    formato_fecha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    zona_horaria: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Período que abarcan las mediciones incorporadas.
    periodo_desde: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    periodo_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Medicion(Base):
    """Un valor de glucosa registrado por el sensor (diccionario de datos, Tabla 24)."""

    __tablename__ = "medicion"
    __table_args__ = (
        # Cada medición se identifica por usuario, origen y fecha y hora.
        UniqueConstraint("id_usuario", "origen", "fecha_hora"),
        ForeignKeyConstraint(
            ["id_importacion", "id_usuario"],
            ["importacion.id_importacion", "importacion.id_usuario"],
            ondelete="CASCADE",
        ),
        Index("ix_medicion_usuario_fecha", "id_usuario", "fecha_hora"),
    )

    id_medicion: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
    id_importacion: Mapped[int] = mapped_column(Integer)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario", ondelete="CASCADE"))
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valor: Mapped[int] = mapped_column(SmallInteger)  # mg/dL
    origen: Mapped[str] = mapped_column(String(40))
    marca: Mapped[str | None] = mapped_column(String(10), nullable=True)  # bajo | alto | None



class IndicadorDiario(Base):
    """Indicadores calculados de un día (diccionario de datos, Tabla 26)."""

    __tablename__ = "indicador_diario"
    __table_args__ = (
        UniqueConstraint("id_usuario", "fecha"),          # una sola vez por usuario y fecha
        UniqueConstraint("id_indicador", "id_usuario"),   # para claves foráneas compuestas
    )

    id_indicador: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario", ondelete="CASCADE"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    rango_min: Mapped[int] = mapped_column(Integer)
    rango_max: Mapped[int] = mapped_column(Integer)
    tir: Mapped[float] = mapped_column(Float)
    tir_personal: Mapped[float] = mapped_column(Float)
    tbr: Mapped[float] = mapped_column(Float)
    tbr_nivel2: Mapped[float] = mapped_column(Float)
    tar: Mapped[float] = mapped_column(Float)
    tar_nivel2: Mapped[float] = mapped_column(Float)
    glucosa_promedio: Mapped[float] = mapped_column(Float)
    coeficiente_variacion: Mapped[float] = mapped_column(Float)
    cobertura: Mapped[float] = mapped_column(Float)
    parcial: Mapped[bool] = mapped_column(Boolean)
    mediciones_validas: Mapped[int] = mapped_column(Integer)
    fecha_calculo: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)

    periodos: Mapped[list["PeriodoRelevante"]] = relationship(
        back_populates="indicador", cascade="all, delete-orphan", order_by="PeriodoRelevante.inicio"
    )


class PeriodoRelevante(Base):
    """Momento del día fuera de rango o con variación rápida (HU-011)."""

    __tablename__ = "periodo_relevante"
    __table_args__ = (
        ForeignKeyConstraint(
            ["id_indicador", "id_usuario"],
            ["indicador_diario.id_indicador", "indicador_diario.id_usuario"],
            ondelete="CASCADE",
        ),
    )

    id_periodo: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_indicador: Mapped[int] = mapped_column(Integer)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(15))  # bajo | sobre | bajo_nivel2 | sobre_nivel2 | subida | bajada
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duracion_min: Mapped[int] = mapped_column(Integer)
    valor_extremo: Mapped[int] = mapped_column(SmallInteger)
    valor_inicio: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    valor_fin: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    indicador: Mapped[IndicadorDiario] = relationship(
        back_populates="periodos", foreign_keys=[id_indicador], primaryjoin="PeriodoRelevante.id_indicador == IndicadorDiario.id_indicador"
    )


class Evento(Base):
    """Acontecimiento cotidiano registrado por el usuario (diccionario de datos, Tabla 25)."""

    __tablename__ = "evento"
    __table_args__ = (Index("ix_evento_usuario_fecha", "id_usuario", "fecha_hora"),)

    id_evento: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario", ondelete="CASCADE"))
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    hora_aproximada: Mapped[bool] = mapped_column(Boolean, default=False)
    # Texto en lenguaje natural tal como lo escribió la persona (HU-008). Vacío en la carga manual.
    texto_original: Mapped[str | None] = mapped_column(Text, nullable=True)
    tipo: Mapped[str] = mapped_column(String(25))  # comida | insulina | actividad_fisica | sintoma | otro
    descripcion: Mapped[str] = mapped_column(String(160))
    cantidad: Mapped[float | None] = mapped_column(Float, nullable=True)
    unidad: Mapped[str | None] = mapped_column(String(15), nullable=True)
    estado: Mapped[str] = mapped_column(String(12), default="confirmado")  # borrador | confirmado | descartado
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)


class ResumenDiario(Base):
    """Resumen del día en lenguaje coloquial, con versiones (diccionario de datos, Tabla 27)."""

    __tablename__ = "resumen_diario"
    __table_args__ = (
        UniqueConstraint("id_usuario", "fecha", "version"),
        # Un resumen solo puede referirse a indicadores de la misma persona (ver DER).
        ForeignKeyConstraint(
            ["id_indicador", "id_usuario"],
            ["indicador_diario.id_indicador", "indicador_diario.id_usuario"],
            ondelete="CASCADE",
        ),
    )

    id_resumen: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id_usuario", ondelete="CASCADE"), index=True)
    id_indicador: Mapped[int] = mapped_column(Integer)
    fecha: Mapped[date] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer)
    vigente: Mapped[bool] = mapped_column(Boolean, default=True)  # solo una por usuario y fecha
    texto_resumen: Mapped[str] = mapped_column(Text)
    estado_verificacion: Mapped[str] = mapped_column(String(15))  # aprobado | plantilla | desactualizado
    motivo_generacion: Mapped[str] = mapped_column(String(40))
    fecha_generacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    modelo_utilizado: Mapped[str] = mapped_column(String(60))
    # Motivos por los que la verificación automática rechazó el texto del modelo (si los hubo).
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
