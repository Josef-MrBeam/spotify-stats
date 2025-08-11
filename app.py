from flask import Flask, render_template, request
import os
import json
import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
    raise ValueError("Missing Spotify API credentials in environment variables.")


# --- Flask App ---
app = Flask(__name__)

# --- Spotify API Setup ---
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri='https://127.0.0.1/callback',
    scope='user-library-read'
))

# --- Load All Streaming History Files ---
def load_streaming_history(folder='streaming_history'):
    all_data = []
    for file in os.listdir(folder):
        if file.endswith('.json'):
            with open(os.path.join(folder, file), 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_data.extend(data)
    df = pd.DataFrame(all_data)
    df.rename(columns={
        'master_metadata_track_name': 'trackName',
        'master_metadata_album_artist_name': 'artistName',
        'ms_played': 'msPlayed'
    }, inplace=True)

    # Use 'ts' instead of 'endTime'
    df['ts'] = pd.to_datetime(df['ts'])
    df['year'] = df['ts'].dt.year

    return df

# --- Load Playlist Tracks from Spotify ---
def get_playlist_tracks(playlist_uri):
    tracks = []
    results = sp.playlist_items(playlist_uri)
    while results:
        for item in results['items']:
            track = item['track']
            if track:
                tracks.append({
                    'trackName': track['name'],
                    'artistName': track['artists'][0]['name']
                })
        if results['next']:
            results = sp.next(results)
        else:
            break
    return pd.DataFrame(tracks)

def get_liked_tracks(sp):
    results = sp.current_user_saved_tracks(limit=50)
    tracks = []
    while results:
        for item in results['items']:
            track = item['track']
            if track:
                tracks.append({
                    'trackName': track['name'],
                    'artistName': track['artists'][0]['name']
                })
        if results['next']:
            results = sp.next(results)
        else:
            break
    return pd.DataFrame(tracks)

# --- Compare and Calculate Skip Stats ---
def compare_and_summarize(history_df, playlist_df):
    merged = pd.merge(history_df, playlist_df, on=['trackName', 'artistName'], how='inner')
    merged['skipped'] = merged['msPlayed'] < 30 * 1000
    group = merged.groupby(['trackName', 'artistName'])
    summary = group.agg(skips=('skipped', 'sum'))
    summary['totalPlays'] = group.size()
    summary = summary.reset_index()
    summary['skipRate'] = (summary['skips'] / summary['totalPlays']).round(2)
    summary = summary.sort_values(by='skipRate', ascending=False)
    return summary



# --- Routes ---
@app.route('/', methods=['GET', 'POST'])
def index():
    summary_table = None
    playlist_uri = ''
    compare_mode = 'playlist'
    year = None

    if request.method == 'POST':
        compare_mode = request.form.get('compare_mode', 'playlist')
        playlist_uri = request.form.get('playlist_uri', '')
        year_input = request.form.get('year', '')
        year = int(year_input) if year_input else None

        try:
            history_df = HISTORY_DF.copy()

            if year:
                history_df = history_df[history_df['year'] == year]

            if compare_mode == 'liked':
                compare_df = LIKED_SONGS_DF.copy()
            else:
                if not playlist_uri:
                    raise ValueError("Playlist URI required.")
                compare_df = get_playlist_tracks(playlist_uri)

            summary = compare_and_summarize(history_df, compare_df)
            summary_table = summary.to_html(classes='table table-striped', index=False, table_id='skipTable')

        except Exception as e:
            summary_table = f"<p style='color:red;'>Error: {str(e)}</p>"

    return render_template('index.html',
                           summary_table=summary_table,
                           playlist_uri=playlist_uri,
                           compare_mode=compare_mode,
                           year=year)

# Load history data once at startup
print("Loading streaming history...")
HISTORY_DF = load_streaming_history()
print(f"Loaded {len(HISTORY_DF)} entries from streaming history.")

# Load history data once at startup
print("Loading liked songs...")
LIKED_SONGS_DF = get_liked_tracks(sp)
print(f"Loaded {len(LIKED_SONGS_DF)} entries from liked songs.")

# --- Run ---
if __name__ == '__main__':
    app.run(debug=True)
