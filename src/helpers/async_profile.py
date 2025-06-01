"""
Async Profile Scraper Helper
Simple wrapper around the standalone profile parser module.
NO ANALYSIS CODE HERE - All profile parsing is handled by profile_parser_standalone.py
"""

import os
import threading
import requests
from bs4 import BeautifulSoup
from .message_bus import message_bus, MessageLevel
import datetime

# Import all functions from the standalone module
from helpers.profile_parser_standalone import extract_profile_data

def scrape_profile_async(player_name: str, metadata: dict = None):
    """Thread simple para scraping de perfil RSI - usa solo el módulo standalone"""
    metadata = metadata or {}
    
    def scrape(metadata):
        try:
            # Log inicio del scraping
            message_bus.publish(
                content=f"Iniciando scraping de perfil para {player_name}",
                level=MessageLevel.INFO,
                metadata={"source": "profile_scraper", "player": player_name}
            )
            
            url = f"https://robertsspaceindustries.com/en/citizens/{player_name}"
            message_bus.publish(
                content=f"Consultando URL: {url}",
                level=MessageLevel.DEBUG,
                metadata={"source": "profile_scraper", "url": url}
            )
            
            response = requests.get(url, timeout=5)
            
            # Log estado de respuesta HTTP
            message_bus.publish(
                content=f"Respuesta HTTP {response.status_code} para perfil de {player_name}",
                level=MessageLevel.DEBUG if response.status_code == 200 else MessageLevel.WARNING,
                metadata={"source": "profile_scraper", "status_code": response.status_code, "player": player_name}
            )
            
            if response.status_code == 200:
                # Callback para integrar con message_bus
                def message_bus_callback(message: str, level: str, metadata_log: dict = None):
                    """Convierte logs del módulo standalone al message_bus local."""
                    level_mapping = {
                        "DEBUG": MessageLevel.DEBUG,
                        "INFO": MessageLevel.INFO,
                        "WARNING": MessageLevel.WARNING,
                        "ERROR": MessageLevel.ERROR
                    }
                    message_bus.publish(
                        content=message,
                        level=level_mapping.get(level, MessageLevel.INFO),
                        metadata=metadata_log or {}
                    )
                
                # USAR SOLO EL MÓDULO STANDALONE - SIN CÓDIGO DE ANÁLISIS AQUÍ
                profile_data = extract_profile_data(response.text, message_bus_callback)
                
                # Log resumen de extracción
                extracted_fields = [k for k, v in profile_data.items() if v not in ['Unknown', '', []]]
                message_bus.publish(
                    content=f"Perfil de {player_name} procesado: {len(extracted_fields)} campos extraídos exitosamente",
                    level=MessageLevel.INFO,
                    metadata={"source": "profile_scraper", "extracted_count": len(extracted_fields), "player": player_name}
                )
                
                metadata.update(profile_data)
                
                # Log emisión de evento
                message_bus.publish(
                    content=f"Evento actor_profile emitido para {player_name}",
                    level=MessageLevel.INFO,
                    metadata={"source": "profile_scraper", "player": player_name}
                )
                
                # Emitir evento actor_profile (misma signatura que antes)
                message_bus.emit('actor_profile', 
                                player_name, 
                                metadata.get('main_org_sid'), 
                                metadata.get('enlisted'), 
                                metadata)
            else:
                message_bus.publish(
                    content=f"Error HTTP {response.status_code} al consultar perfil de {player_name}",
                    level=MessageLevel.WARNING,
                    metadata={"source": "profile_scraper", "status_code": response.status_code, "player": player_name}
                )
                
        except Exception as e:
            # Mejor manejo de errores con más contexto
            message_bus.publish(
                content=f"Error durante scraping de perfil para {player_name}: {str(e)}",
                level=MessageLevel.ERROR,
                metadata={"source": "profile_scraper", "player": player_name, "error": str(e)}
            )
    
    thread = threading.Thread(target=scrape, args=[metadata], daemon=True)
    thread.start()

