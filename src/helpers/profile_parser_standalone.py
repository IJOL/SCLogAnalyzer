#!/usr/bin/env python3
"""
Módulo independiente de parsing de perfiles de Star Citizen.
Sin dependencias internas del proyecto SCLogAnalyzer.
"""

from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Callable, Any


def detect_organization_status(soup: BeautifulSoup, log_callback: Optional[Callable] = None) -> Dict[str, str]:
    """
    Detecta el estado de la organización del perfil.
    
    Args:
        soup: BeautifulSoup object del HTML del perfil
        log_callback: Función opcional para logging (log_callback(message, level, metadata))
    
    Returns:
        Dict con status, name y visibility_class
    """
    try:
        # Buscar información de la organización principal
        org_info = {'status': 'Unknown', 'name': 'Unknown', 'visibility_class': ''}
        
        # Buscar enlaces de organización
        org_links = soup.find_all('a', href=True)
        for link in org_links:
            href = link.get('href', '')
            if '/orgs/' in href or '/citizens/' in href:
                # Verificar si es un enlace de organización válido
                if 'spectrum-id' in href:
                    # Organización visible
                    org_name = link.get_text(strip=True)
                    if org_name and org_name != 'Unknown':
                        org_info['status'] = 'Visible'
                        org_info['name'] = org_name
                        org_info['visibility_class'] = 'visible'
                        break
        
        # Buscar organizaciones censuradas (redactadas)
        if org_info['status'] == 'Unknown':
            redacted_elements = soup.find_all(class_='redacted')
            for element in redacted_elements:
                parent = element.parent
                if parent and any(keyword in parent.get_text().lower() 
                                for keyword in ['organization', 'org', 'affiliation']):
                    org_info['status'] = 'Redacted'
                    org_info['name'] = 'Redacted'
                    org_info['visibility_class'] = 'redacted'
                    break
        
        if log_callback:
            log_callback(f"Organization status detected: {org_info['status']}", "DEBUG", 
                        {"source": "org_detector"})
        
        return org_info
        
    except Exception as e:
        if log_callback:
            log_callback(f"Error detecting organization status: {str(e)}", "ERROR", 
                        {"source": "org_detector", "error": str(e)})
        return {'status': 'Unknown', 'name': 'Unknown', 'visibility_class': ''}


def extract_profile_data(html_content: str, log_callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Extrae toda la información disponible del perfil HTML.
    
    Args:
        html_content: Contenido HTML del perfil como string
        log_callback: Función opcional para logging (log_callback(message, level, metadata))
    
    Returns:
        Dict con todos los datos extraídos del perfil
    """
    
    if log_callback:
        log_callback("Iniciando extracción de datos del perfil HTML", "DEBUG", 
                    {"source": "profile_parser"})
    
    # Crear soup object
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Estructura de datos inicial
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
        'main_org_name': 'Unknown',
        'main_org_status': 'Unknown',
    }
    
    try:
        # 1. UEE Citizen Record
        try:
            citizen_record_elem = soup.select_one('p.citizen-record .value')
            if citizen_record_elem:
                profile_data['uee_citizen_record'] = citizen_record_elem.get_text(strip=True)
                if log_callback:
                    log_callback(f"UEE Citizen Record extraído: {profile_data['uee_citizen_record']}", 
                               "DEBUG", {"source": "profile_parser", "field": "uee_citizen_record"})
            else:
                if log_callback:
                    log_callback("No se pudo extraer UEE Citizen Record: elemento no encontrado", 
                               "WARNING", {"source": "profile_parser", "field": "uee_citizen_record"})
        except Exception as e:
            if log_callback:
                log_callback(f"Error extrayendo UEE Citizen Record: {str(e)}", "WARNING", 
                           {"source": "profile_parser", "field": "uee_citizen_record", "error": str(e)})
        
        # 2. Display Name (primer nombre en profile)
        try:
            display_name_elem = soup.select_one('div.profile.left-col .info p.entry:first-child .value')
            if display_name_elem:
                profile_data['display_name'] = display_name_elem.get_text(strip=True)
                if log_callback:
                    log_callback(f"Display Name extraído: {profile_data['display_name']}", 
                               "DEBUG", {"source": "profile_parser", "field": "display_name"})
            else:
                if log_callback:
                    log_callback("No se pudo extraer Display Name: elemento no encontrado", 
                               "WARNING", {"source": "profile_parser", "field": "display_name"})
        except Exception as e:
            if log_callback:
                log_callback(f"Error extrayendo Display Name: {str(e)}", "WARNING", 
                           {"source": "profile_parser", "field": "display_name", "error": str(e)})
        
        # 3. Handle Name
        try:
            labels = soup.find_all('span', class_='label')
            handle_found = False
            for label in labels:
                if 'Handle name' in label.get_text():
                    value_elem = label.find_next('strong', class_='value')
                    if value_elem:
                        profile_data['handle_name'] = value_elem.get_text(strip=True)
                        if log_callback:
                            log_callback(f"Handle Name extraído: {profile_data['handle_name']}", 
                                       "DEBUG", {"source": "profile_parser", "field": "handle_name"})
                        handle_found = True
                        break
            if not handle_found and log_callback:
                log_callback("No se pudo extraer Handle Name: label no encontrado", 
                           "WARNING", {"source": "profile_parser", "field": "handle_name"})
        except Exception as e:
            if log_callback:
                log_callback(f"Error extrayendo Handle Name: {str(e)}", "WARNING", 
                           {"source": "profile_parser", "field": "handle_name", "error": str(e)})
        
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
        
        # 6.5. Organization Status Detection
        try:
            org_status = detect_organization_status(soup, log_callback)
            profile_data['main_org_status'] = org_status['status']
            profile_data['main_org_name'] = org_status['name']
        except Exception:
            pass
        
        # 7. Location - Usar función específica de extracción de ubicación
        try:
            profile_data['location'] = extract_location(html_content, log_callback)
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
        if log_callback:
            log_callback(f"Enhanced profile HTML parsing had errors: {e}", "ERROR", 
                       {"source": "profile_parser", "error": str(e)})
    
    # Log resumen final de extracción
    extracted_fields = [k for k, v in profile_data.items() if v not in ['Unknown', '', []]]
    total_fields = len(profile_data)
    if log_callback:
        log_callback(f"Extracción completada: {len(extracted_fields)}/{total_fields} campos extraídos exitosamente", 
                   "INFO", {"source": "profile_parser", "extracted_count": len(extracted_fields), 
                           "total_fields": total_fields})
    
    return profile_data


def extract_location(html_content: str, log_callback: Optional[Callable] = None) -> str:
    """
    Extracción de ubicación que evita capturar la ubicación del usuario logueado.
    
    Args:
        html_content: Contenido HTML del perfil
        log_callback: Función opcional para logging
    
    Returns:
        Ubicación del perfil o 'Unknown' si no se encuentra
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    try:
        # SOLUCIÓN: Buscar Location específicamente dentro del contenedor del perfil
        # Primero intentar buscar en div.left-col .inner (estructura típica del perfil)
        profile_container = soup.select_one('div.left-col .inner')
        if profile_container:
            labels = profile_container.find_all('span', class_='label')
            for label in labels:
                if 'Location' in label.get_text():
                    value_elem = label.find_next('strong', class_='value')
                    if value_elem:
                        location_text = value_elem.get_text(separator=' ', strip=True)
                        location_clean = ' '.join(location_text.split()).replace(' ,', ',')
                        if log_callback:
                            log_callback(f"Ubicación extraída del contenedor del perfil: {location_clean}", 
                                       "DEBUG", {"source": "location_extractor"})
                        return location_clean
        
        # Fallback: Si no encuentra en el contenedor específico, usar método original pero con advertencia
        all_labels = soup.find_all('span', class_='label')
        for label in all_labels:
            if 'Location' in label.get_text():
                value_elem = label.find_next('strong', class_='value')
                if value_elem:
                    location_text = value_elem.get_text(separator=' ', strip=True)
                    location_clean = ' '.join(location_text.split()).replace(' ,', ',')
                    if log_callback:
                        log_callback(f"Ubicación extraída con método fallback (posible ubicación incorrecta): {location_clean}", 
                                   "WARNING", {"source": "location_extractor"})
                    return location_clean
        
        if log_callback:
            log_callback("No se pudo extraer ubicación: elemento no encontrado", 
                       "WARNING", {"source": "location_extractor"})
        return 'Unknown'
        
    except Exception as e:
        if log_callback:
            log_callback(f"Error extrayendo ubicación: {str(e)}", "ERROR", 
                       {"source": "location_extractor", "error": str(e)})
        return 'Unknown'


