# Datos de prueba (sintéticos)

Archivos generados a partir de una simulación de **simglucose** (modelo UVA/Padova, paciente
virtual `adult#001`, escenario de comidas aleatorio, 38 días: del 02/10 al 08/11). No contienen datos de personas
reales. Se exportaron con la estructura de cada formato del Anexo I.

| Archivo | Formato | Período | Resultado esperado |
|---|---|---|---|
| `libreview_14dias.csv` | LibreView | 02/10 – 15/10 | Pide confirmar el formato de fecha: elegir **Mes, día y año**. Aceptado: 1.384 mediciones (1.344 del historial cada 15 min + 40 escaneos). 5 escaneos coinciden con un valor histórico y se descartan; las notas se ignoran. |
| `dexcom_14dias.csv` | Dexcom Clarity | 16/10 – 29/10 | Aceptado: 4.032 mediciones (EGV cada 5 min). Filas de paciente, dispositivo y alertas ignoradas. |
| `generico_1dia.csv` | Genérico (coma) | 30/10 | Aceptado: 288 mediciones. |
| `generico_con_errores.csv` | Genérico (punto y coma) | 31/10 | Aceptado con 4 inválidas (valor no numérico, fecha ilegible, fuera de 40–500, vacío), 1 duplicada y 1 en conflicto: 284 mediciones. |
| `dexcom_noviembre.csv` | Dexcom Clarity | 01/11 – 08/11 | Aceptado: 2.304 mediciones (EGV cada 5 min). Continúa la misma simulación. |
| `generico_rechazado.csv` | Genérico | 01/11 | Rechazado: 14 de 40 filas inválidas (35 % > 20 %). No se guarda nada. |
| `formato_desconocido.csv` | — | — | Rechazado: no coincide con ningún formato admitido. |

Volver a importar cualquier archivo aceptado no duplica datos: todas sus filas se informan como duplicadas.

Las fechas de LibreView dependen de la configuración regional de quien exporta («09-10-2026» puede
ser 9 de octubre o 10 de septiembre), por eso la aplicación pide confirmar el formato en vez de
deducirlo. Cada importación guarda el formato confirmado y la zona horaria aplicada.
