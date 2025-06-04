# Handles interactions with the API-Football

import requests
import os
import json
import statistics # For calculating averages
import logging
from datetime import datetime, timedelta

# --- Configuration ---
API_KEY = os.getenv("API_FOOTBALL_KEY", "0a61cabf9fe788a9ecd7c6c1d47eda2a") 
API_HOST = "v3.football.api-sports.io"
BASE_URL = f"https://{API_HOST}"
DEFAULT_BOOKMAKER_ID = 8 # Default to Bet365

HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": API_HOST
}

# Setup basic logging - CORRECTED FORMAT STRING
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Function for API Calls ---

def _make_api_request(endpoint, params={}):
    """Makes a request to the API-Football endpoint and handles basic errors."""
    url = f"{BASE_URL}/{endpoint}"
    if API_KEY == "0a61cabf9fe788a9ecd7c6c1d47eda2a" or not API_KEY: # Check against actual key
        logging.error("API_FOOTBALL_KEY not set or is the example key. Please provide a valid key.")
        return {"error": True, "message": "API Key não configurada ou inválida."}
        
    try:
        logging.info(f"Chamando API: {url} com params: {params}")
        response = requests.get(url, headers=HEADERS, params=params, timeout=30) 
        response.raise_for_status()
        
        data = response.json()
        
        api_errors = data.get("errors")
        if isinstance(api_errors, list) and len(api_errors) > 0:
             logging.error(f"API Error List para {endpoint}: {api_errors}")
             # Try to extract a meaningful message
             msg = str(api_errors[0]) if isinstance(api_errors[0], (str, dict)) else str(api_errors)
             return {"error": True, "message": msg}
        if isinstance(api_errors, dict) and len(api_errors) > 0:
             logging.error(f"API Error Dict para {endpoint}: {api_errors}")
             msg = str(api_errors)
             if "plan" in msg.lower() or "limit" in msg.lower() or "quota" in msg.lower():
                 logging.warning(f"API Plan/Limit Error: {api_errors}")
                 return {"error": True, "message": f"Erro de Plano/Limite API: {msg}"}
             return {"error": True, "message": msg}
             
        api_message = data.get("message")
        if api_message:
            logging.warning(f"API Message/Error para {endpoint}: {api_message}")
            # Check for messages indicating resource not found or permission issues
            if "subscription" in api_message.lower() or \
               "permission" in api_message.lower() or \
               "not found" in api_message.lower() or \
               "doesn't exist" in api_message.lower(): # Corrected apostrophe
                 return {"error": True, "message": api_message}
                 
        if "response" not in data or not data["response"]:
            # Check for specific informative messages even without errors
            if api_message and ("not found" in api_message.lower() or "doesn't exist" in api_message.lower()): # Corrected apostrophe
                 logging.warning(f"API informou '{api_message}' para {endpoint} com params: {params}") # Use single quotes inside f-string
                 return {"error": True, "message": api_message} # Treat as error for flow control
            logging.warning(f"Resposta vazia ou campo 'response' ausente para {endpoint} com params: {params}") # Use single quotes inside f-string
            return [] # Return empty list for consistency when no data found
            
        return data["response"]
        
    except requests.exceptions.Timeout as e:
        logging.error(f"API Request Timeout para {url}: {e}")
        return {"error": True, "message": f"Timeout na comunicação com a API: {e}"}
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP Error para {url}: {e.response.status_code} {e.response.text}")
        # Provide more specific feedback for common errors
        if e.response.status_code == 401 or e.response.status_code == 403:
            return {"error": True, "message": f"Erro de Autenticação API ({e.response.status_code}): Verifique sua chave."}
        if e.response.status_code == 404:
             return {"error": True, "message": f"Recurso não encontrado na API ({e.response.status_code})."}
        if e.response.status_code == 429:
             return {"error": True, "message": f"Limite de requisições API excedido ({e.response.status_code})."}
        return {"error": True, "message": f"Erro HTTP {e.response.status_code} na comunicação com a API."}
    except requests.exceptions.RequestException as e:
        logging.error(f"API Request Error para {url}: {e}")
        return {"error": True, "message": f"Erro de Rede ao conectar com a API: {e}"}
    except json.JSONDecodeError as e:
        logging.error(f"Falha ao decodificar JSON de {url}: {e}")
        return {"error": True, "message": f"Erro ao processar resposta da API (JSON inválido): {e}"}

# --- Data Processing Helper Functions ---

def _get_average_from_stats(stats_data, category, sub_category, location="total"):
    """Safely extracts average values from the team statistics structure."""
    if not stats_data or not isinstance(stats_data, dict):
        return 0.0
    try:
        value_str = stats_data.get(category, {}).get(sub_category, {}).get("average", {}).get(location)
        if value_str is not None:
            return float(value_str)
        else:
            value_str_total = stats_data.get(category, {}).get(sub_category, {}).get("average", {}).get("total")
            if value_str_total is not None:
                 return float(value_str_total)
            else:
                 return 0.0
    except (TypeError, ValueError, AttributeError) as e:
        logging.warning(f"Erro ao parsear média para {category}.{sub_category}.{location}: {e}")
        return 0.0

def _get_total_from_stats(stats_data, category, sub_category, location="total"):
    """Safely extracts total values from the team statistics structure."""
    if not stats_data or not isinstance(stats_data, dict):
        return 0
    try:
        value = stats_data.get(category, {}).get(sub_category, {}).get("total", {}).get(location)
        if value is not None:
            return int(value)
        else:
            value_total = stats_data.get(category, {}).get(sub_category, {}).get("total", {}).get("total")
            if value_total is not None:
                 return int(value_total)
            else:
                 return 0
    except (TypeError, ValueError, AttributeError) as e:
        logging.warning(f"Erro ao parsear total para {category}.{sub_category}.{location}: {e}")
        return 0

def _calculate_strengths(home_stats, away_stats):
    """Calculates attack and defense strengths based on team stats."""
    if not isinstance(home_stats, dict) or not isinstance(away_stats, dict):
        logging.error("Dados de estatísticas inválidos para cálculo de força.")
        return 1.0, 1.0
        
    avg_goals_scored_home = _get_average_from_stats(home_stats, "goals", "for", "home")
    avg_goals_conceded_home = _get_average_from_stats(home_stats, "goals", "against", "home")
    avg_goals_scored_away = _get_average_from_stats(away_stats, "goals", "for", "away")
    avg_goals_conceded_away = _get_average_from_stats(away_stats, "goals", "against", "away")

    league_avg_home_goals = _get_average_from_stats(home_stats, "goals", "for", "total") or 1.4
    league_avg_away_goals = _get_average_from_stats(away_stats, "goals", "for", "total") or 1.1
    league_avg_conceded_home = _get_average_from_stats(home_stats, "goals", "against", "total") or league_avg_away_goals
    league_avg_conceded_away = _get_average_from_stats(away_stats, "goals", "against", "total") or league_avg_home_goals

    if league_avg_home_goals == 0 or league_avg_away_goals == 0 or league_avg_conceded_home == 0 or league_avg_conceded_away == 0:
        logging.warning("Médias da liga zeradas detectadas. Usando forças neutras (1.0).")
        return 1.5, 1.2

    home_attack_strength = avg_goals_scored_home / league_avg_home_goals
    home_defense_strength = avg_goals_conceded_home / league_avg_away_goals
    away_attack_strength = avg_goals_scored_away / league_avg_away_goals
    away_defense_strength = avg_goals_conceded_away / league_avg_home_goals

    lambda_casa = home_attack_strength * away_defense_strength * league_avg_home_goals 
    lambda_fora = away_attack_strength * home_defense_strength * league_avg_away_goals
    
    lambda_casa = max(0.1, lambda_casa)
    lambda_fora = max(0.1, lambda_fora)

    logging.info(f"Forças Calculadas: HA={home_attack_strength:.2f}, HD={home_defense_strength:.2f}, AA={away_attack_strength:.2f}, AD={away_defense_strength:.2f}")
    logging.info(f"Lambdas Calculados: Casa={lambda_casa:.2f}, Fora={lambda_fora:.2f}")

    return lambda_casa, lambda_fora

def _calculate_avg_corners(stats_data, location):
    """Calculates average corners from stats data, prioritizing specific location."""
    avg_corners = 0.0
    corners_for_avg = _get_average_from_stats(stats_data, "corners", "for", location) 
    
    if corners_for_avg > 0:
        avg_corners = corners_for_avg
    else:
        corners_avg_total = _get_average_from_stats(stats_data, "corners", "for", "total")
        if corners_avg_total > 0:
            avg_corners = corners_avg_total
            logging.warning(f"Usando média total de cantos ({avg_corners:.2f}) como fallback para {location}.")
        else:
            default_val = 6.0 if location == "home" else 5.0
            avg_corners = default_val
            logging.warning(f"Usando média padrão de cantos ({avg_corners:.1f}) para {location}.")
            
    logging.info(f"Média de Cantos ({location}): {avg_corners:.2f}")
    return avg_corners

# --- Core Data Fetching Functions ---

def find_team_id(team_name):
    """Finds the team ID based on the team name."""
    logging.info(f"Buscando ID para time: {team_name}")
    response_data = _make_api_request("teams", params={"search": team_name})
    
    if response_data is None or isinstance(response_data, dict) and response_data.get("error"):
        msg = response_data.get("message") if isinstance(response_data, dict) else "Erro desconhecido"
        logging.error(f"Erro API ao buscar ID do time {team_name}: {msg}")
        return None, msg
        
    if response_data: 
        exact_matches = [r for r in response_data if isinstance(r, dict) and r.get("team", {}).get("name", "").lower() == team_name.lower()]
        if exact_matches:
             found_id = exact_matches[0]["team"]["id"]
             logging.info(f"Encontrado ID exato: {found_id} para {team_name}")
             return found_id, None
        elif len(response_data) > 0 and isinstance(response_data[0], dict) and "team" in response_data[0]:
             found_id = response_data[0]["team"]["id"]
             found_name = response_data[0]["team"]["name"]
             logging.warning(f"Sem correspondência exata para {team_name}. Usando primeiro resultado: {found_name} (ID: {found_id})")
             return found_id, None
        else:
             msg = f"Nenhum time encontrado ou estrutura inválida para \"{team_name}\""
             logging.warning(msg)
             return None, msg
    else:
        msg = f"Nenhum time encontrado para \"{team_name}\""
        logging.warning(msg)
        return None, msg

def find_league_id(league_name, country_name=None, season=None):
    """Finds the league ID based on the league name, optional country and season."""
    log_msg = f"Buscando ID para liga: {league_name}"
    params = {"search": league_name}
    if country_name:
        params["country"] = country_name
        log_msg += f" em {country_name}"
    if season:
        params["season"] = season
        log_msg += f" para temporada {season}"
    logging.info(log_msg)
        
    response_data = _make_api_request("leagues", params=params)
    
    if response_data is None or isinstance(response_data, dict) and response_data.get("error"):
        msg = response_data.get("message") if isinstance(response_data, dict) else "Erro desconhecido"
        logging.error(f"Erro API ao buscar ID da liga {league_name}: {msg}")
        return None, msg
        
    if response_data:
        exact_matches = [r for r in response_data if isinstance(r, dict) and r.get("league", {}).get("name", "").lower() == league_name.lower()]
        if exact_matches:
             found_id = exact_matches[0]["league"]["id"]
             logging.info(f"Encontrado ID exato: {found_id} para {league_name}")
             return found_id, None
        elif len(response_data) > 0 and isinstance(response_data[0], dict) and "league" in response_data[0]:
             found_id = response_data[0]["league"]["id"]
             found_name = response_data[0]["league"]["name"]
             logging.warning(f"Sem correspondência exata para {league_name}. Usando primeiro resultado: {found_name} (ID: {found_id})")
             return found_id, None
        else:
             msg = f"Nenhuma liga encontrada ou estrutura inválida para \"{league_name}\""
             logging.warning(msg)
             return None, msg
    else:
        msg = f"Nenhuma liga encontrada para \"{league_name}\""
        logging.warning(msg)
        return None, msg

def find_next_fixture_id(league_id, season, team_id_1, team_id_2):
    """Finds the fixture ID for the next match between two teams in a league/season."""
    logging.info(f"Buscando próximo fixture ID para {team_id_1} vs {team_id_2} na liga {league_id}, temporada {season}")
    params = {"league": league_id, "season": season, "team": team_id_1, "status": "NS", "next": "10"} 
    fixtures_t1 = _make_api_request("fixtures", params=params)
    
    if fixtures_t1 is None or isinstance(fixtures_t1, dict) and fixtures_t1.get("error"):
        msg = fixtures_t1.get("message") if isinstance(fixtures_t1, dict) else "Erro desconhecido"
        logging.error(f"Erro API ao buscar próximos fixtures para time {team_id_1}: {msg}")
        return None, msg
        
    for fixture in fixtures_t1:
        if isinstance(fixture, dict) and "teams" in fixture:
            home_id = fixture.get("teams", {}).get("home", {}).get("id")
            away_id = fixture.get("teams", {}).get("away", {}).get("id")
            if ((home_id == team_id_1 and away_id == team_id_2) or 
                (home_id == team_id_2 and away_id == team_id_1)):
                fixture_id = fixture.get("fixture", {}).get("id")
                fixture_date = fixture.get("fixture", {}).get("date")
                logging.info(f"Encontrado próximo fixture ID: {fixture_id} em {fixture_date}")
                return fixture_id, None
                
    msg = f"Nenhum próximo fixture encontrado entre {team_id_1} e {team_id_2} na liga {league_id}, temporada {season}"
    logging.warning(msg)
    return None, msg

def get_fixture_h2h(team_id_1, team_id_2, last_n=10):
    """Fetches head-to-head fixture data between two teams."""
    logging.info(f"Buscando H2H para times: {team_id_1} vs {team_id_2} (últimos {last_n})")
    params = {"h2h": f"{team_id_1}-{team_id_2}", "last": last_n}
    response = _make_api_request("fixtures/headtohead", params=params)
    if isinstance(response, dict) and response.get("error"):
        return None, response.get("message")
    return response, None

def get_team_statistics(team_id, league_id, season):
    """Fetches team statistics for a specific season and league."""
    logging.info(f"Buscando estatísticas para time: {team_id} na liga: {league_id}, temporada: {season}")
    params = {"team": team_id, "league": league_id, "season": season}
    stats_response = _make_api_request("teams/statistics", params=params)
    
    if stats_response is None or isinstance(stats_response, dict) and stats_response.get("error"):
        msg = stats_response.get("message") if isinstance(stats_response, dict) else "Erro desconhecido"
        logging.error(f"Erro API ao buscar estatísticas para time {team_id}: {msg}")
        return None, msg
        
    if isinstance(stats_response, list):
        msg = f"Nenhuma estatística encontrada para time {team_id} na liga {league_id}, temporada {season}."
        logging.warning(msg)
        return None, msg
        
    if not isinstance(stats_response, dict) or "league" not in stats_response or "team" not in stats_response:
        msg = "Formato inesperado na resposta de estatísticas da API."
        logging.error(msg)
        return None, msg
        
    if stats_response.get("league", {}).get("id") != league_id or stats_response.get("team", {}).get("id") != team_id:
        logging.warning(f"Estatísticas retornadas para time/liga diferente do solicitado.")
        msg = "Dados de estatísticas retornados não correspondem ao time/liga solicitados."
        return None, msg
        
    return stats_response, None

def get_fixture_odds(fixture_id, bookmaker_id=DEFAULT_BOOKMAKER_ID):
    """Fetches odds for a specific fixture from a specific bookmaker."""
    logging.info(f"Buscando odds para fixture: {fixture_id} do bookmaker: {bookmaker_id}")
    params = {"fixture": fixture_id, "bookmaker": bookmaker_id}
    odds_response = _make_api_request("odds", params=params)
    
    if odds_response is None or isinstance(odds_response, dict) and odds_response.get("error"):
        msg = odds_response.get("message") if isinstance(odds_response, dict) else "Erro desconhecido"
        logging.error(f"Erro API ao buscar odds para fixture {fixture_id}: {msg}")
        return None, msg
        
    if not odds_response:
        msg = f"Nenhuma odd encontrada para fixture {fixture_id} no bookmaker {bookmaker_id}."
        logging.warning(msg)
        return None, msg
        
    if isinstance(odds_response, list) and len(odds_response) > 0:
        return odds_response[0], None 
    else:
        msg = f"Formato inesperado ou resposta vazia ao buscar odds para fixture {fixture_id}."
        logging.warning(msg)
        return None, msg

# --- Main Orchestrator Function ---

def get_processed_fixture_data(home_team_name, away_team_name, league_name, season, country_name=None):
    """Orchestrates API calls to get all necessary data for analysis."""
    logging.info(f"Iniciando busca de dados para: {home_team_name} vs {away_team_name} em {league_name} ({season})")
    processed_data = {
        "error": False,
        "error_message": None,
        "home_team_id": None,
        "away_team_id": None,
        "league_id": None,
        "fixture_id": None,
        "season": season,
        "home_team_name": home_team_name,
        "away_team_name": away_team_name,
        "league_name": league_name,
        "lambda_casa": 1.5,
        "lambda_fora": 1.2,
        "avg_corners_home": 6.0,
        "avg_corners_away": 5.0,
        "raw_h2h": None,
        "raw_home_stats": None,
        "raw_away_stats": None,
        "raw_odds": None
    }

    league_id, error_msg = find_league_id(league_name, country_name, season)
    if error_msg:
        processed_data["error"] = True
        processed_data["error_message"] = f"Erro ao buscar Liga: {error_msg}"
        return processed_data
    processed_data["league_id"] = league_id

    home_id, error_msg = find_team_id(home_team_name)
    if error_msg:
        processed_data["error"] = True
        processed_data["error_message"] = f"Erro ao buscar Time Casa ({home_team_name}): {error_msg}"
        return processed_data
    processed_data["home_team_id"] = home_id
    
    away_id, error_msg = find_team_id(away_team_name)
    if error_msg:
        processed_data["error"] = True
        processed_data["error_message"] = f"Erro ao buscar Time Fora ({away_team_name}): {error_msg}"
        return processed_data
    processed_data["away_team_id"] = away_id

    fixture_id, error_msg = find_next_fixture_id(league_id, season, home_id, away_id)
    if error_msg and "Nenhum próximo fixture encontrado" not in error_msg:
        logging.warning(f"Não foi possível encontrar fixture ID: {error_msg}")
    elif fixture_id:
        processed_data["fixture_id"] = fixture_id
        odds_data, error_msg_odds = get_fixture_odds(fixture_id)
        if error_msg_odds:
            logging.warning(f"Não foi possível obter odds para fixture {fixture_id}: {error_msg_odds}")
        else:
            processed_data["raw_odds"] = odds_data

    home_stats, error_msg_h = get_team_statistics(home_id, league_id, season)
    if error_msg_h:
        processed_data["error"] = True
        processed_data["error_message"] = f"Erro ao buscar Estatísticas Casa ({home_team_name}): {error_msg_h}"
        return processed_data
    processed_data["raw_home_stats"] = home_stats

    away_stats, error_msg_a = get_team_statistics(away_id, league_id, season)
    if error_msg_a:
        processed_data["error"] = True
        processed_data["error_message"] = f"Erro ao buscar Estatísticas Fora ({away_team_name}): {error_msg_a}"
        return processed_data
    processed_data["raw_away_stats"] = away_stats

    h2h_data, error_msg_h2h = get_fixture_h2h(home_id, away_id)
    if error_msg_h2h:
        logging.warning(f"Não foi possível obter dados H2H: {error_msg_h2h}")
    else:
        processed_data["raw_h2h"] = h2h_data

    lambda_casa, lambda_fora = _calculate_strengths(home_stats, away_stats)
    processed_data["lambda_casa"] = lambda_casa
    processed_data["lambda_fora"] = lambda_fora

    avg_corners_home = _calculate_avg_corners(home_stats, "home")
    avg_corners_away = _calculate_avg_corners(away_stats, "away")
    processed_data["avg_corners_home"] = avg_corners_home
    processed_data["avg_corners_away"] = avg_corners_away

    logging.info(f"Busca de dados concluída para: {home_team_name} vs {away_team_name}")
    return processed_data

# --- Test Block ---
if __name__ == "__main__":
    logging.info("--- Executando Teste do API Handler ---")
    home = "Manchester City"
    away = "Liverpool"
    league = "Premier League"
    season_test = 2023
    country = "England"
    
    data = get_processed_fixture_data(home, away, league, season_test, country)
    
    print("\n--- Dados Processados ---")
    if data and not data.get("error"):
        print(f"League ID: {data.get('league_id')}")
        print(f"Home ID: {data.get('home_team_id')}")
        print(f"Away ID: {data.get('away_team_id')}")
        print(f"Fixture ID: {data.get('fixture_id')}")
        print(f"Lambda Casa: {data.get('lambda_casa')}")
        print(f"Lambda Fora: {data.get('lambda_fora')}")
        print(f"Avg Corners Home: {data.get('avg_corners_home')}")
        print(f"Avg Corners Away: {data.get('avg_corners_away')}")
        print(f"Odds disponíveis: {'Sim' if data.get('raw_odds') else 'Não'}")
    else:
        print("Falha ao obter dados processados.")
        print(f"Erro: {data.get('error_message')}")

