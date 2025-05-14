from flask import Flask, render_template, send_from_directory, send_file, request, redirect, url_for, session
import os

from io import BytesIO
import base64

from mutagen import File as MutagenFile
from mutagen.mp3 import HeaderNotFoundError
from mutagen import File as MutagenFile
from mutagen.mp4 import MP4, MP4Cover
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB
from pathlib import Path
from ytd import ytd_downloader

app = Flask(__name__)
MUSIC_FOLDER = os.path.join(os.path.dirname(__file__), 'music')


from dotenv import load_dotenv


load_dotenv()  # load variables from .env

# Now you can use them
secret_key = os.getenv("SECRET_KEY")
secret_username = os.getenv("SECRET_USERNAME")
secret_password = os.getenv("SECRET_PASSWORD")
print("moje creds",secret_username, secret_password, secret_key)

app.secret_key = secret_key  # Required for session to work!

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == secret_username and password == secret_password:
            # This creates a session
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return "Invalid credentials", 401

    return render_template('login.html')


@app.before_request
def require_login():
    allowed_routes = ['login', 'static']
    if request.endpoint not in allowed_routes and 'username' not in session:
        return redirect(url_for('login'))


def get_metadata(file_path):
    try:
        audio = MutagenFile(file_path, easy=False)
        if audio is None:
            raise ValueError("Unsupported or unreadable file")

        title = "Unknown Title"
        artist = "Unknown Artist"
        album = "Unknown Album"
        image_url = None

        # MP3 handling
        if isinstance(audio.tags, ID3):
            title = audio.tags.get("TIT2", TIT2(encoding=3, text="Unknown Title")).text[0]
            artist = audio.tags.get("TPE1", TPE1(encoding=3, text="Unknown Artist")).text[0]
            album = audio.tags.get("TALB", TALB(encoding=3, text="Unknown Album")).text[0]

            apic_tags = [tag for tag in audio.tags.values() if isinstance(tag, APIC)]
            if apic_tags:
                image_data = apic_tags[0].data
                mime = apic_tags[0].mime
                image_url = f"data:{mime};base64,{base64.b64encode(image_data).decode('utf-8')}"

        # M4A handling
        elif isinstance(audio, MP4):
            tags = audio.tags
            title = tags.get("\xa9nam", ["Unknown Title"])[0]
            artist = tags.get("\xa9ART", ["Unknown Artist"])[0]
            album = tags.get("\xa9alb", ["Unknown Album"])[0]

            covers = tags.get("covr")
            if covers:
                cover = covers[0]
                mime = "image/jpeg" if cover.imageformat == MP4Cover.FORMAT_JPEG else "image/png"
                image_url = f"data:{mime};base64,{base64.b64encode(cover).decode('utf-8')}"

        return {
            'filename': os.path.basename(file_path),
            'title': title,
            'artist': artist,
            'album': album,
            'image': image_url
        }

    except Exception as e:
        print(f"Metadata error: {file_path}: {e}")
        return {
            'filename': os.path.basename(file_path),
            'title': 'Unknown Title',
            'artist': 'Unknown Artist',
            'album': 'Unknown Album',
            'image': None
        }
@app.route('/')
def index():
    current_directory = os.getcwd()  # This gets the current working directory
    print(f"Current directory: {current_directory}")
    music_dir = os.path.join(current_directory, 'music')  # Assuming 'music' is a subfolder
    print("Files in music directory:", os.listdir(music_dir))
    files = [
        get_metadata(os.path.join(MUSIC_FOLDER, f))
        for f in os.listdir(MUSIC_FOLDER)
        if os.path.isfile(os.path.join(MUSIC_FOLDER, f))
    ]
    return render_template('index.html', files=files)


@app.route('/music/<path:filename>')
def download_file(filename):
    return send_from_directory(MUSIC_FOLDER, filename, as_attachment=True)


# Custom filename sanitization (replaces secure_filename)
def sanitize_filename(filename):
    return os.path.basename(filename)

@app.route('/download_from_YT', methods=['POST'])
def download_from_yt():
    yt_url = request.form.get('download_from_yt')
    ytd_downloader(yt_url)
    return redirect(url_for('index'))


@app.route('/update', methods=['POST'])
def update_metadata(remove_image=False):
    filename = request.form.get('filename')
    file_path = os.path.join(MUSIC_FOLDER, sanitize_filename(filename))

    # Check if file exists
    if not os.path.isfile(file_path):
        return "File not found", 404

    # Get the metadata from the form
    title = request.form.get('title') or 'Unknown Title'
    artist = request.form.get('artist') or 'Unknown Artist'
    album = request.form.get('album') or 'Unknown Album'
    remove_image = request.form.get('remove_image') == 'true'
    image_file = request.files.get('image')

    # Read the file with mutagen
    audio = MutagenFile(file_path, easy=False)

    if isinstance(audio.tags, ID3):  # If it's an MP3 file
        audio.tags["TIT2"] = TIT2(encoding=3, text=title)
        audio.tags["TPE1"] = TPE1(encoding=3, text=artist)
        audio.tags["TALB"] = TALB(encoding=3, text=album)

        # Handle image removal or adding new image
        if remove_image:
            audio.tags.delall("APIC")
        elif image_file:
            image_data = image_file.read()
            audio.tags.delall("APIC")  # Remove old images
            audio.tags.add(APIC(encoding=3, mime=image_file.mimetype, type=3, desc=u"Cover", data=image_data))

    elif isinstance(audio, MP4):  # If it's an M4A file
        audio.tags["\xa9nam"] = [title]
        audio.tags["\xa9ART"] = [artist]
        audio.tags["\xa9alb"] = [album]

        # Handle image removal or adding new image
        if remove_image:
            if "covr" in audio.tags:
                del audio.tags["covr"]
        elif image_file:
            image_data = image_file.read()
            cover_format = MP4Cover.FORMAT_JPEG if image_file.mimetype == "image/jpeg" else MP4Cover.FORMAT_PNG
            audio.tags["covr"] = [MP4Cover(image_data, imageformat=cover_format)]

    # Save changes to the file
    audio.save()
    
    # Redirect back to the main page
    return redirect(url_for('index'))

@app.route('/remove-all-imgs', methods=['POST'])
def remove_all_imgs():
    files = [
            remove_img(os.path.join(MUSIC_FOLDER, f))
            for f in os.listdir(MUSIC_FOLDER)
            if os.path.isfile(os.path.join(MUSIC_FOLDER, f))
        ]
    # Redirect back to the main page
    return redirect(url_for('index'))

def remove_img(file_path):
    try:
        # Check if file exists
        if not os.path.isfile(file_path):
            return "File not found", 404

        remove_image = True
        image_file = request.files.get('image')

        # Read the file with mutagen
        audio = MutagenFile(file_path, easy=False)

        if isinstance(audio.tags, ID3):  # If it's an MP3 file
            # Handle image removal or adding new image
                audio.tags.delall("APIC")


        elif isinstance(audio, MP4):  # If it's an M4A file
                if "covr" in audio.tags:
                    del audio.tags["covr"]


        # Save changes to the file
        audio.save()
    except Exception as e:
        print("Expeition",e)

@app.route('/delete_all_songs', methods=['POST'])
def delete_all_songs():
    for file in os.listdir(MUSIC_FOLDER):
        if file.endswith(('.mp3', '.m4a', '.flac')):
            song_path = Path(MUSIC_FOLDER) / file
            song_path.unlink()  # Delete the song file
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
