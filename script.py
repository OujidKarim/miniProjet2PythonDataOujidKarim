from flask import Flask, jsonify, abort
import requests
import xml.etree.ElementTree as ET
import re
from requests.exceptions import RequestException
from typing import Dict, List, Optional

app = Flask(__name__)

# Fonction helper pour nettoyer le texte HTML
def clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext

# Fonction pour récupérer et parser le XML
def fetch_xml(url: str) -> Optional[ET.Element]:
    try:
        response = requests.get(url, timeout=10)  # Ajout d'un timeout
        response.raise_for_status()  # Lève une exception pour les codes d'erreur HTTP
        return ET.fromstring(response.content)
    except RequestException as e:
        app.logger.error(f"Erreur lors de la récupération du XML: {str(e)}")
        return None
    except ET.ParseError as e:
        app.logger.error(f"Erreur lors du parsing XML: {str(e)}")
        return None

# Route pour lister tous les jeux
@app.route('/games')
def get_games():
    url = 'https://api.geekdo.com/xmlapi/collection/megtrinity'
    
    try:
        root = fetch_xml(url)
        if root is None:
            return jsonify({'error': 'Impossible de récupérer les données'}), 503

        games = []
        for item in root.findall('.//item'):
            try:
                game = {
                    'id': item.get('objectid'),
                    'title': item.find('.//name').text if item.find('.//name') is not None else 'Titre inconnu',
                    'lst_published_year': item.find('.//yearpublished').text if item.find('.//yearpublished') is not None else None,
                    'players': 'Non spécifié',
                    'playtime': 'Non spécifié',
                    'thumbnail': item.find('.//thumbnail').text if item.find('.//thumbnail') is not None else None
                }

                # Récupération des stats avec gestion des erreurs
                stats = item.find('.//stats')
                if stats is not None:
                    min_players = stats.get('minplayers')
                    max_players = stats.get('maxplayers')
                    if min_players and max_players:
                        game['players'] = f"{min_players} - {max_players}"

                    min_time = stats.get('minplaytime')
                    max_time = stats.get('maxplaytime')
                    if min_time and max_time:
                        game['playtime'] = f"{min_time} - {max_time}"

                games.append(game)
            except Exception as e:
                app.logger.error(f"Erreur lors du traitement d'un jeu: {str(e)}")
                continue

        return jsonify(games)
    
    except Exception as e:
        app.logger.error(f"Erreur inattendue: {str(e)}")
        return jsonify({'error': 'Une erreur inattendue est survenue'}), 500

# Route pour obtenir les détails d'un jeu
@app.route('/games/<int:game_id>')
def get_game_details(game_id):
    url = f'https://api.geekdo.com/xmlapi/boardgame/{game_id}'
    
    try:
        root = fetch_xml(url)
        if root is None:
            return jsonify({'error': 'Impossible de récupérer les données du jeu'}), 503

        game = root.find('.//boardgame')
        if game is None:
            return jsonify({'error': 'Jeu non trouvé'}), 404

        # Récupération des catégories avec gestion des erreurs
        try:
            categories = [cat.text for cat in game.findall('.//boardgamecategory') if cat.text]
        except Exception:
            categories = []

        # Récupération des extensions avec gestion des erreurs
        try:
            expansions = [exp.text for exp in game.findall('.//boardgameexpansion') if exp.text]
        except Exception:
            expansions = []

        # Construction du dictionnaire de réponse avec gestion des valeurs manquantes
        game_details = {
            'id': game.get('objectid', str(game_id)),
            'title': game.find('.//name').text if game.find('.//name') is not None else 'Titre inconnu',
            'description': clean_html(game.find('.//description').text if game.find('.//description') is not None else ''),
            'image': game.find('.//image').text if game.find('.//image') is not None else None,
            'players': 'Non spécifié',
            'playtime': 'Non spécifié',
            'categories': ', '.join(categories),
            'expansions': expansions
        }

        # Gestion des joueurs et du temps de jeu
        min_players = game.find('.//minplayers')
        max_players = game.find('.//maxplayers')
        if min_players is not None and max_players is not None:
            game_details['players'] = f"{min_players.text} - {max_players.text}"

        min_time = game.find('.//minplaytime')
        max_time = game.find('.//maxplaytime')
        if min_time is not None and max_time is not None:
            game_details['playtime'] = f"{min_time.text} - {max_time.text}"

        return jsonify(game_details)
    
    except Exception as e:
        app.logger.error(f"Erreur lors de la récupération des détails du jeu {game_id}: {str(e)}")
        return jsonify({'error': 'Une erreur inattendue est survenue'}), 500

# Gestionnaire d'erreur pour les routes non trouvées
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Route non trouvée'}), 404

# Gestionnaire d'erreur pour les erreurs serveur
@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Erreur interne du serveur'}), 500

if __name__ == '__main__':
    app.run(debug=True)
