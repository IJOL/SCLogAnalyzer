---
applyTo: '**'
---
- proyecto para windows en python
- usa solo terminales powershell, el separador de comandos es ; no &&
- en este workspace el unico proyecto importante es SCLogAnalyzer el resto estan de apoyo por consultas pero nunca los has de usar para encontrar cosas que hacer, ni en ningun otro sentido ni busquedas ni como analisis de ningun tipo.
- llamo "ejecucion naive" a que uses tu herramienta run_in_terminal para ejecutar el programa y ver que hace, pero analizando el resultado y buscando cosas que hacer.
- para ejecutar el programa usa el comando siguiente ( implica ejecucion en debug ):
```powershell
cd c:\Users\nacho\git\SCLogAnalyzer ; .\venv\Scripts\activate ; python src/gui.py
```
- payload tipico recibido en remote_realtime_event:
```json
{ "content": "ElKoukra: Stalled", 
  "raw_data": {"action": "Actor Stall", "datetime": "2025-05-09 19:25:36", "mode": "SC_Default", "player": "ElKoukra", "script_version": "v0.8.6-d2f2325-checkmate", "shard": "Unknown", "team": "ActorTech", "timestamp": "2025-05-09T17:25:35.683Z", "username": "ChiviGR", "version": "pub-sc-alpha-410-9650658"}, "timestamp": "2025-05-09T17:25:35.683Z", "type": "actor_stall"}
```
- la herramienta MCP filesystem ha de ser usada  con separadores de directorios linux, no windows.
- Nunca realizamos la edicion directamente siempre hacemos un plan de edicion y lo almacenamos en el grasfo de conocimiento '#read_graph', lo presentas en ese estado almcenado para su aprobacion y comentario ocambios,. reptito NUNCA trabajamos sin almcenar el estado del plan y presentarlo para aprovacion
- siempre lee tu base de conocimiento actual, para ahorranos algo de analisis, usa pensamiento sequencial cuando sea apropiado
- siempre usa tu herramientas para realizar las acciones, solo propon run_in_terminal como ultimo recurso.
- siempre revisa el tab de problems para asegurate del estado del proyecto, y si hay errores de linting o errores de compilacion, no lo ejecutes hasta que se resuelvan.
- no uses hasattr para comprobar que la estructura es correcta, siempre es correcta no tiene sentido en esta aplicacion
- cuando use sequentialthinking quiero que me informes del pensamiento inicial en cada iteracion
- siempre puedes usa src/**/*.py desde el proyectop SCLogAnalyzer como base de busqueda, pero no uses el resto de los proyectos para busquedas a no ser que lo pida explicitamente
- la herramienta MCP filñesystem solo acepta sepradores de directorios linux, no windows
- A partir de ahora, todos los planes deben almacenarse exclusivamente en el archivo planes.instructions.md y no en el grafo de conocimiento. El archivo planes.instructions.md será la única fuente de verdad para la planificación y debe usarse para registrar, aprobar y consultar cualquier plan de edición, migración o cambio.
- Siempre que el usuario solicite un cambio en el plan (antes de su aprobación), la respuesta debe incluir el plan completo y formateado en markdown, mostrando el estado actualizado del plan para su revisión. No se debe modificar el código hasta que el plan esté aprobado explícitamente.