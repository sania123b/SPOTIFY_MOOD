from flask import Flask, render_template, request, jsonify
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import random
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Spotify API credentials from environment variables
CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID', '881efee13ee2450e8ef5e7499c3879d7')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET', '8938ea9ea5d943feb332874602525dec')
REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI', 'http://127.0.0.1:5000/callback')
SCOPE = 'user-library-read user-modify-playback-state'

# Initialize Spotipy client
sp = None

# Mood to search terms mapping
MOOD_SEARCH_TERMS = {
    "happy": ["happy songs", "upbeat", "cheerful", "feel good", "celebration"],
    "sad": ["sad songs", "melancholy", "heartbreak", "emotional", "breakup"],
    "romantic": ["love songs", "romantic", "romance", "love story", "couple"],
    "energetic": ["energetic", "dance", "party", "upbeat", "high energy"],
    "relaxing": ["relaxing", "peaceful", "soothing", "chill", "calm"],
    "devotional": ["devotional", "spiritual", "bhakti", "prayer", "religious"],
    "party": ["party songs", "dance party", "celebration", "festival", "club"]
}

# Language mapping with specific filters
LANGUAGES = {
    "telugu": {
        "market": "IN",
        "search_terms": ["telugu songs", "telugu music", "tollywood"],
        "top_artists": [
            "S. P. Balasubrahmanyam", "Sid Sriram", "S. Thaman", "Anirudh Ravichander",
            "DSP", "Karthik", "Shreya Ghoshal", "Chitra", "Sai Pallavi", "Chinmayi"
        ],
        "keywords": ["telugu", "tollywood", "andhra", "hyderabad"],
        "exclude": ["hindi", "tamil", "kannada", "malayalam"]
    },
    "hindi": {
        "market": "IN",
        "search_terms": ["hindi songs", "bollywood songs", "hindi music"],
        "top_artists": [
            "Arijit Singh", "Shreya Ghoshal", "Sonu Nigam", "Neha Kakkar",
            "Badshah", "Jubin Nautiyal", "Kumar Sanu", "Alka Yagnik"
        ],
        "keywords": ["hindi", "bollywood", "mumbai"],
        "exclude": ["telugu", "tamil", "punjabi"]
    },
    "tamil": {
        "market": "IN",
        "search_terms": ["tamil songs", "kollywood songs", "tamil music"],
        "top_artists": [
            "Anirudh Ravichander", "A.R. Rahman", "Yuvan Shankar Raja",
            "G. V. Prakash Kumar", "Ilaiyaraaja", "Sid Sriram", "Shreya Ghoshal"
        ],
        "keywords": ["tamil", "kollywood", "chennai"],
        "exclude": ["telugu", "hindi", "kannada"]
    },
    "punjabi": {
        "market": "IN",
        "search_terms": ["punjabi songs", "punjabi music", "bhangra"],
        "top_artists": [
            "Diljit Dosanjh", "AP Dhillon", "Sidhu Moose Wala", "Guru Randhawa",
            "Honey Singh", "Jasmine Sandlas", "Parmish Verma"
        ],
        "keywords": ["punjabi", "punjab", "bhangra"],
        "exclude": ["hindi", "telugu", "tamil"]
    }
}

def initialize_spotipy():
    """Initialize the Spotipy client with authentication"""
    global sp
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE
    ))

def verify_language(track, language):
    """Verify if a track is likely in the specified language"""
    lang_info = LANGUAGES[language.lower()]
    
    track_name = track['name'].lower()
    artist_names = [artist['name'].lower() for artist in track['artists']]
    
    # Check if any artist is in the top artists for this language
    for artist in lang_info["top_artists"]:
        if artist.lower() in " ".join(artist_names):
            return True
    
    # Check for language keywords in track name
    for keyword in lang_info["keywords"]:
        if keyword in track_name:
            return True
    
    # Check for excluded language keywords
    for exclude_word in lang_info["exclude"]:
        if exclude_word in track_name:
            return False
    
    return True

@app.route('/')
def index():
    """Render the main page with mood and language options"""
    return render_template('index.html', 
                         moods=list(MOOD_SEARCH_TERMS.keys()),
                         languages=list(LANGUAGES.keys()))

@app.route('/find_song', methods=['POST'])
def find_song():
    """Handle song search request from the web interface"""
    try:
        data = request.json
        mood = data.get('mood')
        language = data.get('language')
        
        if not mood or mood not in MOOD_SEARCH_TERMS:
            return jsonify({"error": "Invalid mood"}), 400
        
        if not language or language not in LANGUAGES:
            return jsonify({"error": "Invalid language"}), 400
        
        # Initialize Spotipy if not already done
        if sp is None:
            initialize_spotipy()
        
        # Find matching song
        lang_info = LANGUAGES[language.lower()]
        mood_terms = MOOD_SEARCH_TERMS[mood]
        verified_tracks = []
        attempts = 0
        max_attempts = 3
        
        while len(verified_tracks) == 0 and attempts < max_attempts:
            attempts += 1
            
            # Strategy 1: Search by language term + mood term
            lang_term = random.choice(lang_info["search_terms"])
            mood_term = random.choice(mood_terms)
            query = f"{lang_term} {mood_term}"
            
            results = sp.search(q=query, type='track', market=lang_info["market"], limit=20)
            
            # Verify each track
            candidate_tracks = results['tracks']['items']
            if candidate_tracks:
                for track in candidate_tracks:
                    if verify_language(track, language):
                        verified_tracks.append(track)
            
            # If we still don't have any tracks, try strategy 2
            if len(verified_tracks) == 0 and attempts < max_attempts:
                # Strategy 2: Use a specific artist from this language
                artist = random.choice(lang_info["top_artists"])
                query = f"artist:\"{artist}\" {mood_term}"
                
                results = sp.search(q=query, type='track', market=lang_info["market"], limit=10)
                
                candidate_tracks = results['tracks']['items']
                if candidate_tracks:
                    for track in candidate_tracks:
                        if verify_language(track, language):
                            verified_tracks.append(track)
        
        if len(verified_tracks) == 0:
            return jsonify({"error": f"No {language} songs found for {mood} mood"}), 404
        
        # Pick a random track from verified tracks
        track = random.choice(verified_tracks)
        
        # Prepare response data
        track_info = {
            "name": track['name'],
            "artists": ", ".join([artist["name"] for artist in track["artists"]]),
            "album": track.get("album", {}).get("name", "Unknown Album"),
            "uri": track['uri'],
            "external_url": track['external_urls']['spotify'],
            "image": track['album']['images'][0]['url'] if track['album']['images'] else None
        }
        
        return jsonify(track_info)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/play_song', methods=['POST'])
def play_song():
    """Handle song playback request"""
    try:
        data = request.json
        track_uri = data.get('uri')
        
        if sp is None:
            initialize_spotipy()
        
        # Try to play the track
        devices = sp.devices()
        if devices['devices']:
            sp.start_playback(uris=[track_uri])
            return jsonify({"status": "Playing on your Spotify device!"})
        else:
            return jsonify({
                "status": "No active Spotify devices found",
                "external_url": data.get('external_url')
            })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)