# Testing Guide - SCLogAnalyzer

## 📋 Tabla de Contenidos

- [Descripción General](#descripción-general)
- [Estructura de Tests](#estructura-de-tests)
- [Configuración del Entorno](#configuración-del-entorno)
- [Ejecutar Tests](#ejecutar-tests)
- [Cobertura de Código](#cobertura-de-código)
- [Escribir Nuevos Tests](#escribir-nuevos-tests)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Descripción General

Este proyecto utiliza **pytest** como framework de testing. La suite de tests actual cubre los módulos críticos del sistema:

### Módulos Testeados

| Módulo | Archivo de Tests | Tests | Cobertura Estimada |
|--------|------------------|-------|-------------------|
| `config_utils.py` | `test_config_utils.py` | 30+ | ~85% |
| `message_bus.py` | `test_message_bus.py` | 40+ | ~90% |
| `rate_limiter.py` | `test_rate_limiter.py` | 20+ | ~95% |

**Total**: ~90 tests unitarios

### Funcionalidades Cubiertas

✅ **ConfigManager**
- Singleton pattern
- Carga/guardado de configuración
- Get/Set con dot notation
- Gestión de VIP players
- Validación de URLs
- Detección de entorno (LIVE/PTU)
- Thread safety

✅ **MessageBus**
- Sistema de mensajes pub/sub
- Filtros por nivel y patrón
- Historial de mensajes
- Sistema de eventos
- Debug mode
- Thread safety

✅ **MessageRateLimiter**
- Límites por mensaje duplicado
- Límites globales de eventos
- Cleanup automático
- Estadísticas de rate limiting
- Thread safety

---

## 📁 Estructura de Tests

```
SCLogAnalyzer/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Fixtures y configuración compartida
│   ├── core/
│   │   ├── __init__.py
│   │   ├── test_config_utils.py
│   │   ├── test_message_bus.py
│   │   └── test_rate_limiter.py
│   ├── ui/                      # Tests de UI (futuro)
│   ├── tournament/              # Tests de torneos (futuro)
│   └── fixtures/                # Datos de prueba
├── pytest.ini                   # Configuración de pytest
└── TESTING.md                   # Esta documentación
```

---

## ⚙️ Configuración del Entorno

### 1. Prerequisitos

- Python 3.12+
- pip (gestor de paquetes)
- Entorno virtual (recomendado)

### 2. Instalación de Dependencias

#### Opción A: Instalación Completa

```bash
# Clonar el repositorio
git clone <repo-url>
cd SCLogAnalyzer

# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Instalar todas las dependencias
pip install -r requirements.txt
```

#### Opción B: Solo Dependencias de Testing

```bash
# Dependencias mínimas para ejecutar tests
pip install pytest pytest-mock pytest-cov pytest-timeout pytest-xdist
pip install watchdog requests beautifulsoup4 Pillow psutil webcolors python-dotenv pyperclip plumbum
```

### 3. Dependencias del Sistema (Opcional)

Algunos tests requieren librerías del sistema:

**Linux (Ubuntu/Debian)**:
```bash
sudo apt-get install libzbar0
```

**Windows**:
Las DLLs de zbar están incluidas en el paquete pyzbar de Python.

**macOS**:
```bash
brew install zbar
```

---

## 🚀 Ejecutar Tests

### Comandos Básicos

```bash
# Ejecutar todos los tests
pytest

# Ejecutar con salida verbose
pytest -v

# Ejecutar tests de un módulo específico
pytest tests/core/test_config_utils.py

# Ejecutar tests de una clase específica
pytest tests/core/test_config_utils.py::TestConfigManager

# Ejecutar un test específico
pytest tests/core/test_config_utils.py::TestConfigManager::test_get_simple_key
```

### Opciones Avanzadas

```bash
# Ejecutar tests en paralelo (más rápido)
pytest -n auto

# Mostrar print statements
pytest -s

# Detener en el primer fallo
pytest -x

# Mostrar tests más lentos
pytest --durations=10

# Ejecutar solo tests marcados como "unit"
pytest -m unit

# Excluir tests lentos
pytest -m "not slow"

# Mostrar cobertura de código
pytest --cov=src/helpers --cov-report=html

# Generar reporte de cobertura en terminal
pytest --cov=src/helpers --cov-report=term-missing
```

### Ejecución con Diferentes Niveles de Detalle

```bash
# Modo silencioso (solo muestra fails)
pytest -q

# Modo normal
pytest

# Modo verbose
pytest -v

# Modo extra verbose
pytest -vv
```

---

## 📊 Cobertura de Código

### Generar Reporte de Cobertura

```bash
# Generar reporte HTML
pytest --cov=src/helpers --cov-report=html

# El reporte estará en htmlcov/index.html
# Abrirlo con:
# Windows:
start htmlcov\index.html
# Linux:
xdg-open htmlcov/index.html
# Mac:
open htmlcov/index.html
```

### Interpretar el Reporte

- **Verde**: Líneas cubiertas por tests
- **Rojo**: Líneas no cubiertas
- **Amarillo**: Líneas parcialmente cubiertas (branches)

### Objetivo de Cobertura

| Módulo | Cobertura Objetivo | Cobertura Actual |
|--------|-------------------|------------------|
| Módulos Core | 80%+ | ~85% |
| UI Components | 60%+ | 0% (pendiente) |
| Utilities | 70%+ | Parcial |
| **TOTAL** | **70%+** | **~40%** |

---

## ✍️ Escribir Nuevos Tests

### Estructura de un Test

```python
"""Tests for mi_modulo module"""
import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from helpers.core.mi_modulo import MiClase


class TestMiClase:
    """Test suite for MiClase"""

    @pytest.fixture
    def mi_instancia(self):
        """Fixture que retorna una instancia de MiClase"""
        return MiClase()

    def test_metodo_basico(self, mi_instancia):
        """Test de método básico"""
        resultado = mi_instancia.metodo()
        assert resultado == valor_esperado

    def test_con_mock(self, mock_config_manager):
        """Test usando mocks"""
        mock_config_manager.get.return_value = "test_value"
        # ... resto del test
```

### Usar Fixtures

Las fixtures están definidas en `tests/conftest.py`:

```python
def test_con_fixture(temp_config_file, mock_message_bus):
    """Test usando fixtures predefinidas"""
    # temp_config_file contiene un archivo de config temporal
    # mock_message_bus es un mock del MessageBus
    pass
```

### Markers Disponibles

```python
@pytest.mark.unit
def test_unit():
    """Test unitario puro"""
    pass

@pytest.mark.integration
def test_integration():
    """Test de integración"""
    pass

@pytest.mark.slow
def test_slow():
    """Test lento (puede tardarse)"""
    pass

@pytest.mark.gui
def test_gui():
    """Test que requiere GUI"""
    pass
```

### Mejores Prácticas

1. **Un test, una aserción** (cuando sea posible)
2. **Nombres descriptivos**: `test_get_config_value_with_dot_notation`
3. **Arrange-Act-Assert** pattern:
   ```python
   def test_ejemplo():
       # Arrange (preparar)
       config = ConfigManager()

       # Act (ejecutar)
       result = config.get('key')

       # Assert (verificar)
       assert result == 'value'
   ```
4. **Usar fixtures para setup/teardown**
5. **Mocks para dependencias externas**
6. **Tests independientes** (no deben depender de orden de ejecución)

---

## 🔧 Troubleshooting

### Problema: "ModuleNotFoundError: No module named 'watchdog'"

**Solución**:
```bash
pip install watchdog
```

### Problema: "ImportError: Unable to find zbar shared library"

**Causa**: pyzbar requiere libzbar del sistema.

**Solución**:
```bash
# Linux
sudo apt-get install libzbar0

# macOS
brew install zbar

# Windows: Ya debería funcionar con pyzbar
```

**Alternativa**: Mockear pyzbar en tests:
```python
@patch('pyzbar.pyzbar.decode')
def test_con_pyzbar_mockeado(mock_decode):
    mock_decode.return_value = []
    # ... resto del test
```

### Problema: Tests fallan por dependencias circulares

**Causa**: El `__init__.py` de `helpers.core` importa todos los módulos.

**Solución**: Importar directamente el módulo específico:
```python
# En vez de:
from helpers.core import ConfigManager

# Usar:
from helpers.core.config_utils import ConfigManager
```

### Problema: "fixture 'X' not found"

**Causa**: Fixture no está en `conftest.py` o no está en scope.

**Solución**:
1. Verificar que `conftest.py` está en el directorio correcto
2. Agregar la fixture a `conftest.py`
3. Verificar que pytest encuentra el `conftest.py`

### Problema: Tests pasan localmente pero fallan en CI

**Causas posibles**:
1. Dependencias del sistema faltantes
2. Diferencias de plataforma (Windows vs Linux)
3. Variables de entorno faltantes
4. Race conditions en tests paralelos

**Soluciones**:
1. Documentar dependencias del sistema en CI config
2. Usar `@pytest.mark.skipif` para tests específicos de plataforma
3. Mockear variables de entorno
4. Agregar locks o usar `-n 0` para tests problemáticos

---

## 📈 Roadmap de Testing

### Fase 1: Core Modules ✅ (COMPLETADO)
- [x] config_utils.py
- [x] message_bus.py
- [x] rate_limiter.py

### Fase 2: Core Modules (Pendiente)
- [ ] log_analyzer.py (tests básicos)
- [ ] supabase_manager.py (con mocks)
- [ ] data_provider.py
- [ ] realtime_bridge.py

### Fase 3: Tournament System
- [ ] tournament.py
- [ ] tournament_manager.py
- [ ] corpse_detector.py

### Fase 4: UI Components (Opcional)
- [ ] main_frame.py (tests básicos)
- [ ] gui_module.py
- [ ] widgets/ (componentes críticos)

### Fase 5: Integration Tests
- [ ] End-to-end log processing
- [ ] Database integration
- [ ] Discord webhook integration (mocked)

---

## 📚 Recursos Adicionales

- [Documentación de pytest](https://docs.pytest.org/)
- [pytest-mock Documentation](https://pytest-mock.readthedocs.io/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [Testing Best Practices](https://docs.python-guide.org/writing/tests/)

---

## 🤝 Contribuir con Tests

Al agregar nuevas funcionalidades, por favor:

1. **Escribe tests primero** (TDD)
2. **Mantén cobertura >70%** para módulos críticos
3. **Documenta tests complejos**
4. **Usa fixtures** para código reusable
5. **Ejecuta tests antes de commit**: `pytest`
6. **Verifica cobertura**: `pytest --cov`

---

**Última actualización**: 2024-11-15
**Mantenedor**: AI Assistant
**Versión del proyecto**: v0.17.2-79946b4-onyx
