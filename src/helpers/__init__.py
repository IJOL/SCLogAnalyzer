"""
Helper modules for SC Log Analyzer.
This package contains utility modules used by the main application.
"""

def ensure_all_field(data):
    """
    Devuelve una copia de data con la clave 'all' generada si no existe.
    Usar SIEMPRE antes de formatear mensajes con .format(**data) que puedan usar {all}.
    """
    data_copy = data.copy()
    if 'all' not in data_copy:
        data_copy['all'] = ' '.join(
            f"{k}: {v}\n"
            for k, v in data_copy.items()
            if v is not None and k not in ['source','timestamp','player_name', 'org', 'enlisted','action'] and v not in ('None','Unknown','')
        )
    return data_copy