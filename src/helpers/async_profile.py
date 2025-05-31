"""
Async Profile Scraper Helper
Enhanced helper for scraping RSI player profiles with maximum information extraction
Extracts: UEE citizen record, handle name, location, fluency, title/rank, SID, org rank
Maintains full compatibility with existing code - same function signature and event format
Uses robust HTML structure parsing instead of fragile regex patterns
"""

import threading
import requests
from bs4 import BeautifulSoup
from .message_bus import message_bus, MessageLevel
import datetime


def extract_enhanced_profile_data(soup):
    """Extrae toda la información disponible de la página principal del perfil usando parsing HTML robusto"""
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
        'enlisted_dt': None  # Nuevo campo: datetime.datetime o None
    }
    
    try:
        # 1. UEE Citizen Record
        try:
            citizen_record_elem = soup.select_one('p.citizen-record .value')
            if citizen_record_elem:
                profile_data['uee_citizen_record'] = citizen_record_elem.get_text(strip=True)
        except Exception:
            pass
        
        # 2. Display Name (primer nombre en profile)
        try:
            display_name_elem = soup.select_one('div.profile.left-col .info p.entry:first-child .value')
            if display_name_elem:
                profile_data['display_name'] = display_name_elem.get_text(strip=True)
        except Exception:
            pass
        
        # 3. Handle Name
        try:
            labels = soup.find_all('span', class_='label')
            for label in labels:
                if 'Handle name' in label.get_text():
                    value_elem = label.find_next('strong', class_='value')
                    if value_elem:
                        profile_data['handle_name'] = value_elem.get_text(strip=True)
                        break
        except Exception:
            pass
        
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
        
        # 7. Location
        try:
            labels = soup.find_all('span', class_='label')
            for label in labels:
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
            level=MessageLevel.DEBUG,
            metadata={"source": "enhanced_profile_html_parser"}
        )
    
    return profile_data


def scrape_profile_async(player_name: str, metadata: dict = None):
    """Thread simple para scraping de perfil RSI según Plan MEGA SIMPLE"""
    metadata = metadata or {}   
    def scrape(metadata):
        try:
            url = f"https://robertsspaceindustries.com/en/citizens/{player_name}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
              
                # Extraer información mejorada
                enhanced_profile_data = extract_enhanced_profile_data(soup)
                
                metadata.update(enhanced_profile_data)
                
                # Emitir evento actor_profile (misma signatura que antes)
                message_bus.emit('actor_profile', 
                                  player_name, 
                                  metadata.get('main_org_sid'), 
                                  metadata.get('enlisted'), metadata)
        except Exception as e:
            # Fail silently según el plan
            message_bus.publish(
                content=f"Profile scraping failed for {player_name}: {e}",
                level=MessageLevel.DEBUG,
                metadata={"source": "profile_scraper"}
            )
    
    thread = threading.Thread(target=scrape, args=[metadata], daemon=True)
    thread.start()

def async_profile_request(player_name: str, action="get", data=None):
    """
    Async profile request function that handles different actions.
    
    Args:
        player_name (str): The player name to process
        action (str): The action to perform ("get", "analyze", etc.)
        data (dict): Optional data context for the request
        
    Returns:
        dict: Result of the profile request operation
    """
    message_bus.publish(
        content=f"Processing profile request for {player_name} with action={action}",
        level=MessageLevel.INFO,
        metadata={"source": "profile_request"}
    )
    
    if action == "get":
        # Perform profile scraping and analysis
        result = scrape_profile_async(player_name, data or {})
        return result
    else:
        error_msg = f"Unsupported action: {action}"
        message_bus.publish(
            content=error_msg,
            level=MessageLevel.ERROR,
            metadata={"source": "profile_request"}
        )
        raise ValueError(error_msg)
