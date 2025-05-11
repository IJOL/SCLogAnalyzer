# Estructura SCLogAnalyzer

Este documento resume la estructura, dependencias, arquitectura de eventos y observaciones clave del proyecto SCLogAnalyzer, integrando todo el conocimiento almacenado en el grafo hasta la fecha.

---

## 1. Estructura de Carpetas y Archivos Principales

- **build_nuitka.bat, build.bat, Dockerfile**: scripts de compilación y despliegue.
- **src/**: código fuente principal.
  - **gui.py**: interfaz gráfica principal (GUI, wxPython).
  - **log_analyzer.py**: lógica de análisis de logs y eventos.
  - **helpers/**: utilidades y módulos de soporte.
    - **supabase_manager.py**: gestión de conexión y operaciones con Supabase.
    - **data_provider.py**: proveedores de datos (Supabase/Google Sheets).
    - **data_display_manager.py**: gestión de visualización de datos.
    - **gui_module.py**: componentes de UI adicionales.
    - **config_utils.py**: utilidades de configuración.
    - **message_bus.py**: bus de mensajes para comunicación interna.
    - **debug_utils.py**: utilidades de depuración y trazado.
    - **main_frame.py**: ventana principal de la aplicación.
    - **window_state_manager.py**: persistencia de estado de ventana.
    - **updater.py**: gestión de actualizaciones.
    - **ui_components.py**: componentes reutilizables de UI.
    - **monitoring_service.py**: servicios de monitorización.
    - **event_handlers.py**: (DEPRECATED, migrado a MessageBus).
- **config.json**: configuración principal del proyecto.
- **requirements.txt**: dependencias del proyecto.

---

## 2. Arquitectura de Componentes y Relaciones

- **LogFileHandler**: clase principal para monitorización y parsing de logs. Detecta eventos, mantiene estado y publica mensajes en el MessageBus.
- **ConfigManager**: gestión de configuración, acceso thread-safe, carga desde config.json.
- **MessageBus**: sistema de comunicación interna (pub/sub), maneja eventos, logs y notificaciones.
- **DataProvider**: interfaz para almacenamiento de datos (implementaciones: GoogleSheetsDataProvider, SupabaseDataProvider).
- **SupabaseDataProvider**: almacenamiento en la nube usando Supabase.
- **WindowStateManager**: persistencia de estado de ventana en el registro de Windows.
- **StatusBoardBot**: bot de Discord para mostrar información de estado.
- **DataDisplayManager**: gestión de visualización de datos en la UI.
- **Otros**: utilidades para iconos, versiones, migraciones, etc.

---

## 3. Integración con Supabase y realtime-py

- **SCLogAnalyzer** depende de **realtime-py** para comunicación en tiempo real (canales de presencia y broadcast).
- **RealtimeBridge** (en helpers/realtime_bridge.py) usa AsyncRealtimeClient y AsyncRealtimeChannel de realtime-py para gestionar presencia y mensajería broadcast.
- **supabase_manager.py** y **realtime_bridge.py** importan y usan clases de realtime-py.
- **realtime-py** está presente en el workspace como proyecto hermano y se usa como dependencia directa.

---

## 4. Eventos, Callbacks y Presencia (realtime-py)

- **Canal soportado**: general (unifica broadcast y presence).
- **Callbacks principales en el canal general**:
  - `on_presence_sync(callback)`: sincronización de presencia.
  - `on_presence_join(callback)`: usuario se une.
  - `on_presence_leave(callback)`: usuario se va.
  - `track(user_status)`: actualiza el estado de presencia del usuario local.
  - `untrack()`: deja de anunciar presencia.
  - `presence_state()`: obtiene el estado actual de presencia.
  - `on_broadcast(event, callback)`: escucha eventos broadcast.
  - `send_broadcast(event, data)`: envía evento broadcast.
  - `on_system(callback)`: eventos internos del sistema (notificaciones, comandos, alertas, etc.).
  - `subscribe(callback)`: estado de suscripción.

### Detalles de track
- Cada llamada a `track` envía el estado del usuario al canal general.
- Es seguro y necesario llamarlo periódicamente (heartbeat) para mantener la presencia activa.
- Si se llama con datos diferentes, los cambios se reflejan en la presencia del usuario.
- Si no se llama durante mucho tiempo, el usuario puede ser considerado desconectado.

### Detalles de on_system
- Permite registrar callbacks para eventos internos enviados por el servidor o la infraestructura de canales.
- Puede usarse para notificaciones de mantenimiento, comandos administrativos, sincronización avanzada o alertas especiales.
- Su uso depende de la lógica de la aplicación y requiere definir qué eventos de sistema se quieren manejar.

---

## 5. Gestión de autenticación y token

- SCLogAnalyzer usa autenticación anónima para obtener un JWT (access_token) por usuario.
- El token se pasa al cliente realtime y se actualiza con `set_auth(token)`.
- Si el token caduca, supabase-py async actualiza automáticamente el header de autorización y el token de realtime-py usando eventos de autenticación (`SIGNED_IN`, `TOKEN_REFRESHED`, etc.).
- Solo es necesario llamar manualmente a `set_auth` si el token se gestiona fuera del flujo estándar de supabase-py. Si se usa supabase-py async y la autenticación/refresh se hace a través de sus métodos, la propagación es automática.
- Para establecer la conexión websocket inicial, NO es estrictamente necesario llamar manualmente a `connect()` sobre el cliente: la primera llamada a `subscribe()` en un canal abrirá la conexión si es necesario (`subscribe()` llama internamente a `connect()` si el cliente no está conectado).
- Llamar a `connect()` explícitamente es opcional y puede aportar control adicional sobre el ciclo de vida de la conexión (por ejemplo, para mostrar estados de conexión en la UI o manejar errores de conexión de forma centralizada), pero no es obligatorio para el funcionamiento básico.
- El flujo estándar asegura que la reconexión y actualización del token funcionen correctamente y de forma transparente para el usuario.

---

## 6. Observaciones clave

- El sistema de eventos y mensajes está centralizado en MessageBus (on/emit/off).
- La migración desde la clase Event a MessageBus está documentada y completada.
- El uso de PowerShell es obligatorio para scripts y comandos.
- El proyecto es Windows-only y debe ejecutarse siempre en ese entorno.
- Los planes de edición y cambios deben almacenarse y aprobarse antes de aplicar modificaciones.
- La estructura y relaciones del proyecto están documentadas en el grafo de conocimiento.

---

## 7. Flujo de activación y detección de modo debug

- El modo debug se activa por flag CLI --debug/-d (main.debug_mode = True) o por combinación secreta CTRL+SHIFT+ALT+D en la GUI (self.debug_mode en LogAnalyzerFrame).
- En scripts de test, el modo debug está forzado por el propio script.
- El modo debug NUNCA está en config.json ni en ConfigManager.
- Para detectar modo debug: primero buscar main.debug_mode (en __main__), luego self.debug_mode en la GUI.
- El modo debug controla visibilidad de botones, logs extra y herramientas de desarrollo.
- Si se necesita saber el modo debug en un panel secundario, buscar primero en __main__.debug_mode y, si se está en la GUI, en el frame principal.
- Buenas prácticas: nunca consultar la configuración para debug, siempre usar el flag global o el atributo del componente.

---

Este archivo debe usarse como referencia base para futuras tareas, migraciones, refactorizaciones y para comprender la arquitectura y dependencias de SCLogAnalyzer.
