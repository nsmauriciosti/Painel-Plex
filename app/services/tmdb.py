import requests
import logging
from ..config import load_or_create_config

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"

def get_tmdb_api_key():
    config = load_or_create_config()
    return config.get('TMDB_API_KEY')

def fetch_from_tmdb(endpoint, params=None):
    api_key = get_tmdb_api_key()
    if not api_key:
        return None
    
    if params is None:
        params = {}
    params['api_key'] = api_key
    params['language'] = 'pt-BR'

    try:
        url = f"{TMDB_BASE_URL}{endpoint}"
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Erro ao buscar no TMDB ({endpoint}): {e}")
        return None

def get_recommendations_by_title(title, media_type='movie'):
    """Busca o ID da mídia pelo título e depois retorna recomendações."""
    # 1. Procurar o ID
    search_data = fetch_from_tmdb(f"/search/{media_type}", {"query": title, "page": 1})
    if not search_data or not search_data.get('results'):
        return []
    
    media_id = search_data['results'][0]['id']
    
    # 2. Buscar recomendações
    rec_data = fetch_from_tmdb(f"/{media_type}/{media_id}/recommendations", {"page": 1})
    if rec_data and rec_data.get('results'):
        return rec_data['results']
    return []

def get_trending(media_type='all', time_window='week'):
    data = fetch_from_tmdb(f"/trending/{media_type}/{time_window}")
    if data and data.get('results'):
        return data['results']
    return []
