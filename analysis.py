# Core analysis functions for calculating betting probabilities

import pandas as pd
from scipy.stats import poisson
import math
from collections import defaultdict
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Function to get Poisson Matrix ---

def _get_poisson_matrix(lambda_casa, lambda_fora, max_goals=10):
    """Calculates the matrix of probabilities for each exact scoreline (i, j)."""
    matrix = defaultdict(float)
    total_prob_raw = 0
    # Ensure lambdas are valid numbers > 0
    if not (isinstance(lambda_casa, (int, float)) and lambda_casa > 0 and 
            isinstance(lambda_fora, (int, float)) and lambda_fora > 0):
        logging.error(f"Lambdas inválidos para _get_poisson_matrix: casa={lambda_casa}, fora={lambda_fora}")
        return defaultdict(float)
        
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            try:
                prob = poisson.pmf(i, lambda_casa) * poisson.pmf(j, lambda_fora)
                matrix[(i, j)] = prob
                total_prob_raw += prob
            except ValueError as e:
                logging.error(f"Erro no cálculo de Poisson PMF para ({i},{j}) com lambdas ({lambda_casa},{lambda_fora}): {e}")
                return defaultdict(float) # Return empty on error
            
    if total_prob_raw <= 0:
        logging.warning(f"Probabilidade total bruta na matriz Poisson é zero ou negativa ({total_prob_raw}). Retornando matriz vazia.")
        return defaultdict(float)
        
    # Normalize the matrix probabilities
    try:
        for score in matrix:
            matrix[score] = matrix[score] / total_prob_raw
    except ZeroDivisionError:
        logging.error("Erro de divisão por zero ao normalizar a matriz Poisson.")
        return defaultdict(float)
        
    return matrix

# --- Probability Calculation Functions ---

def _calculate_lambda(api_data):
    """Helper function to calculate or retrieve lambda values."""
    try:
        lambda_casa = api_data.get("lambda_casa", 1.5)
        lambda_fora = api_data.get("lambda_fora", 1.2)
        
        if not isinstance(lambda_casa, (int, float)) or not isinstance(lambda_fora, (int, float)) or lambda_casa <= 0 or lambda_fora <= 0 or math.isnan(lambda_casa) or math.isnan(lambda_fora):
             logging.warning(f"Valores lambda inválidos recebidos: casa={lambda_casa}, fora={lambda_fora}. Usando padrões 1.5, 1.2.")
             return 1.5, 1.2
        return lambda_casa, lambda_fora
    except Exception as e:
        logging.error(f"Erro ao calcular valores lambda: {e}. Usando padrões 1.5, 1.2.")
        return 1.5, 1.2

def calcular_1x2(poisson_matrix):
    """Calculates Win/Draw/Loss (1X2) probabilities from the Poisson matrix."""
    prob_vitoria_casa = 0
    prob_empate = 0
    prob_vitoria_fora = 0

    if not poisson_matrix:
        logging.error("Matriz Poisson vazia em calcular_1x2. Retornando padrão.")
        return {"casa": 33.3, "empate": 33.3, "fora": 33.3}
        
    for (i, j), prob in poisson_matrix.items():
        if i > j:
            prob_vitoria_casa += prob
        elif i == j:
            prob_empate += prob
        else:
            prob_vitoria_fora += prob
            
    return {
        "casa": round(prob_vitoria_casa * 100, 1),
        "empate": round(prob_empate * 100, 1),
        "fora": round(prob_vitoria_fora * 100, 1)
    }

def calcular_handicaps(poisson_matrix, handicap_lines=[-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5]):
    """Calculates Asian Handicap (AH) probabilities for various lines."""
    results = []
    if not poisson_matrix:
        logging.error("Matriz Poisson vazia em calcular_handicaps. Retornando lista vazia.")
        return []

    for line in handicap_lines:
        prob_casa_ah = 0
        prob_fora_ah = 0
        prob_push = 0

        for (i, j), prob in poisson_matrix.items():
            diff = i - j
            if diff + line > 0:
                prob_casa_ah += prob
            elif diff + line < 0:
                prob_fora_ah += prob
            elif diff + line == 0 and line == int(line):
                 prob_push += prob

        result_line = {
            "linha": f"{line:+.1f}",
            "casa": round(prob_casa_ah * 100, 1),
            "fora": round(prob_fora_ah * 100, 1)
        }
        if prob_push > 0:
             result_line["push"] = round(prob_push * 100, 1)
             
        results.append(result_line)
        
    return results

def calcular_over_under(poisson_matrix, limits=[0.5, 1.5, 2.5, 3.5, 4.5]):
    """Calculates Over/Under goals probabilities for various limits."""
    results = []
    if not poisson_matrix:
        logging.error("Matriz Poisson vazia em calcular_over_under. Retornando lista vazia.")
        return []
        
    for limit in limits:
        prob_over = 0
        prob_under = 0
        for (i, j), prob in poisson_matrix.items():
            total_goals = i + j
            if total_goals > limit:
                prob_over += prob
            elif total_goals < limit:
                prob_under += prob
            
        results.append({
            "limite": limit,
            "over": round(prob_over * 100, 1),
            "under": round(prob_under * 100, 1)
        })
    return results

def calcular_ambas_marcam(poisson_matrix):
    """Calculates Both Teams To Score (BTTS) probabilities (GG/NG)."""
    prob_gg = 0
    if not poisson_matrix:
        logging.error("Matriz Poisson vazia em calcular_ambas_marcam. Retornando padrão.")
        return {"sim": 50.0, "nao": 50.0}
        
    for (i, j), prob in poisson_matrix.items():
        if i > 0 and j > 0:
            prob_gg += prob
            
    prob_ng = 1.0 - prob_gg
    
    return {
        "sim": round(prob_gg * 100, 1),
        "nao": round(prob_ng * 100, 1)
    }

def calcular_ht_ft(api_data, ht_factor=0.45):
    """Calculates Half-Time/Full-Time probabilities using a refined (but still approximate) model."""
    logging.info(f"Calculando HT/FT usando fator HT={ht_factor}")
    lambda_casa_ft, lambda_fora_ft = _calculate_lambda(api_data)
    
    # Calculate HT lambdas
    lambda_casa_ht = lambda_casa_ft * ht_factor
    lambda_fora_ht = lambda_fora_ft * ht_factor
    
    # Calculate 2nd Half lambdas (ensure non-negative)
    lambda_casa_2h = max(0.01, lambda_casa_ft - lambda_casa_ht)
    lambda_fora_2h = max(0.01, lambda_fora_ft - lambda_fora_ht)
    
    # Get Poisson matrices for HT and 2H
    ht_matrix = _get_poisson_matrix(lambda_casa_ht, lambda_fora_ht, max_goals=5) 
    matrix_2h = _get_poisson_matrix(lambda_casa_2h, lambda_fora_2h, max_goals=7) # Allow more goals in 2H
    
    if not ht_matrix or not matrix_2h:
        logging.warning("Não foi possível calcular matrizes HT ou 2H para HT/FT. Retornando não implementado.")
        return {"status": "Não implementado", "motivo": "Erro no cálculo das matrizes HT/2H."}

    results = defaultdict(float)
    total_prob_calculated = 0
    
    # Iterate through HT scores and 2H scores
    for (i_ht, j_ht), prob_ht in ht_matrix.items():
        for (i_2h, j_2h), prob_2h in matrix_2h.items():
            # Final score
            i_ft = i_ht + i_2h
            j_ft = j_ht + j_2h
            
            # Determine HT result (1, X, 2)
            if i_ht > j_ht: ht_res = "1"
            elif i_ht == j_ht: ht_res = "X"
            else: ht_res = "2"
            
            # Determine FT result (1, X, 2)
            if i_ft > j_ft: ft_res = "1"
            elif i_ft == j_ft: ft_res = "X"
            else: ft_res = "2"
            
            ht_ft_key = f"{ht_res}/{ft_res}"
            
            # Probability of this path (assuming HT and 2H are independent given their lambdas)
            prob_path = prob_ht * prob_2h
            results[ht_ft_key] += prob_path
            total_prob_calculated += prob_path

    # Normalize results
    if total_prob_calculated > 0:
        final_results = {key: round((prob / total_prob_calculated) * 100, 1) for key, prob in results.items()}
        logging.info(f"Probabilidades HT/FT (Modelo Refinado): {final_results}")
        return final_results
    else:
        logging.warning("Probabilidade total HT/FT calculada foi zero. Retornando não implementado.")
        return {"status": "Não implementado", "motivo": "Probabilidade total zero no modelo HT/FT."}

def calcular_placar_exato(poisson_matrix, top_n=6):
    """Calculates Correct Score probabilities and returns the top N most likely."""
    if not poisson_matrix:
        logging.error("Matriz Poisson vazia em calcular_placar_exato. Retornando lista vazia.")
        return []
        
    sorted_scores = sorted(poisson_matrix.items(), key=lambda item: item[1], reverse=True)
    
    results = []
    for (i, j), prob in sorted_scores[:top_n]:
        results.append({
            "placar": f"{i}-{j}",
            "prob": round(prob * 100, 1)
        })
    return results

def calcular_total_cantos(api_data, corner_limits=[7.5, 8.5, 9.5, 10.5, 11.5, 12.5]):
    """Calculates Total Corners Over/Under probabilities using a Poisson model."""
    # Model refinement: Could potentially use Negative Binomial or adjust lambda based on H2H/recent form.
    # For now, keeping the Poisson model but ensuring data input is robust.
    results = []
    try:
        avg_corners_home = api_data.get("avg_corners_home", 6.0)
        avg_corners_away = api_data.get("avg_corners_away", 5.0)
        
        if not isinstance(avg_corners_home, (int, float)) or avg_corners_home < 0:
             logging.warning(f"avg_corners_home inválido ({avg_corners_home}). Usando padrão 6.0")
             avg_corners_home = 6.0
        if not isinstance(avg_corners_away, (int, float)) or avg_corners_away < 0:
             logging.warning(f"avg_corners_away inválido ({avg_corners_away}). Usando padrão 5.0")
             avg_corners_away = 5.0
             
        lambda_cantos = avg_corners_home + avg_corners_away
        lambda_cantos = max(0.1, lambda_cantos)
        
        logging.info(f"Calculando probabilidades de Cantos Totais usando lambda = {lambda_cantos:.2f}")

        # Determine reasonable max corners to calculate up to
        max_corners_calc = int(lambda_cantos + 4 * math.sqrt(lambda_cantos)) 
        max_corners_calc = max(max_corners_calc, int(max(corner_limits) + 5)) # Ensure we cover limits
        max_corners_calc = min(max_corners_calc, 30) # Add a practical upper limit
        
        prob_over = defaultdict(float)
        prob_under = defaultdict(float)
        total_prob = 0

        for k in range(max_corners_calc + 1):
            prob_k = poisson.pmf(k, lambda_cantos)
            total_prob += prob_k
            for limit in corner_limits:
                if k > limit:
                    prob_over[limit] += prob_k
                elif k < limit:
                    prob_under[limit] += prob_k
        
        # Normalize probabilities 
        if total_prob > 0:
             # Adjust probs based on calculated total (might be slightly < 1 due to max_corners_calc)
             norm_factor = 1.0 / total_prob 
             for limit in corner_limits:
                 prob_over[limit] *= norm_factor
                 prob_under[limit] *= norm_factor
                 # Ensure Over + Under doesn't exceed 100 due to rounding
                 if round(prob_over[limit] * 100, 1) + round(prob_under[limit] * 100, 1) > 100.0:
                     # Simple adjustment: slightly reduce the larger probability
                     if prob_over[limit] > prob_under[limit]:
                         prob_over[limit] = 1.0 - prob_under[limit]
                     else:
                         prob_under[limit] = 1.0 - prob_over[limit]
                         
        else:
             logging.warning("Probabilidade total para cantos foi zero. Não é possível calcular Over/Under.")
             return []

        for limit in corner_limits:
            results.append({
                "limite": limit,
                "over": round(prob_over[limit] * 100, 1),
                "under": round(prob_under[limit] * 100, 1)
            })
            
    except Exception as e:
        logging.error(f"Erro ao calcular cantos totais: {e}", exc_info=True)
        return []
        
    return results

# --- Value Bet Detection ---

def detectar_value_bet(prob_calculada, odd_mercado):
    """Detects if a bet has positive expected value (+EV)."""
    try:
        prob_decimal = float(prob_calculada) / 100.0
        odd = float(odd_mercado)
        
        if odd <= 1.0 or prob_decimal < 0 or prob_decimal > 1.0:
            return False, 0.0 # Invalid odds or probability
            
        valor_esperado = prob_decimal * odd
        return valor_esperado > 1.0, round(valor_esperado, 3)
    except (TypeError, ValueError) as e:
        logging.warning(f"Erro em detectar_value_bet (prob={prob_calculada}, odd={odd_mercado}): {e}")
        return False, 0.0

# --- Best Bet Selection ---

def _parse_odds(raw_odds_data):
    """Parses the raw odds data from the API into a structured dictionary."""
    parsed = {
        "1X2": {},
        "OverUnderGols": {},
        "BTTS": {},
        "AH": {},
        "OverUnderCantos": {}
    }
    if not raw_odds_data or not isinstance(raw_odds_data, dict):
        logging.warning("Dados brutos de odds ausentes ou inválidos para parse.")
        return parsed

    bets = raw_odds_data.get("bets", [])
    for bet in bets:
        if not isinstance(bet, dict):
            continue
        bet_id = bet.get("id")
        bet_name = bet.get("name", "").lower()
        values = bet.get("values", [])

        try:
            # Match Result (1X2)
            if bet_id == 1 or "match winner" in bet_name or "resultado final" in bet_name:
                for v in values:
                    if v.get("value") == "Home": parsed["1X2"]["casa"] = float(v["odd"])
                    elif v.get("value") == "Draw": parsed["1X2"]["empate"] = float(v["odd"])
                    elif v.get("value") == "Away": parsed["1X2"]["fora"] = float(v["odd"])
            
            # Over/Under Goals
            elif bet_id == 5 or "over/under" in bet_name and "corners" not in bet_name: # Avoid matching corners OU
                for v in values:
                    val_str = v.get("value", "")
                    if "Over " in val_str:
                        limit = float(val_str.replace("Over ", ""))
                        parsed["OverUnderGols"][f"Over{limit}"] = float(v["odd"])
                    elif "Under " in val_str:
                        limit = float(val_str.replace("Under ", ""))
                        parsed["OverUnderGols"][f"Under{limit}"] = float(v["odd"])
                        
            # Both Teams To Score
            elif bet_id == 8 or "both teams score" in bet_name or "ambas marcam" in bet_name:
                for v in values:
                    if v.get("value") == "Yes": parsed["BTTS"]["Sim"] = float(v["odd"])
                    elif v.get("value") == "No": parsed["BTTS"]["Nao"] = float(v["odd"])
                    
            # Asian Handicap
            elif bet_id == 4 or "asian handicap" in bet_name:
                 for v in values:
                     parts = v.get("value", "").split(" ")
                     if len(parts) == 2:
                         team = parts[0].lower()
                         line = float(parts[1])
                         key = f"{line:+.1f}_{team}" 
                         parsed["AH"][key] = float(v["odd"])
                         
            # Corners Over/Under
            elif "corners over/under" in bet_name or "total corners" in bet_name: 
                 for v in values:
                    val_str = v.get("value", "")
                    if "Over " in val_str:
                        limit = float(val_str.replace("Over ", ""))
                        parsed["OverUnderCantos"][f"Over{limit}"] = float(v["odd"])
                    elif "Under " in val_str:
                        limit = float(val_str.replace("Under ", ""))
                        parsed["OverUnderCantos"][f"Under{limit}"] = float(v["odd"])
                        
        except (ValueError, TypeError, AttributeError) as e:
            logging.warning(f"Erro ao parsear odd para {bet_name} - value: {v}: {e}")
            continue
            
    logging.info(f"Odds Parseadas: {parsed}")
    return parsed

def determinar_melhor_aposta(previsoes, odds_mercado):
    """Determines the best bet based on calculated probabilities and market odds."""
    if not odds_mercado or not isinstance(odds_mercado, dict):
        logging.warning("Odds de mercado não disponíveis ou inválidas para determinar melhor aposta.")
        return "N/A (Odds não disponíveis)"
        
    value_bets = []

    # 1. Check 1X2
    probs_1x2 = previsoes.get("1X2", {})
    odds_1x2 = odds_mercado.get("1X2", {})
    if probs_1x2 and odds_1x2:
        for outcome in ["casa", "empate", "fora"]:
            prob = probs_1x2.get(outcome)
            odd = odds_1x2.get(outcome)
            if prob is not None and odd is not None:
                is_value, ev = detectar_value_bet(prob, odd)
                if is_value:
                    value_bets.append({"mercado": "1X2", "selecao": outcome.capitalize(), "odd": odd, "prob": prob, "ev": ev})

    # 2. Check Over/Under Goals
    probs_ou_gols = previsoes.get("over_under_gols", [])
    odds_ou_gols = odds_mercado.get("OverUnderGols", {})
    if probs_ou_gols and odds_ou_gols:
        for prob_item in probs_ou_gols:
            limit = prob_item.get("limite")
            prob_over = prob_item.get("over")
            prob_under = prob_item.get("under")
            odd_over = odds_ou_gols.get(f"Over{limit}")
            odd_under = odds_ou_gols.get(f"Under{limit}")
            if limit is not None:
                if prob_over is not None and odd_over is not None:
                    is_value, ev = detectar_value_bet(prob_over, odd_over)
                    if is_value:
                        value_bets.append({"mercado": "Over/Under Gols", "selecao": f"Over {limit}", "odd": odd_over, "prob": prob_over, "ev": ev})
                if prob_under is not None and odd_under is not None:
                    is_value, ev = detectar_value_bet(prob_under, odd_under)
                    if is_value:
                        value_bets.append({"mercado": "Over/Under Gols", "selecao": f"Under {limit}", "odd": odd_under, "prob": prob_under, "ev": ev})

    # 3. Check BTTS
    probs_btts = previsoes.get("ambos_marcam", {})
    odds_btts = odds_mercado.get("BTTS", {})
    if probs_btts and odds_btts:
        for outcome in ["Sim", "Nao"]:
            prob = probs_btts.get(outcome.lower())
            odd = odds_btts.get(outcome)
            if prob is not None and odd is not None:
                is_value, ev = detectar_value_bet(prob, odd)
                if is_value:
                    value_bets.append({"mercado": "Ambas Marcam", "selecao": outcome, "odd": odd, "prob": prob, "ev": ev})
                    
    # 4. Check Asian Handicap
    probs_ah = previsoes.get("handicap_asiatico", [])
    odds_ah = odds_mercado.get("AH", {})
    if probs_ah and odds_ah:
        for prob_item in probs_ah:
            line_str = prob_item.get("linha") # e.g., "-1.5"
            prob_casa = prob_item.get("casa")
            prob_fora = prob_item.get("fora")
            odd_casa_key = f"{line_str}_home"
            odd_fora_key = f"{line_str}_away"
            odd_casa = odds_ah.get(odd_casa_key)
            odd_fora = odds_ah.get(odd_fora_key)
            
            if line_str is not None:
                if prob_casa is not None and odd_casa is not None:
                    is_value, ev = detectar_value_bet(prob_casa, odd_casa)
                    if is_value:
                        value_bets.append({"mercado": "Handicap Asiático", "selecao": f"Casa {line_str}", "odd": odd_casa, "prob": prob_casa, "ev": ev})
                if prob_fora is not None and odd_fora is not None:
                    is_value, ev = detectar_value_bet(prob_fora, odd_fora)
                    if is_value:
                        value_bets.append({"mercado": "Handicap Asiático", "selecao": f"Fora {line_str}", "odd": odd_fora, "prob": prob_fora, "ev": ev})
                        
    # 5. Check Over/Under Corners
    probs_ou_cantos = previsoes.get("over_under_cantos", [])
    odds_ou_cantos = odds_mercado.get("OverUnderCantos", {})
    if probs_ou_cantos and odds_ou_cantos:
        for prob_item in probs_ou_cantos:
            limit = prob_item.get("limite")
            prob_over = prob_item.get("over")
            prob_under = prob_item.get("under")
            odd_over = odds_ou_cantos.get(f"Over{limit}")
            odd_under = odds_ou_cantos.get(f"Under{limit}")
            if limit is not None:
                if prob_over is not None and odd_over is not None:
                    is_value, ev = detectar_value_bet(prob_over, odd_over)
                    if is_value:
                        value_bets.append({"mercado": "Over/Under Cantos", "selecao": f"Over {limit}", "odd": odd_over, "prob": prob_over, "ev": ev})
                if prob_under is not None and odd_under is not None:
                    is_value, ev = detectar_value_bet(prob_under, odd_under)
                    if is_value:
                        value_bets.append({"mercado": "Over/Under Cantos", "selecao": f"Under {limit}", "odd": odd_under, "prob": prob_under, "ev": ev})

    if not value_bets:
        logging.info("Nenhuma aposta de valor encontrada.")
        return "Nenhuma aposta de valor encontrada."

    # Sort by Expected Value (EV) descending
    value_bets.sort(key=lambda x: x["ev"], reverse=True)
    
    best_bet = value_bets[0]
    logging.info(f"Melhor Aposta Encontrada: {best_bet}")
    
    # Format the output string
    best_bet_str = f"{best_bet['mercado']} - {best_bet['selecao']} @ {best_bet['odd']:.2f} (Prob: {best_bet['prob']:.1f}%, EV: {best_bet['ev']:.3f})"
    return best_bet_str

# --- Main Analysis Orchestrator (Updated) ---

def analisar_jogo_completo(api_data):
    """Orchestrates the calculation of all betting scenarios and finds the best bet."""
    logging.info("Iniciando análise completa do jogo...")
    previsoes = {}
    melhor_aposta = "N/A"
    
    if not isinstance(api_data, dict):
        logging.error("Formato api_data inválido. Esperado um dicionário.")
        return {}, "Erro nos dados de entrada"
        
    if api_data.get("error"): 
        error_msg = api_data.get("error_message", "Erro desconhecido na busca de dados.")
        logging.error(f"Erro crítico na busca de dados: {error_msg}")
        return {}, f"Erro API: {error_msg}"
        
    lambda_casa, lambda_fora = _calculate_lambda(api_data)
    poisson_matrix = _get_poisson_matrix(lambda_casa, lambda_fora)
    
    if not poisson_matrix:
         logging.error("Falha ao gerar matriz Poisson. Não é possível realizar análise.")
         return {}, "Erro no cálculo da matriz de Poisson"

    previsoes["1X2"] = calcular_1x2(poisson_matrix)
    previsoes["handicap_asiatico"] = calcular_handicaps(poisson_matrix)
    previsoes["over_under_gols"] = calcular_over_under(poisson_matrix)
    previsoes["ambos_marcam"] = calcular_ambas_marcam(poisson_matrix)
    previsoes["ht_ft"] = calcular_ht_ft(api_data) # Uses refined model
    previsoes["placar_exato"] = calcular_placar_exato(poisson_matrix)
    previsoes["over_under_cantos"] = calcular_total_cantos(api_data)
    
    raw_odds_data = api_data.get("raw_odds")
    if raw_odds_data:
        parsed_odds = _parse_odds(raw_odds_data)
        melhor_aposta = determinar_melhor_aposta(previsoes, parsed_odds)
    else:
        logging.warning("Dados de odds brutos não encontrados em api_data. Não é possível determinar a melhor aposta.")
        melhor_aposta = "N/A (Odds não disponíveis)"
    
    logging.info("Análise completa.")
    return previsoes, melhor_aposta

# --- Test Block (Updated) ---
if __name__ == "__main__":
    simulated_api_data_with_odds = {
        "error": False,
        "error_message": None,
        "home_team_id": 33,
        "away_team_id": 40,
        "league_id": 39,
        "fixture_id": 123456, 
        "season": 2023,
        "home_team_name": "Manchester United",
        "away_team_name": "Liverpool",
        "league_name": "Premier League",
        "lambda_casa": 1.7, 
        "lambda_fora": 1.4,
        "avg_corners_home": 6.5,
        "avg_corners_away": 5.5,
        "raw_h2h": [], 
        "raw_home_stats": {}, 
        "raw_away_stats": {}, 
        "raw_odds": { 
            "bookmaker": {"id": 8, "name": "Bet365"},
            "bets": [
                {
                    "id": 1, "name": "Match Winner",
                    "values": [
                        {"value": "Home", "odd": "2.10"},
                        {"value": "Draw", "odd": "3.50"},
                        {"value": "Away", "odd": "3.20"}
                    ]
                },
                {
                    "id": 5, "name": "Over/Under",
                    "values": [
                        {"value": "Over 2.5", "odd": "1.80"},
                        {"value": "Under 2.5", "odd": "2.00"},
                        {"value": "Over 3.5", "odd": "2.90"},
                        {"value": "Under 3.5", "odd": "1.40"}
                    ]
                },
                {
                    "id": 8, "name": "Both Teams Score",
                    "values": [
                        {"value": "Yes", "odd": "1.66"},
                        {"value": "No", "odd": "2.10"}
                    ]
                },
                {
                    "id": 4, "name": "Asian Handicap",
                    "values": [
                        {"value": "Home -0.5", "odd": "2.15"},
                        {"value": "Away +0.5", "odd": "1.75"},
                        {"value": "Home -1.0", "odd": "2.90"},
                        {"value": "Away +1.0", "odd": "1.45"}
                    ]
                },
                {
                    "id": 13, "name": "Corners Over/Under", 
                    "values": [
                        {"value": "Over 9.5", "odd": "1.85"},
                        {"value": "Under 9.5", "odd": "1.95"},
                        {"value": "Over 10.5", "odd": "2.10"},
                        {"value": "Under 10.5", "odd": "1.70"}
                    ]
                }
            ]
        }
    }
    
    logging.info("--- Executando Teste de Análise com Odds Simuladas ---")
    previsoes, melhor_aposta = analisar_jogo_completo(simulated_api_data_with_odds)
    
    print("\n--- Resultados da Análise --- ")
    if previsoes:
        print("Previsões Calculadas:")
        # Format output nicely
        for scenario, result in previsoes.items():
            print(f"  {scenario}:")
            if isinstance(result, list) and result and isinstance(result[0], dict):
                for item in result:
                    details = ", ".join([f"{k}: {v}" for k, v in item.items()])
                    print(f"    - {details}")
            elif isinstance(result, dict):
                 details = ", ".join([f"{k}: {v}" for k, v in result.items()])
                 print(f"    * {details}")
            else:
                 print(f"    * {result}")
                 
        print(f"\nMelhor Aposta Sugerida: {melhor_aposta}")
        
    else:
        print(f"Análise falhou ou retornou vazia. Mensagem: {melhor_aposta}")

