# LEXI con IA local

LEXI usa Ollama en el mismo equipo; el servicio de la aplicación solo acepta
`localhost`, desactiva proxies HTTP y rechaza redirecciones. Las preguntas,
actuaciones y respuestas no se envían a proveedores externos.

## Inicio

Instala Ollama y descarga un modelo una sola vez:

```powershell
ollama pull qwen3:4b
ollama serve
```

En Windows, Ollama puede quedar ejecutándose desde su aplicación de escritorio.
LEXI usa `qwen3:4b` por defecto y consulta `http://127.0.0.1:11434`. Si eliges
otro modelo local, define `LEXI_OLLAMA_MODEL` en el entorno antes de iniciar
LexBot. `LEXI_OLLAMA_URL` permite elegir otra dirección solo si sigue siendo
`localhost`.

Si Ollama no está disponible o falta el modelo, LEXI muestra el error y permite
volver a intentarlo después de iniciar el servicio o instalarlo.

## Fuentes y revisión

- Las consultas recuperan actuaciones SAE guardadas localmente de expedientes
  SAE que siguen monitoreados. Los expedientes agregados manualmente no se usan
  como fuentes de documentos.
- El chat limita las búsquedas específicas a 8 actuaciones y el resumen a 20.
  Una consulta general por las últimas novedades recupera la actuación más
  reciente de cada expediente SAE monitoreado y las procesa en lotes de hasta
  3 expedientes. Cada actuación enviada al modelo se limita a 3.500 caracteres
  y cada lote a 8.500 caracteres.
- Las fechas completas se contrastan con el texto citado. Cuando aparecen junto
  a referencias a audiencias, plazos u otras diligencias, pueden mostrarse como
  sugerencias para revisión; esa detección no confirma que correspondan a un
  vencimiento.
- Los resúmenes usan la fecha de incorporación de la actuación para el período,
  no la fecha judicial que aparece en el documento. El acceso rápido del
  Dashboard resume las últimas 24 horas; LEXI también permite elegir 7 o 30
  días.
- No hay PDFs o adjuntos descargados disponibles para el modelo. Las referencias
  apuntan a la actuación local, con expediente, fecha y título.
- LEXI no calcula vencimientos definitivos. Las fechas encontradas en
  actuaciones siguen siendo sugerencias que una persona debe revisar y
  confirmar. En cambio, una instrucción explícita para agendar una cita o
  reunión crea un aviso personal automáticamente solo si incluye fecha y hora
  claras; si falta alguno de esos datos, LEXI los solicita y no crea el evento.
- Chats, citas, análisis y estados de revisión se guardan en la base SQLite
  local de LexBot. Esta versión no incorpora permisos por usuario ni
  autenticación adicional dentro de LexBot. Las citas se conservan como
  metadatos internos y no se muestran como un bloque técnico en el chat.
