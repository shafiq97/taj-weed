from flask import Flask, flash, render_template, request, redirect, url_for, jsonify, session
import os
from werkzeug.utils import secure_filename
import urllib.parse
import speech_recognition as sr
from pydub import AudioSegment
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt

app = Flask(__name__)
app.secret_key = '12345'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')

# MySQL configuration
app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'flask_app'

mysql = MySQL(app)
bcrypt = Bcrypt(app)

def convert_audio_to_text(audio_path):
    recognizer = sr.Recognizer()
    audio = AudioSegment.from_file(audio_path)
    audio = audio.set_frame_rate(16000).set_channels(1)
    audio_path_wav = audio_path.replace('.opus', '.wav')
    audio.export(audio_path_wav, format='wav')

    with sr.AudioFile(audio_path_wav) as source:
        audio_data = recognizer.record(source)
        try:
            text = recognizer.recognize_google(audio_data, language='ar-SA')
            return text
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")
            return None

@app.route('/learn')
def learn():
    base_folder = os.path.join(app.static_folder, 'audio', 'dataset')
    folders = [f for f in os.listdir(base_folder) if f.startswith('Ikhfa Hakiki')]
    audio_files = []

    for folder in folders:
        folder_path = os.path.join(base_folder, folder)
        files = [os.path.join(folder, file) for file in os.listdir(folder_path) if file.endswith('.opus')]
        audio_files.extend(files)

    uploaded_files = {}
    for file in audio_files:
        file_name = secure_filename(file.split('/')[-1])
        encoded_name = urllib.parse.quote(file_name)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'recorded_{encoded_name}')
        if os.path.exists(file_path):
            uploaded_files[file] = f'recorded_{encoded_name}'
        else:
            uploaded_files[file] = None
    
    return render_template('index.html', audio_files=audio_files, uploaded_files=uploaded_files)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files or 'original_file' not in request.form:
        return redirect(request.url)
    
    file = request.files['file']
    original_file = request.form['original_file']
    
    if file.filename == '':
        return redirect(request.url)
    
    if file:
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        
        original_file_name = secure_filename(original_file)
        encoded_name = urllib.parse.quote(original_file_name)
        filename = f'recorded_{encoded_name}'
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Construct the dataset file path
        dataset_folder = original_file.rsplit('/', 1)[0]
        dataset_file_name = original_file.rsplit('/', 1)[1]
        dataset_file_path = os.path.join(app.static_folder, 'audio', 'dataset', dataset_folder, dataset_file_name)
        
        # Ensure the dataset file exists before processing
        if not os.path.exists(dataset_file_path):
            return jsonify({'error': f'Dataset file not found: {dataset_file_path}'}), 400
        
        # Compare the uploaded file with the dataset
        dataset_text = convert_audio_to_text(dataset_file_path)
        user_text = convert_audio_to_text(file_path)
        
        result = None
        if dataset_text and user_text:
            result = dataset_text == user_text
        
        return jsonify({'result': result, 'dataset_text': dataset_text, 'user_text': user_text})

@app.route('/read-quran')
def read_quran():
    return render_template('read_quran.html')

@app.route('/about-us')
def about_us():
    return render_template('about-us.html')

@app.route('/profile')
def profile():
    return render_template('profile.html')

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password_candidate = request.form['password']
        
        cur = mysql.connection.cursor()
        result = cur.execute("SELECT * FROM users WHERE username = %s", [username])
        
        if result > 0:
            data = cur.fetchone()
            print(data)
            password = data[2]
            
            if bcrypt.check_password_hash(password, password_candidate):
                session['logged_in'] = True
                session['username'] = username
                
                flash('Login successful!', 'success')
                return redirect(url_for('learn'))
            else:
                flash('Invalid credentials, please try again.', 'danger')
        else:
            flash('Username not found.', 'danger')
        cur.close()
        
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password == confirm_password:
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
            mysql.connection.commit()
            cur.close()
            
            flash('You are now registered and can log in', 'success')
            return redirect(url_for('login'))
        else:
            flash('Passwords do not match.', 'danger')
            
    return render_template('register.html')

@app.route('/home', methods=['GET'])
def home():
  return render_template('home.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return render_template('login.html')

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True, port=5001)