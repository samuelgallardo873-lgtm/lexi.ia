"""Persistencia local de expedientes y actuaciones de LexBot."""

from contextlib import contextmanager
from datetime import date, datetime
import hashlib
import json
import re
import sqlite3

import ajustes

DB_PATH = ajustes.CARPETA / "lexbot.sqlite3"


def _extraer_oficina(texto):
    for linea in str(texto or "").splitlines():
        candidata = " ".join(linea.split())
        normalizada = candidata.casefold()
        if (normalizada.startswith("oficina ")
                and "asociada" in normalizada):
            return candidata
    return ""


def _fecha_movimiento(texto):
    """Interpreta las fechas usadas por SAE y devuelve su día calendario."""
    texto = str(texto or "").strip()
    if not texto:
        return None
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for formato in (
        "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(texto[:19], formato).date()
        except ValueError:
            continue
    return None


def _fecha_iso_citada(fecha_iso, texto):
    if fecha_iso in texto:
        return True
    patrones = (
        r"\b\d{1,2}[/.]\d{1,2}[/.]\d{4}\b",
        r"\b\d{1,2}-\d{1,2}-\d{4}\b",
        r"\b\d{1,2}\s+de\s+[a-záéíóú]+\s+(?:de|del)\s+\d{4}\b",
    )
    meses = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5,
        "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9,
        "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    }
    for patron in patrones:
        for coincidencia in re.finditer(patron, texto, flags=re.IGNORECASE):
            literal = coincidencia.group(0)
            fecha_literal = _fecha_movimiento(literal)
            if fecha_literal is None:
                partes = re.fullmatch(
                    r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+(?:de|del)\s+(\d{4})",
                    literal.casefold(),
                )
                if partes and partes.group(2) in meses:
                    try:
                        fecha_literal = date(
                            int(partes.group(3)), meses[partes.group(2)],
                            int(partes.group(1)),
                        )
                    except ValueError:
                        continue
            if fecha_literal is not None and fecha_literal.isoformat() == fecha_iso:
                return True
    return False


@contextmanager
def _conexion():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def inicializar():
    """Crea el esquema y migra instalaciones anteriores de forma idempotente."""
    with _conexion() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS expedientes (
                expediente TEXT PRIMARY KEY,
                caratula TEXT NOT NULL DEFAULT '',
                fuero TEXT NOT NULL DEFAULT '',
                juzgado TEXT NOT NULL DEFAULT '',
                oficina TEXT NOT NULL DEFAULT '',
                centro_judicial TEXT NOT NULL DEFAULT '',
                estado TEXT NOT NULL DEFAULT 'Activo',
                ultimo TEXT NOT NULL DEFAULT '',
                novedad TEXT NOT NULL DEFAULT '',
                sae_url TEXT NOT NULL DEFAULT '',
                fuente_sae INTEGER NOT NULL DEFAULT 0 CHECK (fuente_sae IN (0, 1)),
                monitorear INTEGER NOT NULL DEFAULT 1 CHECK (monitorear IN (0, 1)),
                actualizado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        columnas = {row["name"] for row in db.execute("PRAGMA table_info(expedientes)")}
        if "monitorear" not in columnas:
            db.execute(
                "ALTER TABLE expedientes "
                "ADD COLUMN monitorear INTEGER NOT NULL DEFAULT 1"
            )
        if "sae_url" not in columnas:
            db.execute(
                "ALTER TABLE expedientes ADD COLUMN sae_url TEXT NOT NULL DEFAULT ''"
            )
        if "fuente_sae" not in columnas:
            db.execute(
                "ALTER TABLE expedientes "
                "ADD COLUMN fuente_sae INTEGER NOT NULL DEFAULT 0"
            )
        if "centro_judicial" not in columnas:
            db.execute(
                "ALTER TABLE expedientes "
                "ADD COLUMN centro_judicial TEXT NOT NULL DEFAULT ''"
            )
        if "oficina" not in columnas:
            db.execute(
                "ALTER TABLE expedientes "
                "ADD COLUMN oficina TEXT NOT NULL DEFAULT ''"
            )
        db.execute("""
            CREATE TABLE IF NOT EXISTS novedades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expediente TEXT NOT NULL,
                fecha TEXT NOT NULL,
                tipo TEXT NOT NULL DEFAULT 'Actuación',
                titulo TEXT NOT NULL DEFAULT '',
                texto TEXT NOT NULL DEFAULT '',
                texto_completo INTEGER NOT NULL DEFAULT 0,
                hash TEXT NOT NULL UNIQUE,
                creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (expediente) REFERENCES expedientes(expediente)
                    ON DELETE CASCADE
            )
        """)
        columnas_novedades = {
            row["name"] for row in db.execute("PRAGMA table_info(novedades)")
        }
        if "texto_completo" not in columnas_novedades:
            db.execute(
                "ALTER TABLE novedades "
                "ADD COLUMN texto_completo INTEGER NOT NULL DEFAULT 0"
            )
        db.execute("""
            CREATE TABLE IF NOT EXISTS analisis_ia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                periodo_dias INTEGER NOT NULL CHECK (periodo_dias IN (1, 7, 30)),
                resumen TEXT NOT NULL,
                modelo TEXT NOT NULL,
                cantidad_fuentes INTEGER NOT NULL DEFAULT 0,
                creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        definicion_analisis = db.execute("""
            SELECT sql FROM sqlite_master
            WHERE type = 'table' AND name = 'analisis_ia'
        """).fetchone()["sql"]
        if not re.search(r"periodo_dias\s+IN\s*\(\s*1\s*,", definicion_analisis):
            db.execute("PRAGMA foreign_keys = OFF")
            db.execute("DROP TABLE IF EXISTS analisis_ia_nuevo")
            db.execute("""
                CREATE TABLE analisis_ia_nuevo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    periodo_dias INTEGER NOT NULL CHECK (periodo_dias IN (1, 7, 30)),
                    resumen TEXT NOT NULL,
                    modelo TEXT NOT NULL,
                    cantidad_fuentes INTEGER NOT NULL DEFAULT 0,
                    creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.execute("""
                INSERT INTO analisis_ia_nuevo
                    (id, periodo_dias, resumen, modelo, cantidad_fuentes, creada_en)
                SELECT id, periodo_dias, resumen, modelo, cantidad_fuentes, creada_en
                FROM analisis_ia
            """)
            db.execute("DROP TABLE analisis_ia")
            db.execute("ALTER TABLE analisis_ia_nuevo RENAME TO analisis_ia")
            db.execute("PRAGMA foreign_keys = ON")
        db.execute("""
            CREATE TABLE IF NOT EXISTS estado_fuentes_ia (
                novedad_id INTEGER PRIMARY KEY,
                hash_fuente TEXT NOT NULL,
                estado TEXT NOT NULL CHECK (
                    estado IN ('pendiente', 'procesada', 'fallida')
                ),
                analizada_en TEXT,
                codigo_error TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (novedad_id) REFERENCES novedades(id) ON DELETE CASCADE
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS hallazgos_ia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analisis_id INTEGER NOT NULL,
                novedad_id INTEGER NOT NULL,
                hash_fuente TEXT NOT NULL,
                expediente TEXT NOT NULL,
                categoria TEXT NOT NULL,
                titulo TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                fecha_detectada TEXT,
                fecha_original TEXT NOT NULL DEFAULT '',
                cita TEXT NOT NULL,
                certeza TEXT NOT NULL CHECK (
                    certeza IN ('explicit', 'inferred', 'unclear')
                ),
                confianza REAL NOT NULL CHECK (confianza BETWEEN 0 AND 1),
                estado TEXT NOT NULL DEFAULT 'nueva' CHECK (
                    estado IN ('nueva', 'revisada', 'agendada', 'descartada')
                ),
                aviso_id INTEGER,
                huella TEXT NOT NULL,
                creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analisis_id) REFERENCES analisis_ia(id) ON DELETE CASCADE,
                FOREIGN KEY (novedad_id) REFERENCES novedades(id) ON DELETE CASCADE,
                UNIQUE (novedad_id, huella)
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS preferencias (
                clave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS chats_lexi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL DEFAULT 'Nueva conversación',
                creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                actualizada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS mensajes_lexi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                rol TEXT NOT NULL CHECK (rol IN ('user', 'assistant')),
                contenido TEXT NOT NULL,
                creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES chats_lexi(id) ON DELETE CASCADE
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS avisos_calendario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                hora TEXT NOT NULL DEFAULT '09:00',
                titulo TEXT NOT NULL,
                detalle TEXT NOT NULL DEFAULT '',
                creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        columnas_mensajes = {
            row["name"] for row in db.execute("PRAGMA table_info(mensajes_lexi)")
        }
        if "fuentes" not in columnas_mensajes:
            db.execute(
                "ALTER TABLE mensajes_lexi "
                "ADD COLUMN fuentes TEXT NOT NULL DEFAULT '[]'"
            )
        columnas_avisos = {
            row["name"] for row in db.execute("PRAGMA table_info(avisos_calendario)")
        }
        if "hallazgo_ia_id" not in columnas_avisos:
            db.execute(
                "ALTER TABLE avisos_calendario ADD COLUMN hallazgo_ia_id INTEGER"
            )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_mensajes_lexi_chat "
            "ON mensajes_lexi (chat_id, id)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_novedades_expediente_fecha "
            "ON novedades (expediente, fecha DESC)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_hallazgos_ia_estado "
            "ON hallazgos_ia (estado, creada_en DESC)"
        )
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_avisos_hallazgo_ia "
            "ON avisos_calendario (hallazgo_ia_id) "
            "WHERE hallazgo_ia_id IS NOT NULL"
        )
        expedientes_sin_oficina = db.execute("""
            SELECT e.expediente
            FROM expedientes AS e
            WHERE e.oficina = ''
        """).fetchall()
        for fila in expedientes_sin_oficina:
            textos = db.execute("""
                SELECT texto
                FROM novedades
                WHERE expediente = ?
                ORDER BY fecha DESC, id DESC
                LIMIT 5
            """, (fila["expediente"],)).fetchall()
            oficina = next(
                (nombre for nombre in
                 (_extraer_oficina(texto["texto"]) for texto in textos)
                 if nombre),
                "",
            )
            if oficina:
                db.execute(
                    "UPDATE expedientes SET oficina = ? WHERE expediente = ?",
                    (oficina, fila["expediente"]),
                )


def listar_expedientes(solo_monitoreados=False, solo_sae=True):
    inicializar()
    filtros = []
    if solo_sae:
        filtros.append("fuente_sae = 1")
    if solo_monitoreados:
        filtros.append("monitorear = 1")
    consulta = "SELECT * FROM expedientes"
    if filtros:
        consulta += " WHERE " + " AND ".join(filtros)
    consulta += " ORDER BY expediente"
    with _conexion() as db:
        return [dict(row) for row in db.execute(consulta)]


def guardar_expediente(datos, desde_sae=False):
    numero = str(datos.get("expediente", "")).strip()
    if not numero:
        raise ValueError("El número de expediente no puede estar vacío.")
    valores = (
        numero,
        str(datos.get("caratula", "")),
        str(datos.get("fuero", "")),
        str(datos.get("juzgado", "")),
        str(datos.get("oficina", "")),
        str(datos.get("centro_judicial", "")),
        str(datos.get("estado", "Activo")),
        str(datos.get("ultimo", "")),
        str(datos.get("novedad", "")),
        str(datos.get("sae_url", "")),
        int(desde_sae),
    )
    inicializar()
    with _conexion() as db:
        db.execute("""
            INSERT INTO expedientes
                (expediente, caratula, fuero, juzgado, oficina,
                 centro_judicial, estado, ultimo, novedad,
                 sae_url, fuente_sae)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(expediente) DO UPDATE SET
                caratula = excluded.caratula,
                fuero = excluded.fuero,
                juzgado = excluded.juzgado,
                oficina = COALESCE(
                    NULLIF(excluded.oficina, ''), expedientes.oficina
                ),
                centro_judicial = COALESCE(
                    NULLIF(excluded.centro_judicial, ''), expedientes.centro_judicial
                ),
                estado = excluded.estado,
                ultimo = excluded.ultimo,
                novedad = excluded.novedad,
                sae_url = excluded.sae_url,
                fuente_sae = MAX(expedientes.fuente_sae, excluded.fuente_sae),
                actualizado_en = CURRENT_TIMESTAMP
        """, valores)


def crear_expediente_manual(datos):
    """Registra un expediente aportado por el usuario, sin marcarlo como SAE."""
    numero = str(datos.get("expediente", "")).strip()
    if not numero:
        raise ValueError("El número de expediente no puede estar vacío.")
    inicializar()
    with _conexion() as db:
        try:
            db.execute("""
                INSERT INTO expedientes
                    (expediente, caratula, fuero, centro_judicial, estado,
                     fuente_sae, monitorear)
                VALUES (?, ?, ?, ?, 'Activo', 0, 1)
            """, (
                numero,
                str(datos.get("caratula", "")).strip(),
                str(datos.get("fuero", "")).strip(),
                str(datos.get("centro_judicial", "")).strip(),
            ))
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed: expedientes.expediente" in str(exc):
                raise ValueError(
                    f"El expediente {numero} ya está registrado."
                ) from exc
            raise
    return next(
        item for item in listar_expedientes(solo_sae=False)
        if item["expediente"] == numero
    )


def actualizar_monitoreo(expediente, monitorear):
    inicializar()
    with _conexion() as db:
        cursor = db.execute(
            "UPDATE expedientes SET monitorear = ?, actualizado_en = CURRENT_TIMESTAMP "
            "WHERE expediente = ?",
            (int(bool(monitorear)), str(expediente)),
        )
        if cursor.rowcount != 1:
            raise LookupError(f"No existe el expediente {expediente!r}.")


def guardar_novedad(actuacion):
    """Inserta una actuación solo una vez; devuelve True si fue nueva."""
    numero = str(actuacion["expediente"]).strip()
    fecha = str(actuacion.get("fecha", "")).strip()
    tipo = str(actuacion.get("tipo") or "Actuación").strip()
    titulo = str(actuacion.get("titulo", "")).strip()
    texto = str(actuacion.get("texto", "")).strip()
    oficina = _extraer_oficina(texto)
    texto_completo = int(bool(actuacion.get("texto_completo", False)))
    if not numero or not fecha or not (titulo or texto):
        raise ValueError("La actuación debe incluir expediente, fecha y contenido.")

    identidad = "\x1f".join((numero, fecha, tipo, titulo, texto))
    digest = hashlib.sha256(identidad.encode("utf-8")).hexdigest()
    inicializar()
    with _conexion() as db:
        if oficina:
            db.execute(
                "UPDATE expedientes SET oficina = ? "
                "WHERE expediente = ? AND oficina = ''",
                (oficina, numero),
            )
        previa = db.execute("""
            SELECT id, texto, texto_completo
            FROM novedades
            WHERE expediente = ? AND fecha = ? AND tipo = ? AND titulo = ?
            ORDER BY id DESC
            LIMIT 1
        """, (numero, fecha, tipo, titulo)).fetchone()
        if previa is not None and (
            texto_completo
            or len(texto) > len(previa["texto"])
        ):
            db.execute(
                "UPDATE novedades "
                "SET texto = ?, texto_completo = MAX(texto_completo, ?), hash = ? "
                "WHERE id = ?",
                (texto, texto_completo, digest, previa["id"]),
            )
            return False

        cursor = db.execute("""
            INSERT OR IGNORE INTO novedades
                (expediente, fecha, tipo, titulo, texto, texto_completo, hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            numero, fecha, tipo, titulo, texto, texto_completo, digest,
        ))
        if cursor.rowcount:
            anterior = db.execute(
                "SELECT ultimo FROM expedientes WHERE expediente = ?", (numero,)
            ).fetchone()
            fecha_nueva = _fecha_movimiento(fecha)
            fecha_anterior = _fecha_movimiento(anterior["ultimo"]) if anterior else None
            if fecha_nueva is not None and (
                fecha_anterior is None or fecha_nueva >= fecha_anterior
            ):
                db.execute("""
                    UPDATE expedientes
                    SET ultimo = ?, novedad = ?, actualizado_en = CURRENT_TIMESTAMP
                    WHERE expediente = ?
                """, (fecha, titulo or texto, numero))
        return bool(cursor.rowcount)


def listar_novedades(
        limite=100, solo_monitoreados=True, expediente=None,
        solo_ultima_por_expediente=False):
    inicializar()
    filtros = ["e.fuente_sae = 1"]
    if solo_monitoreados:
        filtros.append("e.monitorear = 1")
    if expediente is not None:
        filtros.append("e.expediente = ?")
    if solo_ultima_por_expediente:
        filtros.append("""
            NOT EXISTS (
                SELECT 1
                FROM novedades AS posterior
                WHERE posterior.expediente = n.expediente
                  AND (
                      posterior.fecha > n.fecha
                      OR (posterior.fecha = n.fecha AND posterior.id > n.id)
                  )
            )
        """)
    params = [str(expediente)] if expediente is not None else []
    consulta = f"""
        SELECT n.id, n.hash, n.creada_en, n.expediente, n.fecha, n.tipo,
               n.titulo, n.texto, n.texto_completo,
               e.caratula, e.fuero, e.juzgado
        FROM novedades AS n
        JOIN expedientes AS e ON e.expediente = n.expediente
        WHERE {" AND ".join(filtros)}
        ORDER BY n.fecha DESC, n.id DESC
    """
    if limite is not None:
        consulta += " LIMIT ?"
        params.append(int(limite))
    with _conexion() as db:
        return [dict(row) for row in db.execute(consulta, params)]


def _fuentes_ia_desde_filas(filas):
    return [
        {
            "id": row["id"],
            "hash": row["hash"],
            "expediente": row["expediente"],
            "caratula": row["caratula"] or "",
            "fuero": row["fuero"] or "",
            "juzgado": row["juzgado"] or "",
            "fecha": row["fecha"],
            "creada_en": row["creada_en"],
            "titulo": row["titulo"] or row["tipo"] or "Actuación",
            "texto": row["texto"],
        }
        for row in filas
    ]


def _consulta_solicita_todas_las_novedades(consulta):
    texto = str(consulta).casefold()
    texto = re.sub(r"[¿?¡!.,;:]", " ", texto)
    tiene_todas = any(
        expresion in texto
        for expresion in (
            "todos", "todas", "cada expediente", "cada uno",
            "de los expedientes", "de mis expedientes", "de mis causas",
        )
    )
    tiene_novedades = any(
        palabra in texto
        for palabra in (
            "novedad", "actuacion", "actuación", "movimiento",
            "ultima", "última", "ultimo", "último", "reciente",
        )
    )
    pide_resumen_general = any(
        expresion in texto
        for expresion in (
            "ultimas novedades", "últimas novedades",
            "ultima novedad", "última novedad",
            "novedades recientes", "ultimos movimientos",
            "últimos movimientos", "ultimas actuaciones",
            "últimas actuaciones", "dame todas las",
            "decime todas las", "mostrame todas las",
        )
    )
    return tiene_novedades and (tiene_todas or pide_resumen_general)


def buscar_fuentes_ia(consulta, limite=8):
    """Recupera únicamente actuaciones locales relacionadas con la pregunta."""
    inicializar()
    consulta = str(consulta).strip()
    todas_las_novedades = _consulta_solicita_todas_las_novedades(consulta)
    expediente = re.search(r"(?<!\w)(\d{2,7}/\d{2,4})(?!\w)", consulta)
    if todas_las_novedades and not expediente:
        filas = listar_novedades(
            limite=None,
            solo_monitoreados=True,
            solo_ultima_por_expediente=True,
        )
        fuentes = _fuentes_ia_desde_filas(filas)
        for fuente in fuentes:
            if not str(fuente["texto"] or "").strip():
                fuente["texto"] = (
                    "No hay texto disponible para la actuación más reciente; "
                    f"solo consta el título: {fuente['titulo']}."
                )
        return fuentes

    palabras = list(dict.fromkeys(
        palabra.casefold()
        for palabra in re.findall(r"[\wáéíóúüñ/-]{3,}", consulta)
        if palabra.casefold() not in {
            "que", "qué", "cual", "cuál", "como", "cómo", "cuando", "cuándo",
            "donde", "dónde", "sobre", "para", "desde", "hasta", "expediente",
            "expedientes", "actuacion", "actuación", "actuaciones", "decime",
            "decir", "mostrar", "informacion", "información", "tengo",
            "ultimo", "último", "ultima", "última", "movimiento", "movimientos",
            "resumen", "resumir", "reciente", "recientes", "novedad", "novedades",
        }
    ))[:10]
    filtros = ["e.fuente_sae = 1", "e.monitorear = 1", "trim(n.texto) <> ''"]
    parametros = []
    if expediente:
        filtros.append("e.expediente = ?")
        parametros.append(expediente.group(1))
    elif palabras:
        condiciones = []
        for palabra in palabras:
            condiciones.append(
                "(n.texto LIKE ? OR n.titulo LIKE ? OR e.caratula LIKE ? "
                "OR e.expediente LIKE ?)"
            )
            parametro = f"%{palabra}%"
            parametros.extend([parametro] * 4)
        filtros.append("(" + " OR ".join(condiciones) + ")")
    consulta_sql = f"""
        SELECT n.id, n.hash, n.expediente, n.fecha, n.creada_en, n.tipo,
               n.titulo, n.texto, e.caratula, e.fuero, e.juzgado
        FROM novedades AS n
        JOIN expedientes AS e ON e.expediente = n.expediente
        WHERE {" AND ".join(filtros)}
        ORDER BY n.fecha DESC, n.id DESC
        LIMIT ?
    """
    parametros.append(max(int(limite), 1) if expediente else max(int(limite) * 8, 32))
    with _conexion() as db:
        filas = db.execute(consulta_sql, parametros).fetchall()
    fuentes = _fuentes_ia_desde_filas(filas)
    if palabras and not expediente:
        def puntuacion(fuente):
            valores = " ".join((
                fuente["texto"], fuente["titulo"], fuente["caratula"],
                fuente["expediente"],
            )).casefold()
            return sum(valores.count(palabra) for palabra in palabras)

        fuentes.sort(key=lambda fuente: (
            puntuacion(fuente), fuente["fecha"], fuente["id"]), reverse=True)
    return fuentes[:int(limite)]


def listar_fuentes_para_resumen_ia(periodo_dias, limite=20):
    """Carga fuentes por fecha de incorporación, no por fecha judicial."""
    if periodo_dias not in (1, 7, 30):
        raise ValueError("El período del resumen debe ser de 24 horas, 7 o 30 días.")
    inicializar()
    with _conexion() as db:
        filas = db.execute("""
            SELECT n.id, n.hash, n.expediente, n.fecha, n.creada_en, n.tipo,
                   n.titulo, n.texto, e.caratula, e.fuero, e.juzgado
            FROM novedades AS n
            JOIN expedientes AS e ON e.expediente = n.expediente
            WHERE e.fuente_sae = 1 AND e.monitorear = 1
              AND trim(n.texto) <> ''
              AND n.creada_en >= datetime('now', ?)
            ORDER BY n.creada_en DESC, n.id DESC
            LIMIT ?
        """, (f"-{periodo_dias} days", int(limite))).fetchall()
    return _fuentes_ia_desde_filas(filas)


def actualizar_estado_fuentes_ia(fuentes, estado, codigo_error=""):
    if estado not in {"pendiente", "procesada", "fallida"}:
        raise ValueError("Estado de análisis IA no válido.")
    inicializar()
    with _conexion() as db:
        for fuente in fuentes:
            db.execute("""
                INSERT INTO estado_fuentes_ia
                    (novedad_id, hash_fuente, estado, analizada_en, codigo_error)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
                ON CONFLICT(novedad_id) DO UPDATE SET
                    hash_fuente = excluded.hash_fuente,
                    estado = excluded.estado,
                    analizada_en = CURRENT_TIMESTAMP,
                    codigo_error = excluded.codigo_error
            """, (
                int(fuente["id"]), str(fuente["hash"]), estado,
                str(codigo_error)[:80],
            ))


def guardar_analisis_ia(periodo_dias, resumen, modelo, fuentes, hallazgos):
    """Persiste un informe acotado y solo hallazgos con citas de sus fuentes."""
    if periodo_dias not in (1, 7, 30):
        raise ValueError("El período debe ser de 24 horas, 7 o 30 días.")
    resumen = str(resumen).strip()
    modelo = str(modelo).strip()
    if not resumen or not modelo:
        raise ValueError("El análisis debe incluir resumen y modelo.")
    fuentes_por_id = {int(fuente["id"]): fuente for fuente in fuentes}
    inicializar()
    with _conexion() as db:
        for fuente in fuentes_por_id.values():
            actual = db.execute(
                "SELECT hash FROM novedades WHERE id = ?", (fuente["id"],)
            ).fetchone()
            if actual is None or actual["hash"] != fuente["hash"]:
                raise ValueError(
                    "Una actuación cambió mientras se analizaba; vuelve a generar el resumen."
                )
        cursor = db.execute("""
            INSERT INTO analisis_ia
                (periodo_dias, resumen, modelo, cantidad_fuentes)
            VALUES (?, ?, ?, ?)
        """, (periodo_dias, resumen, modelo, len(fuentes_por_id)))
        analisis_id = cursor.lastrowid
        for fuente in fuentes_por_id.values():
            db.execute("""
                INSERT INTO estado_fuentes_ia
                    (novedad_id, hash_fuente, estado, analizada_en, codigo_error)
                VALUES (?, ?, 'procesada', CURRENT_TIMESTAMP, '')
                ON CONFLICT(novedad_id) DO UPDATE SET
                    hash_fuente = excluded.hash_fuente,
                    estado = 'procesada',
                    analizada_en = CURRENT_TIMESTAMP,
                    codigo_error = ''
            """, (fuente["id"], fuente["hash"]))

        for hallazgo in hallazgos:
            fuente = fuentes_por_id.get(int(hallazgo["source"]["id"]))
            if fuente is None:
                continue
            cita = " ".join(str(hallazgo.get("evidence_quote", "")).split())
            texto = " ".join(str(fuente["texto"]).split())
            if not cita or cita.casefold() not in texto.casefold():
                continue
            fecha_detectada = hallazgo.get("event_date")
            if fecha_detectada is not None:
                try:
                    fecha_detectada = date.fromisoformat(fecha_detectada).isoformat()
                except (TypeError, ValueError):
                    continue
                if not _fecha_iso_citada(fecha_detectada, cita):
                    continue
            identidad = json.dumps([
                hallazgo.get("category", ""),
                str(hallazgo.get("title", "")).strip().casefold(),
                fecha_detectada,
                cita.casefold(),
            ], ensure_ascii=False, separators=(",", ":"))
            huella = hashlib.sha256(identidad.encode("utf-8")).hexdigest()
            db.execute("""
                INSERT INTO hallazgos_ia (
                    analisis_id, novedad_id, hash_fuente, expediente,
                    categoria, titulo, descripcion, fecha_detectada,
                    fecha_original, cita, certeza, confianza, huella
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(novedad_id, huella) DO UPDATE SET
                    analisis_id = excluded.analisis_id,
                    hash_fuente = excluded.hash_fuente,
                    descripcion = excluded.descripcion,
                    confianza = excluded.confianza
            """, (
                analisis_id, fuente["id"], fuente["hash"], fuente["expediente"],
                hallazgo["category"], str(hallazgo["title"]).strip(),
                str(hallazgo["description"]).strip(), fecha_detectada,
                str(hallazgo.get("date_text", "")).strip(), cita,
                hallazgo["certainty"],
                max(0.0, min(float(hallazgo["confidence"]), 1.0)), huella,
            ))
    return analisis_id


def listar_analisis_ia(limite=20):
    inicializar()
    with _conexion() as db:
        return [
            dict(fila) for fila in db.execute("""
                SELECT id, periodo_dias, resumen, modelo, cantidad_fuentes, creada_en
                FROM analisis_ia
                ORDER BY creada_en DESC, id DESC
                LIMIT ?
            """, (int(limite),))
        ]


def listar_hallazgos_ia(estado=None, solo_con_fecha=False):
    inicializar()
    filtros = []
    parametros = []
    if estado is not None and estado != "todos":
        filtros.append("h.estado = ?")
        parametros.append(str(estado))
    if solo_con_fecha:
        filtros.append("h.fecha_detectada IS NOT NULL")
    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    with _conexion() as db:
        return [
            dict(fila) for fila in db.execute(f"""
                SELECT h.*, n.fecha AS fecha_actuacion, n.titulo AS titulo_actuacion
                FROM hallazgos_ia AS h
                JOIN novedades AS n ON n.id = h.novedad_id
                AND n.hash = h.hash_fuente
                {where}
                ORDER BY h.creada_en DESC, h.id DESC
            """, parametros)
        ]


def descartar_hallazgo_ia(hallazgo_id):
    inicializar()
    with _conexion() as db:
        cursor = db.execute("""
            UPDATE hallazgos_ia SET estado = 'descartada'
            WHERE id = ? AND estado = 'nueva'
        """, (int(hallazgo_id),))
        if cursor.rowcount != 1:
            raise LookupError("El hallazgo ya no está pendiente de revisión.")


def agendar_hallazgo_ia(hallazgo_id, fecha, titulo, hora="09:00", detalle=""):
    """Confirma una sugerencia IA tras revisión explícita y crea un único aviso."""
    fecha = fecha.isoformat() if isinstance(fecha, date) else str(fecha).strip()
    try:
        fecha = date.fromisoformat(fecha).isoformat()
    except ValueError as exc:
        raise ValueError("La fecha debe tener el formato AAAA-MM-DD.") from exc
    titulo, hora, detalle = str(titulo).strip(), str(hora).strip(), str(detalle).strip()
    if not titulo:
        raise ValueError("El título del aviso no puede estar vacío.")
    try:
        datetime.strptime(hora, "%H:%M")
    except ValueError as exc:
        raise ValueError("La hora debe tener el formato HH:MM.") from exc

    inicializar()
    with _conexion() as db:
        hallazgo = db.execute("""
            SELECT h.id, h.estado, h.aviso_id, h.hash_fuente, n.hash AS hash_actual
            FROM hallazgos_ia AS h
            JOIN novedades AS n ON n.id = h.novedad_id
            WHERE h.id = ?
        """, (int(hallazgo_id),)).fetchone()
        if hallazgo is None:
            raise LookupError("No se encontró la sugerencia de LEXI.")
        if hallazgo["hash_fuente"] != hallazgo["hash_actual"]:
            raise ValueError(
                "La actuación cambió desde el análisis; genera un resumen nuevo."
            )
        if hallazgo["estado"] == "descartada":
            raise ValueError("La sugerencia fue descartada y no puede agendarse.")
        if hallazgo["aviso_id"] is not None:
            aviso = db.execute(
                "SELECT id, fecha, hora, titulo, detalle "
                "FROM avisos_calendario WHERE id = ?",
                (hallazgo["aviso_id"],),
            ).fetchone()
            if aviso is not None:
                return {
                    **dict(aviso),
                    "fecha": date.fromisoformat(aviso["fecha"]),
                    "expediente": "",
                    "caratula": aviso["titulo"],
                    "diligencia": aviso["detalle"],
                    "prioridad": "habil",
                    "es_actuacion": False,
                    "es_aviso": True,
                }
        cursor = db.execute("""
            INSERT INTO avisos_calendario
                (fecha, hora, titulo, detalle, hallazgo_ia_id)
            VALUES (?, ?, ?, ?, ?)
        """, (fecha, hora, titulo, detalle, int(hallazgo_id)))
        aviso_id = cursor.lastrowid
        db.execute("""
            UPDATE hallazgos_ia SET estado = 'agendada', aviso_id = ?
            WHERE id = ?
        """, (aviso_id, int(hallazgo_id)))
    return {
        "id": aviso_id, "fecha": date.fromisoformat(fecha), "hora": hora,
        "expediente": "", "caratula": titulo, "diligencia": detalle,
        "prioridad": "habil", "es_actuacion": False, "es_aviso": True,
    }


def novedades_para_dashboard(limite=None):
    items = []
    for row in listar_novedades(
            limite=limite, solo_ultima_por_expediente=True):
        items.append({
            "expediente": row["expediente"],
            "caratula": row["caratula"] or row["titulo"] or row["expediente"],
            "titulo": row["titulo"] or row["texto"] or "Actuación registrada",
            "fuero": row["fuero"] or "SAE",
            "fecha": row["fecha"],
            "prioridad": "info",
            "resumen": row["texto"] or row["titulo"],
            "limite": "Sin plazo calculado; verificar el proveído original en el SAE.",
        })
    return items


def obtener_expediente(expediente):
    """Devuelve un expediente local por número o informa si no está registrado."""
    inicializar()
    with _conexion() as db:
        row = db.execute(
            "SELECT * FROM expedientes WHERE expediente = ?",
            (str(expediente).strip(),),
        ).fetchone()
    if row is None:
        raise LookupError(f"No existe el expediente {expediente!r}.")
    return dict(row)


def novedades_para_calendario():
    """Devuelve fechas de actuaciones, sin interpretarlas como vencimientos."""
    eventos = []
    for row in listar_novedades():
        try:
            fecha_evento = datetime.fromisoformat(row["fecha"].replace("Z", "+00:00")).date()
        except ValueError:
            try:
                fecha_evento = date.fromisoformat(row["fecha"][:10])
            except ValueError:
                continue
        eventos.append({
            "fecha": fecha_evento,
            "hora": row["fecha"][11:16] if len(row["fecha"]) >= 16 else "—",
            "expediente": row["expediente"],
            "caratula": row["caratula"] or row["expediente"],
            "diligencia": row["titulo"] or row["texto"],
            "prioridad": "info",
            "es_actuacion": True,
        })
    with _conexion() as db:
        avisos = db.execute("""
            SELECT id, fecha, hora, titulo, detalle
            FROM avisos_calendario
            ORDER BY fecha, hora, id
        """).fetchall()
    for aviso in avisos:
        eventos.append({
            "id": aviso["id"],
            "fecha": date.fromisoformat(aviso["fecha"]),
            "hora": aviso["hora"],
            "expediente": "",
            "caratula": aviso["titulo"],
            "diligencia": aviso["detalle"],
            "prioridad": "habil",
            "es_actuacion": False,
            "es_aviso": True,
        })
    for hallazgo in listar_hallazgos_ia(estado="nueva", solo_con_fecha=True):
        try:
            fecha_evento = date.fromisoformat(hallazgo["fecha_detectada"])
        except (TypeError, ValueError):
            continue
        eventos.append({
            "id": hallazgo["id"],
            "fecha": fecha_evento,
            "hora": "—",
            "expediente": hallazgo["expediente"],
            "caratula": hallazgo["titulo"],
            "diligencia": (
                f"{hallazgo['descripcion']}\nCita: {hallazgo['cita']}"
            ),
            "prioridad": "ia",
            "es_actuacion": False,
            "es_aviso": False,
            "es_sugerencia_ia": True,
            "cita": hallazgo["cita"],
            "fecha_original": hallazgo["fecha_original"],
        })
    return eventos


def alertas_por_inactividad(hoy=None):
    """Calcula avisos de inactividad solo a partir de movimientos guardados."""
    hoy = hoy or date.today()
    fechas_por_expediente = {}
    with _conexion() as db:
        fechas = db.execute("""
            SELECT n.expediente, n.fecha
            FROM novedades AS n
            JOIN expedientes AS e ON e.expediente = n.expediente
            WHERE e.fuente_sae = 1 AND e.monitorear = 1
        """).fetchall()
    for fila in fechas:
        fecha = _fecha_movimiento(fila["fecha"])
        if fecha is not None and fecha <= hoy:
            numero = fila["expediente"]
            if numero not in fechas_por_expediente or fecha > fechas_por_expediente[numero]:
                fechas_por_expediente[numero] = fecha

    alertas = []
    for expediente in listar_expedientes(solo_monitoreados=True):
        numero = expediente["expediente"]
        fecha_movimiento = fechas_por_expediente.get(numero)
        if fecha_movimiento is None:
            fecha_movimiento = _fecha_movimiento(expediente.get("ultimo"))
        if fecha_movimiento is None:
            continue
        dias = (hoy - fecha_movimiento).days
        if dias < 0:
            continue
        alertas.append({
            "expediente": numero,
            "caratula": expediente["caratula"] or numero,
            "juzgado": expediente["juzgado"],
            "dias": dias,
        })
    return alertas


def guardar_aviso_calendario(fecha, titulo, hora="09:00", detalle=""):
    """Guarda un aviso personal del calendario y devuelve el evento creado."""
    if isinstance(fecha, datetime):
        fecha = fecha.date().isoformat()
    elif isinstance(fecha, date):
        fecha = fecha.isoformat()
    else:
        fecha = str(fecha).strip()
    try:
        fecha_validada = date.fromisoformat(fecha)
    except ValueError as exc:
        raise ValueError("La fecha del aviso debe tener el formato AAAA-MM-DD.") from exc

    titulo = str(titulo).strip()
    hora = str(hora).strip()
    detalle = str(detalle).strip()
    if not titulo:
        raise ValueError("El título del aviso no puede estar vacío.")
    try:
        datetime.strptime(hora, "%H:%M")
    except ValueError as exc:
        raise ValueError("La hora del aviso debe tener el formato HH:MM.") from exc

    inicializar()
    with _conexion() as db:
        cursor = db.execute(
            "INSERT INTO avisos_calendario (fecha, hora, titulo, detalle) "
            "VALUES (?, ?, ?, ?)",
            (fecha_validada.isoformat(), hora, titulo, detalle),
        )
        aviso_id = cursor.lastrowid
    return {
        "id": aviso_id,
        "fecha": fecha_validada,
        "hora": hora,
        "expediente": "",
        "caratula": titulo,
        "diligencia": detalle,
        "prioridad": "habil",
        "es_actuacion": False,
        "es_aviso": True,
    }


def eliminar_aviso_calendario(aviso_id):
    """Elimina un aviso personal existente o informa que no se encontró."""
    inicializar()
    with _conexion() as db:
        db.execute("""
            UPDATE hallazgos_ia
            SET estado = 'descartada', aviso_id = NULL
            WHERE aviso_id = ?
        """, (int(aviso_id),))
        cursor = db.execute(
            "DELETE FROM avisos_calendario WHERE id = ?", (int(aviso_id),)
        )
        if cursor.rowcount != 1:
            raise LookupError(f"No existe el aviso de calendario {aviso_id!r}.")


def guardar_preferencias(datos):
    inicializar()
    with _conexion() as db:
        for clave, valor in datos.items():
            db.execute(
                "INSERT INTO preferencias (clave, valor) VALUES (?, ?) "
                "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
                (str(clave), json.dumps(valor, ensure_ascii=False)),
            )


def leer_preferencias():
    inicializar()
    with _conexion() as db:
        return {
            row["clave"]: json.loads(row["valor"])
            for row in db.execute("SELECT clave, valor FROM preferencias")
        }


def crear_chat_lexi():
    """Crea una conversación vacía y devuelve su identificador."""
    inicializar()
    with _conexion() as db:
        cursor = db.execute("INSERT INTO chats_lexi DEFAULT VALUES")
        return cursor.lastrowid


def listar_chats_lexi():
    """Devuelve las conversaciones, de la más recientemente actualizada a la más vieja."""
    inicializar()
    with _conexion() as db:
        return [
            dict(row)
            for row in db.execute(
                "SELECT id, titulo, creada_en, actualizada_en "
                "FROM chats_lexi ORDER BY actualizada_en DESC, id DESC"
            )
        ]


def listar_mensajes_lexi(chat_id):
    """Devuelve los mensajes en orden de envío o informa si el chat no existe."""
    inicializar()
    with _conexion() as db:
        existe = db.execute(
            "SELECT 1 FROM chats_lexi WHERE id = ?", (chat_id,)
        ).fetchone()
        if existe is None:
            raise LookupError(f"No existe la conversación {chat_id!r}.")
        mensajes = [
            dict(row)
            for row in db.execute(
                "SELECT id, chat_id, rol, contenido, fuentes, creada_en "
                "FROM mensajes_lexi WHERE chat_id = ? ORDER BY id",
                (chat_id,),
            )
        ]
    for mensaje in mensajes:
        mensaje["fuentes"] = json.loads(mensaje["fuentes"])
    return mensajes


def guardar_mensaje_lexi(chat_id, rol, contenido, fuentes=None):
    """Guarda un mensaje local y titula la conversación con la primera consulta."""
    rol = str(rol).strip()
    contenido = str(contenido).strip()
    if rol not in {"user", "assistant"}:
        raise ValueError("El rol del mensaje debe ser 'user' o 'assistant'.")
    if not contenido:
        raise ValueError("El mensaje no puede estar vacío.")

    inicializar()
    with _conexion() as db:
        chat = db.execute(
            "SELECT titulo FROM chats_lexi WHERE id = ?", (chat_id,)
        ).fetchone()
        if chat is None:
            raise LookupError(f"No existe la conversación {chat_id!r}.")

        cantidad = db.execute(
            "SELECT COUNT(*) FROM mensajes_lexi WHERE chat_id = ?", (chat_id,)
        ).fetchone()[0]
        db.execute(
            "INSERT INTO mensajes_lexi "
            "(chat_id, rol, contenido, fuentes) VALUES (?, ?, ?, ?)",
            (
                chat_id, rol, contenido,
                json.dumps(fuentes or [], ensure_ascii=False),
            ),
        )

        if rol == "user" and cantidad == 0:
            titulo = " ".join(contenido.split())
            if len(titulo) > 48:
                titulo = titulo[:47].rstrip() + "…"
            db.execute(
                "UPDATE chats_lexi SET titulo = ?, "
                "actualizada_en = strftime('%Y-%m-%d %H:%M:%f', 'now') "
                "WHERE id = ?",
                (titulo, chat_id),
            )
        else:
            db.execute(
                "UPDATE chats_lexi "
                "SET actualizada_en = strftime('%Y-%m-%d %H:%M:%f', 'now') "
                "WHERE id = ?",
                (chat_id,),
            )
