import json
import pandas as pd
import spotipy
import os
from spotipy.oauth2 import SpotifyOAuth

# --- SETUP SPOTIFY AUTH ---
# Replace with your own credentials
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id='3bef302d159a4cb99ad5bb46894c7d8a',
    client_secret='0938a976e3704129a3239763db2caeaa',
    redirect_uri='https://127.0.0.1/callback',
    scope='user-library-read'
))

# --- CONFIGURATION ---
playlist_id = '6cTqq5QoNmj022KSn4JT0F'  # e.g. '37i9dQZF1DXcBWIGoYBM5M'
streaming_history_file = 'C:/Users/jfinkl/Downloads/Streaming_History_Audio_2014-2015_0.json'
streaming_history_folder = 'C:/Users/jfinkl/Downloads/my_spotify_data/Spotify Extended Streaming History/'
#"C:\Users\jfinkl\Downloads\my_spotify_data\Spotify Extended Streaming History\Streaming_History_Audio_2025_13.json"
skip_threshold_seconds = 30

# # --- LOAD STREAMING HISTORY ---
# with open(streaming_history_file, 'r', encoding='utf-8') as f:
#     data = json.load(f)
# history_df = pd.DataFrame(data)

all_data = []

for filename in os.listdir(streaming_history_folder):
    if filename.endswith('.json'):
        file_path = os.path.join(streaming_history_folder, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            file_data = json.load(f)
            all_data.extend(file_data)  # Append list entries

history_df = pd.DataFrame(all_data)


history_df.rename(columns={
    'master_metadata_track_name': 'trackName',
    'master_metadata_album_artist_name': 'artistName',
    'ms_played': 'msPlayed'
}, inplace=True)

# --- GET TRACKS FROM PLAYLIST VIA SPOTIFY API ---
def get_playlist_tracks(sp, playlist_id):
    tracks = []
    results = sp.playlist_items(playlist_id)
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
            results = None
    return pd.DataFrame(tracks)

# --- STEP 1: FETCH LIKED SONGS FROM SPOTIFY LIBRARY ---
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

#playlist_df = get_playlist_tracks(sp, playlist_id)
liked_df = get_liked_tracks(sp)

merged_df = pd.merge(history_df, liked_df, on=['trackName', 'artistName'], how='inner')
# --- MERGE STREAMING HISTORY WITH PLAYLIST TRACKS ---
#merged_df = pd.merge(history_df, playlist_df, on=['trackName', 'artistName'], how='inner')

# --- DEFINE SKIPS ---
#merged_df['skipped'] = merged_df['msPlayed'] < skip_threshold_seconds * 1000

# --- AGGREGATE STATS ---
group = merged_df.groupby(['trackName', 'artistName'])

summary = group.agg(skips=('skipped', 'sum'))
summary['totalPlays'] = group.size()
summary['skipRate'] = summary['skips'] / summary['totalPlays']

# --- SORT AND DISPLAY ---
summary_sorted = summary.sort_values(by='skipRate', ascending=False)
print(summary_sorted)
