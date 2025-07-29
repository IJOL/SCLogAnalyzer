"""
RSI Organization Scraper

Este módulo proporciona funcionalidad para obtener miembros de organizaciones
de Star Citizen desde el endpoint oficial de RSI.
"""

import requests
import json
import re
import time
import random
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

# Import MessageBus for logging
from .message_bus import message_bus, MessageLevel


def _calculate_delay(attempt: int, base_delay=1.0, max_delay=60.0) -> float:
    """
    Calcula delay con backoff exponencial y jitter para evitar thundering herd.
    
    Args:
        attempt: Número de intento actual (0-based)
        base_delay: Delay base en segundos
        max_delay: Delay máximo en segundos
        
    Returns:
        Delay en segundos con jitter
    """
    delay = min(base_delay * (2 ** attempt), max_delay)
    # Añadir jitter para evitar sincronización de reintentos
    jitter = random.uniform(0, 0.1 * delay)
    return delay + jitter


def _should_retry(exception) -> bool:
    """
    Determina si reintentar basado en tipo de error.
    
    Args:
        exception: Excepción capturada
        
    Returns:
        True si se debe reintentar, False en caso contrario
    """
    if isinstance(exception, requests.exceptions.HTTPError):
        # Solo reintentar para throttling (429)
        return exception.response.status_code == 429
    elif isinstance(exception, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        # Siempre reintentar errores de red
        return True
    else:
        # No reintentar otros errores
        return False


def _handle_throttling_error(org: str, attempt: int, error_msg: str):
    """
    Manejo específico para errores de throttling (429, rate limiting).
    
    Args:
        org: Símbolo de la organización
        attempt: Número de intento actual
        error_msg: Mensaje de error
    """
    # Delay más largo para throttling (mínimo 30 segundos)
    delay = max(30, _calculate_delay(attempt))
    
    # Logging específico para throttling
    message_bus.publish(
        content=f"[{org}] Throttling detectado (intento {attempt}): {error_msg}. Esperando {delay}s...",
        level=MessageLevel.WARNING,
        metadata={"source": "rsi_org_scraper", "action": "throttling", "attempt": attempt}
    )
    
    time.sleep(delay)


def _handle_network_error(org: str, attempt: int, error_msg: str):
    """
    Manejo específico para errores de red (timeout, connection error).
    
    Args:
        org: Símbolo de la organización
        attempt: Número de intento actual
        error_msg: Mensaje de error
    """
    # Delay más corto para errores de red (máximo 10 segundos)
    delay = min(10, _calculate_delay(attempt))
    
    # Logging específico para errores de red
    message_bus.publish(
        content=f"[{org}] Error de red (intento {attempt}): {error_msg}. Reintentando en {delay}s...",
        level=MessageLevel.WARNING,
        metadata={"source": "rsi_org_scraper", "action": "network_error", "attempt": attempt}
    )
    
    time.sleep(delay)


def _make_request_with_retry(org: str, page: int, max_retries=5) -> Dict:
    """
    Hace petición HTTP con reintentos automáticos.
    
    Args:
        org: Símbolo de la organización
        page: Número de página
        max_retries: Número máximo de reintentos
        
    Returns:
        Respuesta JSON de la API
        
    Raises:
        Exception: Si fallan todos los reintentos
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
    
    payload = {
        "symbol": org,
        "pagesize": 20,
        "page": page
    }
    
    for attempt in range(max_retries + 1):
        try:
            # Realizar petición POST
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            # Verificar que la respuesta tenga contenido
            if not response.text:
                raise ValueError(f"Respuesta vacía del servidor para {org}")
            
            # Parsear JSON
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
                    raise requests.exceptions.HTTPError(f"API throttled para {org}. Intenta más tarde.", response=response)
                else:
                    raise ValueError(f"Error de API para {org}: {error_msg}")
            
            return data
            
        except requests.exceptions.HTTPError as e:
            if _should_retry(e) and attempt < max_retries:
                if e.response.status_code == 429:  # Throttling
                    _handle_throttling_error(org, attempt, str(e))
                else:
                    # Otros errores HTTP que se pueden reintentar
                    delay = _calculate_delay(attempt)
                    message_bus.publish(
                        content=f"[{org}] Error HTTP {e.response.status_code} (intento {attempt}): {str(e)}. Reintentando en {delay}s...",
                        level=MessageLevel.WARNING,
                        metadata={"source": "rsi_org_scraper", "action": "http_error", "attempt": attempt, "status_code": e.response.status_code}
                    )
                    time.sleep(delay)
                continue
            else:
                raise
                
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if _should_retry(e) and attempt < max_retries:
                _handle_network_error(org, attempt, str(e))
                continue
            else:
                raise Exception(f"Error de red persistente para {org} después de {max_retries} intentos")
                
        except Exception as e:
            if _should_retry(e) and attempt < max_retries:
                delay = _calculate_delay(attempt)
                message_bus.publish(
                    content=f"[{org}] Error inesperado (intento {attempt}): {str(e)}. Reintentando en {delay}s...",
                    level=MessageLevel.WARNING,
                    metadata={"source": "rsi_org_scraper", "action": "retry", "attempt": attempt}
                )
                time.sleep(delay)
            else:
                raise
    
    # Nunca debería llegar aquí, pero por si acaso
    raise Exception(f"Error inesperado para {org} después de {max_retries} intentos")


def _log_progress(org: str, page: int, total_pages: int, members_count: int, expected_total: int):
    """
    Logging detallado del progreso usando MessageBus.
    
    Args:
        org: Símbolo de la organización
        page: Página actual
        total_pages: Total de páginas estimadas
        members_count: Número de miembros obtenidos hasta ahora
        expected_total: Total esperado de miembros
    """
    progress = (page / total_pages) * 100 if total_pages > 0 else 0
    message_bus.publish(
        content=f"[{org}] Página {page}/{total_pages} ({progress:.1f}%) - {members_count}/{expected_total} miembros",
        level=MessageLevel.INFO,
        metadata={"source": "rsi_org_scraper", "action": "progress"}
    )

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
    all_members = []
    page = 1
    redacted_counter = 1  # Contador global para redacted
    expected_total = None
    
    try:
        # Obtener primer paquete para extraer totalrows
        message_bus.publish(
            content=f"[{org}] Iniciando obtención de datos...",
            level=MessageLevel.INFO,
            metadata={"source": "rsi_org_scraper", "action": "start"}
        )
        
        first_response = _make_request_with_retry(org, 1)
        data_section = first_response.get("data")
        if data_section is None:
            raise ValueError("Respuesta JSON no contiene sección 'data'")
        
        expected_total = data_section.get('totalrows')
        if expected_total is None:
            message_bus.publish(
                content=f"[{org}] Advertencia: No se pudo obtener totalrows, continuando sin validación",
                level=MessageLevel.WARNING,
                metadata={"source": "rsi_org_scraper", "action": "no_totalrows"}
            )
        
        html_content = data_section.get("html", "")
        if html_content:
            # Parsear el HTML para obtener todos los miembros de la primera página
            page_members = _parse_members_full_all(html_content, org, redacted_counter)
            
            # Actualizar el contador global de redacted
            for member in page_members:
                if member['visibility'] == 'R':
                    redacted_counter += 1
            
            # Añadir miembros de esta página al total
            all_members.extend(page_members)
            
            # Logging del progreso inicial
            if expected_total:
                _log_progress(org, 1, (expected_total + 19) // 20, len(all_members), expected_total)
        
        # Continuar con el resto de páginas
        page = 2
        while True:
            try:
                # Hacer petición con reintentos
                data = _make_request_with_retry(org, page)
                
                # Extraer data de forma segura
                data_section = data.get("data")
                if data_section is None:
                    raise ValueError("Respuesta JSON no contiene sección 'data'")
                
                html_content = data_section.get("html", "")
                
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
                
                # Logging del progreso
                if expected_total:
                    total_pages = (expected_total + 19) // 20
                    _log_progress(org, page, total_pages, len(all_members), expected_total)
                
                # Delay aleatorio entre páginas para evitar throttling
                delay = random.uniform(0.5, 3.0)  # Delay entre 0.5 y 3 segundos
                message_bus.publish(
                    content=f"[{org}] Esperando {delay:.1f}s antes de la siguiente página...",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "rsi_org_scraper", "action": "page_delay", "delay": delay}
                )
                time.sleep(delay)
                
                # Continuar con la siguiente página
                page += 1
                
                # Limitar a un máximo de páginas para evitar bucles infinitos
                if page > 150:
                    message_bus.publish(
                        content=f"[{org}] Advertencia: Límite de páginas alcanzado (150), deteniendo obtención",
                        level=MessageLevel.WARNING,
                        metadata={"source": "rsi_org_scraper", "action": "page_limit"}
                    )
                    break
                    
            except Exception as e:
                message_bus.publish(
                    content=f"[{org}] Error en página {page}: {str(e)}",
                    level=MessageLevel.ERROR,
                    metadata={"source": "rsi_org_scraper", "action": "page_error", "page": page}
                )
                raise
        
        # Validación simple: solo informar si no coincide, pero no reintentar
        if expected_total and len(all_members) != expected_total:
            message_bus.publish(
                content=f"[{org}] Advertencia: Número de miembros obtenidos ({len(all_members)}) no coincide con totalrows ({expected_total})",
                level=MessageLevel.WARNING,
                metadata={"source": "rsi_org_scraper", "action": "validation_mismatch", "obtained": len(all_members), "expected": expected_total}
            )
        
        # Logging final
        message_bus.publish(
            content=f"[{org}] Obtención completada: {len(all_members)} miembros totales",
            level=MessageLevel.INFO,
            metadata={"source": "rsi_org_scraper", "action": "complete", "total_members": len(all_members)}
        )
                
    except Exception as e:
        message_bus.publish(
            content=f"[{org}] Error final: {str(e)}",
            level=MessageLevel.ERROR,
            metadata={"source": "rsi_org_scraper", "action": "final_error"}
        )
        raise
    
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


def get_org_members_count(org: str) -> int:
    """
    Obtiene solo el número total de miembros de una organización.
    Esta es la función más rápida disponible.
    
    Args:
        org: Símbolo de la organización (ej: "DZERO")
        
    Returns:
        Número total de miembros de la organización
        
    Raises:
        requests.RequestException: Si hay error de red o HTTP
        ValueError: Si la respuesta no es válida
    """
    try:
        # Obtener solo la primera página
        first_response = _make_request_with_retry(org, 1)
        data_section = first_response.get("data")
        if data_section is None:
            raise ValueError("Respuesta JSON no contiene sección 'data'")
        
        total_members = data_section.get('totalrows', 0)
        
        message_bus.publish(
            content=f"[{org}] Número de miembros obtenido: {total_members}",
            level=MessageLevel.DEBUG,
            metadata={"source": "rsi_org_scraper", "action": "count_only", "total_members": total_members}
        )
        
        return total_members
        
    except Exception as e:
        message_bus.publish(
            content=f"[{org}] Error obteniendo número de miembros: {str(e)}",
            level=MessageLevel.ERROR,
            metadata={"source": "rsi_org_scraper", "action": "count_error"}
        )
        raise Exception(f"Error al obtener número de miembros de {org}: {e}")


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