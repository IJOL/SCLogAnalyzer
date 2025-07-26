"""
RSI Organization Scraper

Este módulo proporciona funcionalidad para obtener miembros de organizaciones
de Star Citizen desde el endpoint oficial de RSI.
"""

import requests
import json
import re
from typing import Dict, Any, Optional, List, Union
from datetime import datetime


def _fetch_all_org_data(org: str) -> List[Dict[str, Any]]:
    """
    Función base que obtiene TODOS los datos de la organización (visibles y redacted).
    Esta es la única función que hace peticiones HTTP.
    
    Args:
        org: Símbolo de la organización (ej: "DZERO")
        
    Returns:
        Lista de diccionarios con TODOS los datos de miembros (visibles y redacted)
        
    Raises:
        requests.RequestException: Si hay error de red o HTTP
        ValueError: Si la respuesta no es válida
    """
    url = "https://robertsspaceindustries.com/api/orgs/getOrgMembers"
    
    # Headers de la petición con User-Agent realista
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    
    all_members = []
    page = 1
    pagesize = 20  # Pagesize de 20 para obtener todos los miembros
    redacted_counter = 1  # Contador global para redacted
    
    try:
        while True:
            # Payload para la petición
            payload = {
                "symbol": org,
                "pagesize": pagesize,
                "page": page
            }
            
            # Realizar petición POST
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            # Verificar que la respuesta tenga contenido
            if not response.text:
                raise ValueError(f"Respuesta vacía del servidor para {org}")
            
            # Extraer HTML de la respuesta
            try:
                data = response.json()
                if data is None:
                    raise ValueError("Respuesta JSON vacía del servidor")
                
                # Verificar que data sea un diccionario
                if not isinstance(data, dict):
                    raise ValueError(f"Respuesta JSON inválida: {type(data)}")
                
                # Verificar si hay error de throttling u otros errores
                if data.get('success') == 0:
                    error_msg = data.get('msg', 'Unknown error')
                    if 'throttled' in error_msg.lower():
                        raise ValueError(f"API throttled para {org}. Intenta más tarde.")
                    else:
                        raise ValueError(f"Error de API para {org}: {error_msg}")
                
                # Extraer data de forma segura
                data_section = data.get("data")
                if data_section is None:
                    raise ValueError("Respuesta JSON no contiene sección 'data'")
                
                html_content = data_section.get("html", "")
            except (ValueError, TypeError) as e:
                # Si el JSON no es válido, intentar extraer información del texto
                if "not found" in response.text.lower() or "404" in response.text.lower():
                    raise ValueError(f"Organización '{org}' no encontrada")
                elif "forbidden" in response.text.lower() or "403" in response.text.lower():
                    raise ValueError(f"Acceso denegado a la organización '{org}'")
                elif "throttled" in response.text.lower():
                    raise ValueError(f"API throttled para {org}. Intenta más tarde.")
                else:
                    raise ValueError(f"Error al parsear respuesta JSON de {org}: {e}")
            
            if not html_content:
                break
            
            # Parsear el HTML para obtener todos los miembros
            page_members = _parse_members_full_all(html_content, org, redacted_counter)
            
            # Actualizar el contador global de redacted
            for member in page_members:
                if member['visibility'] == 'R':
                    redacted_counter += 1
            
            # Añadir miembros de esta página al total
            all_members.extend(page_members)
            
            # Continuar con la siguiente página (no nos detenemos si obtenemos más de pagesize)
            page += 1
            
            # Limitar a un máximo de páginas para evitar bucles infinitos
            if page > 50:
                break
                
    except requests.RequestException as e:
        if response.status_code == 404:
            raise Exception(f"Organización '{org}' no encontrada")
        elif response.status_code == 403:
            raise Exception(f"Acceso denegado a la organización '{org}'")
        else:
            raise Exception(f"Error de red al obtener datos de {org}: {e}")
    except ValueError as e:
        raise Exception(f"Error al parsear respuesta de {org}: {e}")
    except Exception as e:
        raise Exception(f"Error inesperado al obtener datos de {org}: {e}")
    
    return all_members


def get_org_members(org: str, full: bool = False, redacted: bool = False) -> Union[List[str], List[Dict[str, Any]]]:
    """
    Obtiene los miembros de una organización de Star Citizen desde RSI.
    Usa la función base _fetch_all_org_data y filtra según los parámetros.
    
    Args:
        org: Símbolo de la organización (ej: "DZERO")
        full: Si True, devuelve datos completos. Si False, solo usernames
        redacted: Si True, incluye miembros redacted. Si False, solo miembros visibles
        
    Returns:
        Si full=False: Lista de usernames (str)
        Si full=True: Lista de diccionarios con datos completos
        
    Raises:
        requests.RequestException: Si hay error de red o HTTP
        ValueError: Si la respuesta no es válida
    """
    # Obtener TODOS los datos usando la función base
    all_members = _fetch_all_org_data(org)
    
    # Filtrar según el parámetro redacted
    if redacted:
        # Incluir todos los miembros (visibles y redacted)
        filtered_members = all_members
    else:
        # Solo miembros visibles
        filtered_members = [member for member in all_members if member.get('visibility') == 'V']
    
    if full:
        return filtered_members
    else:
        return [member.get('username', '') for member in filtered_members if member.get('username')]


def get_org_info(org: str) -> Dict[str, Any]:
    """
    Obtiene información general de una organización de Star Citizen.
    Usa la función base _fetch_all_org_data para obtener estadísticas precisas.
    
    Args:
        org: Símbolo de la organización (ej: "DZERO")
        
    Returns:
        Diccionario con información de la organización:
        - symbol: Símbolo de la organización
        - name: Nombre de la organización
        - total_members: Total de miembros (visibles + redacted)
        - visible_members: Número de miembros visibles
        - restricted_members: Número de miembros redacted
        
    Raises:
        requests.RequestException: Si hay error de red o HTTP
        ValueError: Si la respuesta no es válida
    """
    # Obtener TODOS los datos usando la función base
    all_members = _fetch_all_org_data(org)
    
    # Contar por visibilidad
    visible_count = len([m for m in all_members if m.get('visibility') == 'V'])
    restricted_count = len([m for m in all_members if m.get('visibility') == 'R'])
    total_count = len(all_members)
    
    # Obtener nombre de la organización del primer miembro
    org_name = org
    if all_members:
        org_name = all_members[0].get('org_name', org)
    
    return {
        'symbol': org,
        'name': org_name,
        'total_members': total_count,
        'visible_members': visible_count,
        'restricted_members': restricted_count
    }


def save_all_html_pages(org: str, output_file: str = "all_pages.html"):
    """
    Guarda todo el HTML de todas las páginas de una organización en un archivo.
    
    Args:
        org: Símbolo de la organización (ej: "DZERO")
        output_file: Nombre del archivo de salida
        
    Returns:
        Número total de páginas procesadas
    """
    
    # Validar parámetros
    if not org:
        raise ValueError("El símbolo de la organización es requerido")
    
    # URL del endpoint
    url = "https://robertsspaceindustries.com/api/orgs/getOrgMembers"
    
    # Headers de la petición con User-Agent realista
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    
    all_html = []
    page = 1
    pagesize = 20
    
    try:
        while True:
            # Body de la petición
            payload = {
                "symbol": org,
                "pagesize": pagesize,
                "page": page
            }
            
            # Realizar petición POST
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            # Verificar si la petición fue exitosa
            response.raise_for_status()
            
            # Obtener respuesta JSON
            data = response.json()
            
            # Verificar si la respuesta es exitosa
            if data.get('success') != 1:
                error_msg = data.get('msg', 'Unknown error')
                if 'throttled' in error_msg.lower():
                    raise ValueError(f"API throttled para {org}. Intenta más tarde.")
                else:
                    raise requests.RequestException(f"Error en respuesta RSI: {error_msg}")
            
            # Extraer HTML de la respuesta de forma segura
            data_section = data.get('data')
            if data_section is None:
                raise ValueError("Respuesta JSON no contiene sección 'data'")
            
            html_content = data_section.get('html', '')
            
            if not html_content:
                break
            
            # Añadir HTML de esta página al total
            all_html.append(f"<!-- PÁGINA {page} -->")
            all_html.append(html_content)
            all_html.append("<!-- FIN PÁGINA {page} -->\n")
            
            # Continuar con la siguiente página
            page += 1
            
            # Limitar a un máximo de páginas para evitar bucles infinitos
            if page > 50:
                break
        
        # Guardar todo el HTML en el archivo
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"<!-- HTML COMPLETO DE TODAS LAS PÁGINAS PARA {org} -->\n")
            f.write(f"<!-- Total de páginas: {page-1} -->\n")
            f.write(f"<!-- Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->\n\n")
            f.write('\n'.join(all_html))
        
        return page - 1
        
    except Exception as e:
        print(f"Error: {e}")
        return 0


def _parse_org_info(html_content: str, org_symbol: str) -> Dict[str, Any]:
    """
    Extrae información general de la organización desde el HTML.
    
    Args:
        html_content: HTML de la respuesta RSI
        org_symbol: Símbolo de la organización
        
    Returns:
        Diccionario con información de la organización
    """
    # Extraer nombre de la organización del primer elemento
    org_name_match = re.search(r'data-org-name="([^"]*)"', html_content)
    org_name = org_name_match.group(1) if org_name_match else org_symbol
    
    # Contar miembros usando el patrón correcto para detectar redacted
    visible_count = len(re.findall(r'<li class="[^"]*org-visibility-V[^"]*"', html_content))
    restricted_count = len(re.findall(r'<li class="[^"]*org-visibility-R[^"]*"', html_content))
    total_count = visible_count + restricted_count
    
    return {
        'symbol': org_symbol,
        'name': _clean_html(org_name),
        'total_members': total_count,
        'visible_members': visible_count,
        'restricted_members': restricted_count
    }


def _parse_members_simple(html_content: str) -> List[str]:
    """
    Extrae solo los usernames de los miembros visibles desde el HTML.
    
    Args:
        html_content: HTML de la respuesta RSI
        
    Returns:
        Lista de usernames (str) - solo miembros visibles
    """
    usernames = []
    
    # Patrón para extraer usernames solo de miembros visibles
    pattern = r'<li class="member-item[^"]*org-visibility-V"[^>]*>.*?href="/citizens/([^"]+)"'
    
    matches = re.findall(pattern, html_content, re.DOTALL)
    for match in matches:
        if match and match.strip():
            usernames.append(match.strip())
    
    return usernames


def _parse_members_full(html_content: str, org_symbol: str) -> List[Dict[str, Any]]:
    """
    Extrae datos completos de los miembros visibles desde el HTML.
    
    Args:
        html_content: HTML de la respuesta RSI
        org_symbol: Símbolo de la organización
        
    Returns:
        Lista de diccionarios con datos completos de cada miembro - solo visibles
    """
    members = []
    
    # Patrón para extraer solo miembros visibles
    member_pattern = r'<li class="member-item[^"]*org-visibility-V"[^>]*data-org-sid="([^"]*)" data-org-name="([^"]*)">(.*?)</li>'
    
    member_matches = re.findall(member_pattern, html_content, re.DOTALL)
    
    for org_sid, org_name, member_html in member_matches:
        try:
            # Extraer username del href
            username_match = re.search(r'href="/citizens/([^"]*)"', member_html)
            username = username_match.group(1) if username_match else ""
            
            # Extraer display name
            name_match = re.search(r'<span class="[^"]*name[^"]*">([^<]*)</span>', member_html)
            display_name = name_match.group(1).strip() if name_match else ""
            
            # Extraer nick
            nick_match = re.search(r'<span class="[^"]*nick[^"]*">([^<]*)</span>', member_html)
            nick = nick_match.group(1).strip() if nick_match else ""
            
            # Extraer rank
            rank_match = re.search(r'<span class="rank">([^<]*)</span>', member_html)
            rank = rank_match.group(1).strip() if rank_match else ""
            
            # Extraer avatar URL
            avatar_match = re.search(r'<img[^>]*src="([^"]*)"', member_html)
            avatar_url = avatar_match.group(1) if avatar_match else ""
            
            # Construir profile URL
            profile_url = f"https://robertsspaceindustries.com/citizens/{username}" if username else ""
            
            # Limpiar datos HTML
            username = _clean_html(username)
            display_name = _clean_html(display_name)
            nick = _clean_html(nick)
            rank = _clean_html(rank)
            avatar_url = _clean_html(avatar_url)
            org_name = _clean_html(org_name)
            
            # Solo incluir si el username no está vacío
            if username and username.strip():
                member_data = {
                    'username': username.strip(),
                    'display_name': display_name.strip() if display_name else username.strip(),
                    'nick': nick.strip() if nick else username.strip(),
                    'rank': rank.strip() if rank else 'Unknown',
                    'avatar_url': avatar_url.strip() if avatar_url else '',
                    'profile_url': profile_url.strip() if profile_url else '',
                    'visibility': 'V',  # Siempre visible en esta función
                    'org_symbol': org_sid.strip() if org_sid else org_symbol,
                    'org_name': org_name.strip() if org_name else ''
                }
                members.append(member_data)
                
        except Exception as e:
            # Si hay error parseando un miembro, continuar con el siguiente
            continue
    
    return members


def _parse_members_simple_all(html_content: str) -> List[str]:
    """
    Extrae TODOS los usernames (visibles y no visibles) desde el HTML.
    
    Args:
        html_content: HTML de la respuesta RSI
        
    Returns:
        Lista de usernames (str) - TODOS los miembros
    """
    usernames = []
    
    # Patrón para extraer usernames de TODOS los miembros (visibles y no visibles)
    pattern = r'<li class="member-item[^"]*"[^>]*>.*?href="/citizens/([^"]+)"'
    
    matches = re.findall(pattern, html_content, re.DOTALL)
    for match in matches:
        if match and match.strip():
            usernames.append(match.strip())
    
    return usernames


def _parse_members_full_all(html_content: str, org_symbol: str, redacted_counter: int) -> List[Dict[str, Any]]:
    """
    Extrae datos completos de TODOS los miembros (visibles y no visibles) desde el HTML.
    """
    members = []
    
    # Buscar TODOS los elementos li con member-item, tanto visibles como redacted
    # Patrón específico para detectar ambos tipos
    all_li_pattern = r'<li class=\"([^\"]*)\"[^>]*data-org-sid=\"([^\"]*)\" data-org-name=\"([^\"]*)\">(.*?)</li>'
    all_matches = re.findall(all_li_pattern, html_content, re.DOTALL)
    
    for li_classes, org_sid, org_name, member_html in all_matches:
        try:
            # Determinar visibilidad - buscar org-visibility-R en las clases
            if 'org-visibility-R' in li_classes:
                visibility = 'R'
                # Para miembros redacted, usar nombre genérico numerado
                username = f"redacted_{redacted_counter}"
                redacted_counter += 1
                display_name = username
                nick = username
            else:
                visibility = 'V'
                # Extraer username del href para miembros visibles
                username_match = re.search(r'href="/citizens/([^"]+)"', member_html)
                username = username_match.group(1) if username_match else None
                
                # Extraer display name
                display_match = re.search(r'<span class="display-name">([^<]+)</span>', member_html)
                display_name = display_match.group(1) if display_match else username
                
                # Extraer nick
                nick_match = re.search(r'<span class="nick">([^<]+)</span>', member_html)
                nick = nick_match.group(1) if nick_match else username
            
            # Extraer rank
            rank_match = re.search(r'<span class="rank">([^<]+)</span>', member_html)
            rank = rank_match.group(1) if rank_match else "Unknown"
            
            # Extraer avatar URL
            avatar_match = re.search(r'<img[^>]*src="([^"]*)"[^>]*class="avatar"', member_html)
            avatar_url = avatar_match.group(1) if avatar_match else ""
            
            # Construir profile URL
            profile_url = f"https://robertsspaceindustries.com/citizens/{username}" if username else ""
            
            if username and username.strip():
                member_data = {
                    'username': username,
                    'display_name': display_name,
                    'nick': nick,
                    'rank': rank,
                    'avatar_url': avatar_url,
                    'profile_url': profile_url,
                    'visibility': visibility,  # V para visible, R para restringido
                    'org_symbol': org_symbol,
                    'org_name': org_name
                }
                members.append(member_data)
        except Exception as e:
            continue
    
    return members


def _clean_html(text: str) -> str:
    """
    Limpia entidades HTML comunes.
    
    Args:
        text: Texto con posibles entidades HTML
        
    Returns:
        Texto limpio
    """
    if not text:
        return ""
    
    # Reemplazar entidades HTML comunes
    replacements = {
        '&nbsp;': ' ',
        '&amp;': '&',
        '&lt;': '<',
        '&gt;': '>',
        '&quot;': '"',
        '&#39;': "'",
        '&apos;': "'"
    }
    
    for entity, replacement in replacements.items():
        text = text.replace(entity, replacement)
    
    return text.strip() 