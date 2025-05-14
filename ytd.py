


import yt_dlp
from ytmusicapi import YTMusic
import json
import re
import requests
import os

"YOUTUBE URL SCRIPT"

import re
from urllib.parse import urlparse, parse_qs

def extract_youtube_ids_from_text(text):
    try:
        # Find all YouTube-style links in the text
        urls = re.findall(r'(https?://[^\s]+)', text)
        if not urls:
            raise ValueError("No URLs found in the input text.")

        video_id = None
        playlist_id = None

        for url in urls:
            parsed = urlparse(url)
            query = parse_qs(parsed.query)

            # Extract video ID
            if 'youtu.be' in parsed.netloc:
                video_id = parsed.path.lstrip('/')
            elif 'youtube.com' in parsed.netloc and 'v' in query:
                video_id = query.get('v', [None])[0]

            # Extract playlist ID
            if 'list' in query:
                playlist_id = query.get('list', [None])[0]

        if not video_id and not playlist_id:
            raise ValueError("No YouTube video or playlist ID found.")

        return video_id, playlist_id

    except Exception as e:
        raise ValueError(f"Failed to extract YouTube IDs: {e}")


def ytd_downloader(yt_url):
    video_id, playlist_id = extract_youtube_ids_from_text(yt_url)
    urls = []
    if video_id:
        urls.append(video_id)

    if playlist_id:
        ytmusic = YTMusic()  # No auth needed for public playlists

        playlist = ytmusic.get_playlist(playlist_id)

        for track in playlist['tracks']:
            title = track.get('title', 'Unknown')

            artists = ', '.join([artist['name']
                                for artist in track.get('artists', [])])

            album = track.get('album', {}).get('name', 'Unknown')

            # Get the largest thumbnail (usually last one)
            thumbnails = track.get('thumbnails', [])
            image_url = thumbnails[-1]['url'] if thumbnails else 'N/A'

            video_id = track.get('videoId')
            song_url = f'https://music.youtube.com/watch?v={video_id}' if video_id else 'N/A'

            urls.append((song_url))

            print(f"🎵 Song: {title}")
            print(f"🎤 Artists: {artists}")
            print(f"💿 Album: {album}")
            print(f"🖼️ Image URL: {image_url}")
            print(f"🔗 Song URL: {song_url}")
            print('-' * 60)


    music_dir = os.path.join(os.getcwd(), 'music')
    os.makedirs(music_dir, exist_ok=True)

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio',  # Prefer m4a, fallback to any
        'outtmpl': os.path.join(music_dir, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegMetadata',  # This adds metadata to audio files
        },
            {
                'key': 'EmbedThumbnail',  # Embeds thumbnail as cover image
        },
        ],
        'writethumbnail': True,  # Download the thumbnail
        'addmetadata': True,  # Skip ffmpeg or conversion
    }


    

    for url in urls:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

# python -m http.server 8000
