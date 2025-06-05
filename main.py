# Entry point for the Telegram Bot

import logging
import os
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import html # For escaping HTML characters if needed, though using parse_mode=HTML is simpler

# Import necessary functions from other modules
from api_handler import get_processed_fixture_data
from analysis import analisar_jogo_completo

# Setup basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7664698447:AAFx4uxHitMeegCrWuvIiP6Fzb7wrOWBfZM")
DEFAULT_SEASON = 2023 # Use a season likely available in free tier

# --- Helper Functions ---

def format_report(previsoes, melhor_aposta, home_team, away_team):
    """Formats the analysis results into a user-friendly string for Telegram using HTML."""
    # Escape team names to prevent accidental HTML injection
    home_team_html = html.escape(home_team)
    away_team_html = html.escape(away_team)
    
    report = f"📊 <b>Análise para {home_team_html} x {away_team_html}</b> 📊\n\n"
    report += "<b>Probabilidades Estimadas:</b>\n"

    # 1X2
    if "1X2" in previsoes:
        p = previsoes["1X2"]
        casa_prob = p.get("casa", "N/A")
        empate_prob = p.get("empate", "N/A")
        fora_prob = p.get("fora", "N/A")
        report += f"  - <b>Resultado Final (1X2):</b> Casa: {casa_prob}%, Empate: {empate_prob}%, Fora: {fora_prob}%\n"

    # BTTS
    if "ambos_marcam" in previsoes:
        p = previsoes["ambos_marcam"]
        sim_prob = p.get("sim", "N/A")
        nao_prob = p.get("nao", "N/A")
        report += f"  - <b>Ambas Marcam (BTTS):</b> Sim: {sim_prob}%, Não: {nao_prob}%\n"

    # Over/Under Gols
    if "over_under_gols" in previsoes and previsoes["over_under_gols"]:
        report += "  - <b>Over/Under Gols:</b>\n"
        for item in previsoes["over_under_gols"]:
            limite = item.get("limite", "?")
            over_prob = item.get("over", "N/A")
            under_prob = item.get("under", "N/A")
            report += f"    - Limite {limite}: Over {over_prob}%, Under {under_prob}%\n"

    # Placar Exato
    if "placar_exato" in previsoes and previsoes["placar_exato"]:
        report += "  - <b>Placares Mais Prováveis:</b>\n"
        for item in previsoes["placar_exato"]:
            placar = item.get("placar", "?")
            prob = item.get("prob", "N/A")
            report += f"    - {placar}: {prob}%\n"

    # Handicap Asiático
    if "handicap_asiatico" in previsoes and previsoes["handicap_asiatico"]:
        report += "  - <b>Handicap Asiático:</b>\n"
        for item in previsoes["handicap_asiatico"][:5]: # Limit lines
            linha = item.get("linha", "?")
            casa_prob = item.get("casa", "N/A")
            fora_prob = item.get("fora", "N/A")
            push_prob = item.get("push")
            push_txt = f", Push: {push_prob}%" if push_prob is not None else ""
            report += f"    - Linha {linha}: Casa {casa_prob}%, Fora {fora_prob}%{push_txt}\n"

    # Over/Under Cantos
    if "over_under_cantos" in previsoes and previsoes["over_under_cantos"]:
        report += "  - <b>Over/Under Cantos:</b>\n"
        for item in previsoes["over_under_cantos"]:
            limite = item.get("limite", "?")
            over_prob = item.get("over", "N/A")
            under_prob = item.get("under", "N/A")
            report += f"    - Limite {limite}: Over {over_prob}%, Under {under_prob}%\n"

    # HT/FT
    if "ht_ft" in previsoes and isinstance(previsoes["ht_ft"], dict) and "status" not in previsoes["ht_ft"]:
        report += "  - <b>Intervalo/Final (HT/FT - Modelo Simples):</b>\n"
        htft_sorted = sorted(previsoes["ht_ft"].items(), key=lambda item: item[1], reverse=True)
        for key, prob in htft_sorted[:5]: # Show top 5
            report += f"    - {key}: {prob}%\n"
    else:
        report += "  - <b>Intervalo/Final (HT/FT):</b> Não disponível ou erro no cálculo.\n"

    # Melhor Aposta - Escape potential HTML in the suggestion string
    melhor_aposta_html = html.escape(melhor_aposta)
    report += f"\n💡 <b>Melhor Aposta Sugerida (Baseado em Valor):</b>\n  - {melhor_aposta_html}\n"

    # Nota final
    report += "\n<i>Nota: Probabilidades são estimativas. Aposte com responsabilidade.</i>"
    return report

async def process_analysis_request(text):
    """Parses message, gets data, runs analysis, and formats report."""
    logger.info(f"Processando solicitação de análise: {text}")
    match = re.match(r"^\s*([^,]+?)\s+x\s+([^,]+?)\s*,\s*([^,]+?)\s*(?:,\s*Season=(\d{4}))?\s*(?:,\s*Country=([^,]+))?\s*$", text, re.IGNORECASE)
    
    if not match:
        logger.warning("Formato de mensagem inválido.")
        return "Formato inválido. Use: <code>Time Casa x Time Fora, Liga [, Season=AAAA] [, Country=NomePais]</code>"

    home_team, away_team, league_name, season_str, country_name = match.groups()
    home_team = home_team.strip()
    away_team = away_team.strip()
    league_name = league_name.strip()
    season = int(season_str) if season_str else DEFAULT_SEASON
    country_name = country_name.strip() if country_name else None

    logger.info(f"Dados extraídos: Casa=\"{home_team}\", Fora=\"{away_team}\", Liga=\"{league_name}\", Temporada={season}, País={country_name}")

    try:
        api_data = get_processed_fixture_data(
            home_team_name=home_team,
            away_team_name=away_team,
            league_name=league_name,
            season=season,
            country_name=country_name
        )
        
        if not api_data or not isinstance(api_data, dict):
            logger.error("Falha ao obter dados do api_handler ou formato inválido.")
            return "Desculpe, não consegui obter os dados necessários da API."
            
        if api_data.get("error"): 
            error_msg = api_data.get("error_message", "Erro desconhecido na busca de dados API.")
            logger.error(f"Erro da API impedindo análise: {error_msg}")
            # Escape error message for HTML safety
            return f"Desculpe, ocorreu um erro ao buscar dados da API: {html.escape(error_msg)}"

        previsoes, melhor_aposta = analisar_jogo_completo(api_data)
        
        if not previsoes and "Erro" in melhor_aposta:
             logger.error(f"Falha na análise do jogo: {melhor_aposta}")
             # Escape error message for HTML safety
             return f"Desculpe, ocorreu um erro durante a análise: {html.escape(melhor_aposta)}"

        report = format_report(previsoes, melhor_aposta, home_team, away_team)
        return report
        
    except Exception as e:
        logger.error(f"Erro inesperado ao processar a solicitação ", text, ": ", e, exc_info=True)
        return "Ocorreu um erro inesperado ao processar sua solicitação. Por favor, tente novamente mais tarde."

# --- Telegram Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    user = update.effective_user
    logger.info(f"Usuário {user.username} (ID: {user.id}) iniciou o bot.")
    await update.message.reply_html(
        f"Olá {user.mention_html()}! Sou o BetInsight Bot. ⚽️\n\n"
        "Envie os detalhes da partida que você quer analisar no formato:\n"
        "<code>Time Casa x Time Fora, Nome da Liga</code>\n\n"
        "Exemplo: <code>Manchester City x Liverpool, Premier League</code>\n\n"
        "Opcionalmente, adicione a temporada e o país:\n"
        "<code>Time Casa x Time Fora, Liga, Season=AAAA, Country=NomePais</code>\n\n"
        f"(Se a temporada não for informada, usarei {DEFAULT_SEASON}).",
        disable_web_page_preview=True,
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message when the /help command is issued."""
    logger.info(f"Usuário {update.effective_user.username} solicitou ajuda.")
    await update.message.reply_html(
        "Para analisar uma partida, envie uma mensagem no formato:\n"
        "<code>Time Casa x Time Fora, Nome da Liga</code>\n\n"
        "Exemplo: <code>Real Madrid x Barcelona, La Liga</code>\n\n"
        "Você também pode especificar a temporada e o país (útil para ligas com nomes iguais):\n"
        "<code>Time Casa x Time Fora, Liga, Season=AAAA, Country=NomePais</code>\n\n"
        f"Exemplo: <code>Flamengo x Palmeiras, Brasileirão Série A, Season=2023, Country=Brazil</code>\n\n"
        f"A temporada padrão é {DEFAULT_SEASON}."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles regular text messages to perform analysis."""
    message_text = update.message.text
    user = update.effective_user
    logger.info(f"Mensagem recebida de {user.username} (ID: {user.id}): {message_text}")
    
    # Indicate processing
    processing_message = await update.message.reply_text("Processando sua solicitação... ⏳", quote=True)
    
    # Process the request
    analysis_report = await process_analysis_request(message_text)
    
    # Edit the processing message with the final report
    try:
        await context.bot.edit_message_text(
            chat_id=processing_message.chat_id,
            message_id=processing_message.message_id,
            text=analysis_report,
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Falha ao editar mensagem com o relatório: {e}. Enviando como nova mensagem.")
        # Fallback to sending a new message if editing fails
        await update.message.reply_text(analysis_report, quote=True, parse_mode='HTML')

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("Desculpe, ocorreu um erro interno ao processar sua solicitação.")
        except Exception as e:
            logger.error(f"Falha ao enviar mensagem de erro para o usuário: {e}")

# --- Main Bot Function ---

def main() -> None:
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "7664698447:AAFx4uxHitMeegCrWuvIiP6Fzb7wrOWBfZM": # Check against the actual token now
        logger.warning("TOKEN DO BOT DO TELEGRAM NÃO PARECE ESTAR CONFIGURADO CORRETAMENTE ou é o token de exemplo. Verifique a variável de ambiente TELEGRAM_BOT_TOKEN ou o valor hardcoded.")
        # Allow running for testing purposes even if token seems wrong, but log warning.
        # return # Uncomment this line to prevent running with the example token

    logger.info("Iniciando BetInsight Bot...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    logger.info("Bot iniciado e escutando por mensagens...")
    application.run_polling()

if __name__ == "__main__":
    main()

import os
TOKEN = os.getenv('DISCORD_TOKEN')

