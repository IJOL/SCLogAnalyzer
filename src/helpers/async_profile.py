"""
Async Profile Scraper Helper
Enhanced helper for scraping RSI player profiles with maximum information extraction
Extracts: UEE citizen record, handle name, location, fluency, title/rank, SID, org rank
Maintains full compatibility with existing code - same function signature and event format
Uses robust HTML structure parsing instead of fragile regex patterns
"""

import os
import threading
import requests
from bs4 import BeautifulSoup
from .message_bus import message_bus, MessageLevel
import datetime


def detect_organization_status(soup):
    """
    Detecta el estado de la organización del jugador basado en la estructura HTML
    
    Args:
        soup: BeautifulSoup object del HTML del perfil
        
    Returns:
        dict: {
            'status': 'None'|'Visible'|'Redacted'|'Unknown',
            'name': str,
            'visibility_class': str
        }
    """
    try:
        message_bus.publish(
            content="Iniciando detección de estado de organización",
            level=MessageLevel.DEBUG,
            metadata={"source": "org_detector"}
        )
        
        # Buscar el div principal de organización
        org_div = soup.select_one('div.main-org.right-col')
        if not org_div:
            result = {'status': 'Unknown', 'name': 'Unknown', 'visibility_class': ''}
            message_bus.publish(
                content="No se encontró div principal de organización",
                level=MessageLevel.DEBUG,
                metadata={"source": "org_detector"}
            )
            return result
        
        # Extraer clase de visibilidad
        visibility_class = ''
        for cls in org_div.get('class', []):
            if cls.startswith('visibility-'):
                visibility_class = cls
                break
        
        message_bus.publish(
            content=f"Clase de visibilidad detectada: {visibility_class}",
            level=MessageLevel.DEBUG,
            metadata={"source": "org_detector", "visibility_class": visibility_class}
        )
        
        # NUEVA LÓGICA: Detectar estado basado en clase de visibilidad PRIMERO
        # Caso 1: Sin organización (visibility- sin letra o clase vacía)
        if visibility_class == 'visibility-' or not visibility_class:
            empty_div = org_div.select_one('div.empty')
            if empty_div and 'NO MAIN ORG FOUND' in empty_div.get_text():
                result = {'status': 'None', 'name': 'None', 'visibility_class': visibility_class}
                message_bus.publish(
                    content=f"Estado de organización detectado: {result['status']} - {result['name']}",
                    level=MessageLevel.INFO,
                    metadata={"source": "org_detector", "visibility_class": result['visibility_class'], "status": result['status']}
                )
                return result
        
        # Caso 2: Organización visible (visibility-V)
        elif visibility_class == 'visibility-V':
            org_link = org_div.select_one('a.value')
            if org_link:
                org_name = org_link.get_text(strip=True)
                if org_name:  # Solo si tiene nombre válido
                    result = {'status': 'Visible', 'name': org_name, 'visibility_class': visibility_class}
                    message_bus.publish(
                        content=f"Estado de organización detectado: {result['status']} - {result['name']}",
                        level=MessageLevel.INFO,
                        metadata={"source": "org_detector", "visibility_class": result['visibility_class'], "status": result['status']}
                    )
                    return result
        
        # Caso 3: Organización redacted/privada (visibility-R)
        elif visibility_class == 'visibility-R':
            # Verificar si tiene imagen redacted como indicador adicional
            redacted_img = org_div.select_one('img[src*="redacted"]')
            if redacted_img:
                result = {'status': 'Redacted', 'name': 'Redacted', 'visibility_class': visibility_class}
                message_bus.publish(
                    content=f"Estado de organización detectado: {result['status']} - {result['name']}",
                    level=MessageLevel.INFO,
                    metadata={"source": "org_detector", "visibility_class": result['visibility_class'], "status": result['status']}
                )
                return result
            
            # También detectar por patrón de elementos con solo espacios
            info_div = org_div.select_one('div.info')
            if info_div:
                # Buscar elementos con clase data que contengan solo espacios
                data_elements = info_div.select('[class*="data"]')
                if len(data_elements) > 0:
                    # Si hay elementos data pero sin contenido útil, es redacted
                    result = {'status': 'Redacted', 'name': 'Redacted', 'visibility_class': visibility_class}
                    message_bus.publish(
                        content=f"Estado de organización detectado: {result['status']} - {result['name']}",
                        level=MessageLevel.INFO,
                        metadata={"source": "org_detector", "visibility_class": result['visibility_class'], "status": result['status']}
                    )
                    return result
        
        # Fallback: Intentar detección por contenido (para casos no estándar)
        # Caso 4: Sin organización (como "aaa")
        empty_div = org_div.select_one('div.empty')
        if empty_div and 'NO MAIN ORG FOUND' in empty_div.get_text():
            result = {'status': 'None', 'name': 'None', 'visibility_class': visibility_class}
            message_bus.publish(
                content=f"Estado de organización detectado (fallback): {result['status']} - {result['name']}",
                level=MessageLevel.INFO,
                metadata={"source": "org_detector", "visibility_class": result['visibility_class'], "status": result['status']}
            )
            return result
        
        # Caso 5: Organización visible (fallback)
        org_link = org_div.select_one('a.value')
        if org_link:
            org_name = org_link.get_text(strip=True)
            if org_name:  # Solo si tiene nombre válido
                result = {'status': 'Visible', 'name': org_name, 'visibility_class': visibility_class}
                message_bus.publish(
                    content=f"Estado de organización detectado (fallback): {result['status']} - {result['name']}",
                    level=MessageLevel.INFO,
                    metadata={"source": "org_detector", "visibility_class": result['visibility_class'], "status": result['status']}
                )
                return result
        
        # Caso 6: Organización redacted/privada (fallback)
        info_div = org_div.select_one('div.info')
        if info_div:
            text_content = info_div.get_text(strip=True)
            if 'REDACTED' in text_content.upper() or 'PRIVATE' in text_content.upper():
                result = {'status': 'Redacted', 'name': 'Redacted', 'visibility_class': visibility_class}
                message_bus.publish(
                    content=f"Estado de organización detectado (fallback): {result['status']} - {result['name']}",
                    level=MessageLevel.INFO,
                    metadata={"source": "org_detector", "visibility_class": result['visibility_class'], "status": result['status']}
                )
                return result
            
            # Si tiene info pero está vacía o solo espacios, podría ser redacted
            if len(text_content) == 0 or text_content.isspace():
                return {'status': 'Redacted', 'name': 'Redacted', 'visibility_class': visibility_class}
        
        # Caso por defecto: Unknown
        result = {'status': 'Unknown', 'name': 'Unknown', 'visibility_class': visibility_class}
        
        # Log del resultado final
        message_bus.publish(
            content=f"Estado de organización detectado: {result['status']} - {result['name']}",
            level=MessageLevel.INFO,
            metadata={"source": "org_detector", "visibility_class": result['visibility_class'], "status": result['status']}
        )
        
        return result
        
    except Exception as e:
        # En caso de error, devolver estado desconocido
        message_bus.publish(
            content=f"Error detectando estado de organización: {str(e)}",
            level=MessageLevel.ERROR,
            metadata={"source": "org_detector", "error": str(e)}
        )
        return {'status': 'Unknown', 'name': 'Unknown', 'visibility_class': ''}


def extract_enhanced_profile_data(soup):
    """Extrae toda la información disponible de la página principal del perfil usando parsing HTML robusto"""
    
    # Log inicio del procesamiento
    message_bus.publish(
        content="Iniciando extracción de datos del perfil HTML",
        level=MessageLevel.DEBUG,
        metadata={"source": "profile_parser"}
    )
    
    profile_data = {
        'uee_citizen_record': 'Unknown',
        'handle_name': 'Unknown',
        'display_name': 'Unknown',
        'title_rank': 'Unknown',
        'location': 'Unknown',
        'fluency': [],
        'main_org_sid': 'Unknown',
        'main_org_rank': 'Unknown',
        'enlisted': 'Unknown',
        'main_org_name': 'Unknown',      # Nombre de la organización principal
        'main_org_status': 'Unknown',    # None|Visible|Redacted|Unknown
    }
    
    try:
        # 1. UEE Citizen Record
        try:
            citizen_record_elem = soup.select_one('p.citizen-record .value')
            if citizen_record_elem:
                profile_data['uee_citizen_record'] = citizen_record_elem.get_text(strip=True)
                message_bus.publish(
                    content=f"UEE Citizen Record extraído: {profile_data['uee_citizen_record']}",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "profile_parser", "field": "uee_citizen_record"}
                )
            else:
                message_bus.publish(
                    content="No se pudo extraer UEE Citizen Record: elemento no encontrado",
                    level=MessageLevel.WARNING,
                    metadata={"source": "profile_parser", "field": "uee_citizen_record"}
                )
        except Exception as e:
            message_bus.publish(
                content=f"Error extrayendo UEE Citizen Record: {str(e)}",
                level=MessageLevel.WARNING,
                metadata={"source": "profile_parser", "field": "uee_citizen_record", "error": str(e)}
            )
        
        # 2. Display Name (primer nombre en profile)
        try:
            display_name_elem = soup.select_one('div.profile.left-col .info p.entry:first-child .value')
            if display_name_elem:
                profile_data['display_name'] = display_name_elem.get_text(strip=True)
                message_bus.publish(
                    content=f"Display Name extraído: {profile_data['display_name']}",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "profile_parser", "field": "display_name"}
                )
            else:
                message_bus.publish(
                    content="No se pudo extraer Display Name: elemento no encontrado",
                    level=MessageLevel.WARNING,
                    metadata={"source": "profile_parser", "field": "display_name"}
                )
        except Exception as e:
            message_bus.publish(
                content=f"Error extrayendo Display Name: {str(e)}",
                level=MessageLevel.WARNING,
                metadata={"source": "profile_parser", "field": "display_name", "error": str(e)}
            )
        
        # 3. Handle Name
        try:
            labels = soup.find_all('span', class_='label')
            handle_found = False
            for label in labels:
                if 'Handle name' in label.get_text():
                    value_elem = label.find_next('strong', class_='value')
                    if value_elem:
                        profile_data['handle_name'] = value_elem.get_text(strip=True)
                        message_bus.publish(
                            content=f"Handle Name extraído: {profile_data['handle_name']}",
                            level=MessageLevel.DEBUG,
                            metadata={"source": "profile_parser", "field": "handle_name"}
                        )
                        handle_found = True
                        break
            if not handle_found:
                message_bus.publish(
                    content="No se pudo extraer Handle Name: label no encontrado",
                    level=MessageLevel.WARNING,
                    metadata={"source": "profile_parser", "field": "handle_name"}
                )
        except Exception as e:
            message_bus.publish(
                content=f"Error extrayendo Handle Name: {str(e)}",
                level=MessageLevel.WARNING,
                metadata={"source": "profile_parser", "field": "handle_name", "error": str(e)}
            )
        
        # 4. Title/Rank (icono con heap_thumb)
        try:
            icon_entries = soup.find_all('p', class_='entry')
            for entry in icon_entries:
                icon_span = entry.find('span', class_='icon')
                if icon_span:
                    img = icon_span.find('img')
                    if img and img.get('src') and 'heap_thumb' in img.get('src'):
                        value_span = entry.find('span', class_='value')
                        if value_span:
                            profile_data['title_rank'] = value_span.get_text(strip=True)
                            break
        except Exception:
            pass
        
        # 5. Spectrum Identification (SID)
        try:
            labels = soup.find_all('span', class_='label')
            for label in labels:
                if 'Spectrum Identification' in label.get_text():
                    value_elem = label.find_next('strong', class_='value')
                    if value_elem:
                        profile_data['main_org_sid'] = value_elem.get_text(strip=True)
                        break
        except Exception:
            pass
        
        # 6. Organization Rank
        try:
            labels = soup.find_all('span', class_='label')
            for label in labels:
                if 'Organization rank' in label.get_text():
                    value_elem = label.find_next('strong', class_='value')
                    if value_elem:
                        profile_data['main_org_rank'] = value_elem.get_text(strip=True)
                        break
        except Exception:
            pass
        
        # 6.5. Organization Status Detection (Nueva funcionalidad)
        try:
            org_status = detect_organization_status(soup)
            profile_data['main_org_status'] = org_status['status']
            profile_data['main_org_name'] = org_status['name']
        except Exception:
            pass
        
        # 7. Location
        try:
            # Buscar TODOS los labels con "Location" sin restricciones de selector
            # Esto evita capturar la location del usuario logueado y busca específicamente
            # en el perfil del jugador que se está visualizando
            all_labels = soup.find_all('span', class_='label')
            for label in all_labels:
                if 'Location' in label.get_text():
                    value_elem = label.find_next('strong', class_='value')
                    if value_elem:
                        # Limpiar texto multi-línea y espacios extra
                        location_text = value_elem.get_text(separator=' ', strip=True)
                        # Limpiar comas extra y espacios
                        location_clean = ' '.join(location_text.split()).replace(' ,', ',')
                        profile_data['location'] = location_clean
                        break
        except Exception:
            pass
        
        # 8. Fluency (idiomas)
        try:
            labels = soup.find_all('span', class_='label')
            for label in labels:
                if 'Fluency' in label.get_text():
                    value_elem = label.find_next('strong', class_='value')
                    if value_elem:
                        # Obtener texto y separar por comas
                        fluency_text = value_elem.get_text(separator=' ', strip=True)
                        # Separar por comas y limpiar cada idioma
                        languages = [lang.strip() for lang in fluency_text.split(',')]
                        # Filtrar idiomas vacíos
                        languages = [lang for lang in languages if lang]
                        profile_data['fluency'] = languages
                        break
        except Exception:
            pass
        
        # 9. Enlisted (fecha de alistamiento)
        try:
            entries = soup.find_all('p', class_='entry')
            for entry in entries:
                label = entry.find('span', class_='label')
                if label and 'Enlisted' in label.get_text():
                    value = entry.find('span', class_='value')
                    if value:
                        enlisted_str = value.get_text(strip=True)
                    else:
                        text = entry.get_text(strip=True)
                        if text.startswith('Enlisted'):
                            enlisted_str = text.replace('Enlisted', '', 1).strip()
                        else:
                            enlisted_str = text
                    profile_data['enlisted'] = enlisted_str
        except Exception:
            pass
        
    except Exception as e:
        # Log error pero continuar
        message_bus.publish(
            content=f"Enhanced profile HTML parsing had errors: {e}",
            level=MessageLevel.ERROR,
            metadata={"source": "enhanced_profile_html_parser", "error": str(e)}
        )
    
    # Log resumen final de extracción
    extracted_fields = [k for k, v in profile_data.items() if v not in ['Unknown', '', []]]
    total_fields = len(profile_data)
    message_bus.publish(
        content=f"Extracción completada: {len(extracted_fields)}/{total_fields} campos extraídos exitosamente",
        level=MessageLevel.INFO,
        metadata={"source": "profile_parser", "extracted_count": len(extracted_fields), "total_fields": total_fields}
    )
    
    return profile_data


def scrape_profile_async(player_name: str, metadata: dict = None):
    """Thread simple para scraping de perfil RSI según Plan MEGA SIMPLE"""
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
                soup = BeautifulSoup(response.text, 'html.parser')
              
                # Extraer información mejorada
                enhanced_profile_data = extract_enhanced_profile_data(soup)
                
                # Log resumen de extracción
                extracted_fields = [k for k, v in enhanced_profile_data.items() if v not in ['Unknown', '', []]]
                message_bus.publish(
                    content=f"Perfil de {player_name} procesado: {len(extracted_fields)} campos extraídos exitosamente",
                    level=MessageLevel.INFO,
                    metadata={"source": "profile_scraper", "extracted_count": len(extracted_fields), "player": player_name}
                )
                
                metadata.update(enhanced_profile_data)
                
                # Log emisión de evento
                message_bus.publish(
                    content=f"Evento actor_profile emitido para {player_name}",
                    level=MessageLevel.INFO,
                    metadata={"source": "profile_scraper", "player": player_name}
                )
                
                # Emitir evento actor_profile (misma signatura que antes)
                message_bus.emit('actor_profile', 
                                  player_name, 
                                  metadata.get('main_org_name'), 
                                  metadata.get('enlisted'), metadata)
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

