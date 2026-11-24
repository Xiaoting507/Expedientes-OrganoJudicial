# Encuesta SUS (System Usability Scale) — Sprint 8

Instrumento para medir la usabilidad del Expediente Judicial Digital con usuarios reales.
Se aplica después de que cada participante complete las tareas de la sección 2.

## 1. Participantes

Mínimo 5 personas (con 5 usuarios aparecen la mayoría de los problemas de uso). Idealmente:
2 en el rol de secretario, 1 de juez, 1 de abogado y 1 ciudadano.

## 2. Tareas (demo local, `SEED_DEMO=1`)

| # | Rol | Tarea | Se considera lograda si… |
| --- | --- | --- | --- |
| 1 | Secretario | Registrar un expediente civil y anotar el código de consulta | Aparece el número EXP-AAAA-NNNNNN |
| 2 | Secretario | Adjuntar un PDF al expediente | Se ve la huella SHA-256 del documento |
| 3 | Juez | Cambiar el estado del expediente a «En trámite» con un motivo | La línea de tiempo muestra el cambio |
| 4 | Juez | Verificar la integridad del PDF | El documento aparece como íntegro |
| 5 | Abogado | Presentar un escrito en su expediente | El escrito aparece en la línea de tiempo |
| 6 | Ciudadano | Consultar el estado con número y código | Ve el estado sin nombres de las partes |

Registrar por tarea: lograda (sí/no), tiempo en segundos y errores o dudas en voz alta.

## 3. Cuestionario (escala 1 = muy en desacuerdo … 5 = muy de acuerdo)

1. Creo que me gustaría usar este sistema con frecuencia.
2. Encontré el sistema innecesariamente complejo.
3. Pensé que el sistema era fácil de usar.
4. Creo que necesitaría ayuda de una persona técnica para poder usar este sistema.
5. Encontré que las funciones del sistema estaban bien integradas.
6. Pensé que había demasiada inconsistencia en el sistema.
7. Imagino que la mayoría de las personas aprendería a usar este sistema muy rápido.
8. Encontré el sistema muy difícil de usar.
9. Me sentí muy seguro(a) usando el sistema.
10. Necesité aprender muchas cosas antes de poder usar el sistema.

## 4. Cálculo

- Preguntas impares: respuesta − 1. Preguntas pares: 5 − respuesta.
- Sumar las 10 y multiplicar por 2.5: puntaje de 0 a 100 por participante.
- Resultado del sistema = promedio de los participantes.

| Puntaje | Interpretación |
| --- | --- |
| ≥ 80.3 | Excelente |
| 68 – 80.2 | Bueno (68 es el promedio de la industria) |
| 51 – 67.9 | Aceptable con problemas |
| < 51 | Problemas serios de usabilidad |

Meta del equipo: SUS ≥ 68 y al menos 5 de 6 tareas logradas por cada participante.

## 5. Registro de resultados

| Participante | Rol | Tareas logradas | Puntaje SUS | Comentario principal |
| --- | --- | --- | --- | --- |
| P1 | | | | |
| P2 | | | | |
| P3 | | | | |
| P4 | | | | |
| P5 | | | | |
| **Promedio** | | | | |
