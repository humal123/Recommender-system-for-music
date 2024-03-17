from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, make_response
import json
import jwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import matplotlib.pyplot as plt
import numpy as np
import time
import io
import sqlite3
from CBFiltering import *
from CFiltering import *

#[{n,l,s[{n,a,y},{n,a,y}]}]
genres = []
songs = {}
plt.switch_backend('agg')
for i,r in cbf.df.iterrows():
    genre = r['genre'].capitalize()
    link = r['genre']
    sid = r['songid']
    name = r['name']
    artist = r['artist']
    year = r['year']
    songs[str(sid)] = {"songid":sid,"name":name,"artist":artist,"year":year,"genre":genre}
    append = True
    for j in genres:
        if j["name"] == genre:
            j["songs"].append({"songid":sid,"name":name,"artist":artist,"year":year})
            append = False
            break
    if append:
        genres.append({"name":genre,"link":link,"songs":[{"songid":sid,"name":name,"artist":artist,"year":year}]})

conn = sqlite3.connect('database.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users
            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
            username TEXT NOT NULL UNIQUE, 
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            ratings TEXT,
            playlists TEXT)''')
c.execute('''CREATE TRIGGER IF NOT EXISTS set_initial_id
            AFTER INSERT ON users
            BEGIN
                UPDATE users SET id = (SELECT MAX(id) FROM users) - 1 WHERE id = (SELECT MAX(id) FROM users);
            END;''')
try:
    c.execute("INSERT INTO users (username, email, password, ratings, playlists) VALUES (?, ?, ?, ?, ?)", ("admin", "admin@musicrs" ,"scrypt:32768:8:1$HN8OL1ZaEVTH6JBN$1f9c8f3e9ce80e143b9cb38f038d7b7472988a8d41d5ec1e023b6c6d172be32c381fa3aea234116002f37764563cc096909eaba342b4e0101c35cb3121f2e175",json.dumps([]),json.dumps([])))
except:
    pass
conn.commit()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'MusicRS'

def generate_token(eu,em):
    payload = {
        'username': eu,
        'email':em,
        'exp': datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=240)
    }
    token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
    return token

def decode_token(token):
    try:
        decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return decoded
    except jwt.ExpiredSignatureError:
        return 'Signature expired. Please log in again.'
    except jwt.InvalidTokenError:
        return 'Invalid token. Please log in again.'

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('session')
        if not token:
            return redirect(url_for('login'))
        try:
            data = decode_token(token)
            username = data.get('username')
            email = data.get('email')
            if (not username) or (not email):
                return jsonify({'message': 'Invalid jwt!'}), 401
            user = get_user(username)
            if not user:
                return jsonify({'message': 'User not found!'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token'}), 401
        return f(user=user,*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('session')
        if not token:
            return redirect(url_for('login'))
        try:
            data = decode_token(token)
            username = data.get('username')
            if not username:
                return jsonify({'message': 'Invalid jwt!'}), 401
            user = get_admin(username)
            if not user:
                return jsonify({'message': 'No admin found!'}), 401
            if user[1] != "admin":
                return jsonify({'message': 'No admin found!'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token'}), 401
        return f(user=user,*args, **kwargs)
    return decorated

@app.route('/register', methods=['POST','GET'])
def register():
    if request.method == 'GET':
        return render_template('register.html',bodyclasses='bg-register')
    elif request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password1']
        password2 = request.form['password2']
        if password != password2:
            flash('Confirm password does not match!','warning')
            return redirect(url_for('register'))
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? OR email=?", (username,email))
        existing_user = c.fetchone()
        if existing_user:
            flash('Username Or Email already exists','warning')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        c.execute("INSERT INTO users (username, email, password, ratings, playlists) VALUES (?, ?, ?, ?, ?)", (username, email, hashed_password, json.dumps([]), json.dumps([])))
        conn.commit()
        flash('User registered successfully!','success')
        return redirect(url_for('login'))
    else:
        return jsonify({'error':'method not allowed'})

@app.route('/login', methods=['POST','GET'])
def login():
    if request.method == 'GET':
        return render_template('login.html',bodyclasses='bg-login')
    elif request.method == 'POST':
        eu = request.form['eu']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? OR email=?", (eu,eu))
        user = c.fetchone()
        conn.commit()
        if user and check_password_hash(user[3], password):
            if user[1] == "admin":
                token = generate_token(user[1],user[2])
                resp = make_response(redirect(url_for('admin')))
                resp.set_cookie('session', token)
                return resp
            else:
                token = generate_token(user[1],user[2])
                resp = make_response(redirect(url_for('home')))
                resp.set_cookie('session', token)
                return resp
        else:
            flash('Invalid username or password','warning')
            return redirect(url_for('login'))

@app.route('/logout')
def logout():
    flash('Logged out','info')
    resp = make_response(redirect(url_for('login')))
    resp.set_cookie('session', '', expires=0)
    return resp

@app.route('/', methods=['GET'])
def default():
    return redirect(url_for('home'))

@app.route('/home', methods=['POST','GET'])
@token_required
def home(user):
    if request.method == 'GET':
        return render_template('home.html',user={'id':user[0],'username':user[1],'email':user[2]},genres=genres,recommended=cf.get_recommendations(user[0]),playlists=get_playlists(user[0]))
        #[{'name':'Classical','link':'classical','songs':[{'name':'HEHE','artist':'Hehe'},{'name':'HEHE','artist':'Hehe'},{'name':'HEHE','artist':'Hehe'},{'name':'HEHE','artist':'Hehe'},{'name':'HEHE','artist':'Hehe'}]},{'name':'Pop','link':'pop','songs':[{'name':'HEHE','artist':'Hehe'},{'name':'HEHE','artist':'Hehe'},{'name':'HEHE','artist':'Hehe'},{'name':'HEHE','artist':'Hehe'},{'name':'HEHE','artist':'Hehe'}]}])
    else:
        pass

@app.route('/view-song', methods=['GET'])
@token_required
def view_song(user):
    if request.method == 'GET':
        song_id = request.args.get('songid')
        song_name = request.args.get('name')
        song_artist = request.args.get('artist')
        song_year = request.args.get('year')
        song_genre = request.args.get('genre').lower()
        song_rating = request.args.get('rate')
        rInt = request.args.get('rint')
        if song_rating is not None:
            rate_song(user[0],song_id,song_rating)
        recommended = cbf.get_recommendations(song_name)
        return render_template('song.html',song={"songid":song_id,"name":song_name,"artist":song_artist,"year":song_year,"genre":song_genre,"rating":get_rating(user[0],song_id)},recommended=recommended,playlists=get_playlists(user[0]),rInt=rInt)
    else:
        pass

@app.route('/create-playlist', methods=['POST'])
@token_required
def create__playlist(user):
    if request.method == 'POST':
        data = request.json
        name = data.get('name')
        if check_playlist(user[0],name):
            return jsonify({'message': 'exists'})
        else:
            create_playlist(user[0],name)
            return jsonify({'message':'ok'})
    else:
        pass

@app.route('/add-to-playlist', methods=['POST'])
@token_required
def addto_playlist(user):
    if request.method == 'POST':
        data = request.json
        name = data.get('name')
        songid = data.get('songid')
        if check_playlist(user[0],name):
            if add_to_playlist(user[0],name,songid):
                return jsonify({'message':'ok'})
            else:
                return jsonify({'message':'error'})
        else:
            return jsonify({'message':'not_found'})
    else:
        pass

@app.route('/remove-from-playlist', methods=['POST'])
@token_required
def removefrom_playlist(user):
    if request.method == 'POST':
        data = request.json
        name = data.get('name')
        songid = data.get('songid')
        if check_playlist(user[0],name):
            if remove_from_playlist(user[0],name,songid):
                return jsonify({'message':'ok'})
            else:
                return jsonify({'message':'error'})
        else:
            return jsonify({'message':'not_found'})
    else:
        pass

@app.route('/remove-playlist', methods=['POST'])
@token_required
def remove_Playlist(user):
    if request.method == 'POST':
        data = request.json
        name = data.get('name')
        if check_playlist(user[0],name):
            if remove_playlist(user[0],name):
                return jsonify({'message':'ok'})
            else:
                return jsonify({'message':'error'})
        else:
            return jsonify({'message':'not_found'})
    else:
        pass

@app.route('/view-playlist', methods=['GET'])
@token_required
def view_playlist(user):
    if request.method == 'GET':
        name = request.args.get('name')
        if check_playlist(user[0],name):
            return render_template('playlist.html',user={'id':user[0],'username':user[1],'email':user[2]},playlists=get_playlists(user[0]),playlist=get_playlist(user[0],name),name=name)
        else:
            flash('Playlist not found','warning')
            return render_template('playlist.html',user={'id':user[0],'username':user[1],'email':user[2]},playlists=get_playlists(user[0]),playlist=[],name="Playlist not found!")
    else:
        pass

@app.route('/profile', methods=['GET','POST'])
@token_required
def profile(user):
    if request.method == 'GET':
        return render_template('profile.html',username=user[1],email=user[2],playlists=get_playlists(user[0]))
    else:
        username = request.form['username']
        email = request.form['email']
        oldpassword = request.form['oldpassword']
        newpassword = request.form['newpassword']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        usernameCheck = c.fetchone()
        c.execute("SELECT * FROM users WHERE email=?", (email,))
        emailCheck = c.fetchone()
        c.execute("SELECT * FROM users WHERE username=? OR email=?", (user[1],user[2]))
        currentuser = c.fetchone()
        conn.commit()
        if usernameCheck and username != user[1]:
            flash("Username has already taken!","warning")
            return render_template('profile.html',username=user[1],email=user[2])
        if emailCheck and email != user[2]:
            flash("Email is already in use!","warning")
            return render_template('profile.html',username=user[1],email=user[2])
        if currentuser and check_password_hash(currentuser[3], oldpassword):
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("UPDATE users SET username = ?,email = ?,password = ? WHERE id=?",(username,email,generate_password_hash(newpassword),str(user[0])))
            conn.commit()
            flash("Updated!","info")
            return redirect(url_for('logout'))
        else:
            flash('Wrong Password!','warning')
            return render_template('profile.html',username=user[1],email=user[2])

@app.route('/admin', methods=['GET','POST'])
@admin_required
def admin(user):
    if request.method == 'GET':
        return render_template('admin.html',users=get_users())
    else:
        data = request.json
        action = data.get('action')
        if action == "delete":
            id = data.get('id')
            delete_user(id)
            return jsonify({'message':'ok'})
        if action == "edit":
            id = data.get('id')
            username = data.get('username')
            email = data.get('email')
            password = data.get('password')
            return jsonify({'message':edit_user(id,username,email,password)})

@app.route('/totalsongsgenrewise')
def totalsongsgenrewise():
    plt.figure(figsize=(8, 5))
    cmap = plt.colormaps.get_cmap('tab20')
    plt.barh([i["name"] for i in genres], [len(i["songs"]) for i in genres],color=cmap(np.arange(len(genres))))
    plt.xlabel("No. of Songs")
    plt.ylabel("Genres")
    plt.title("Genre/Songs")
    for i, v in enumerate([len(i["songs"]) for i in genres]):
        plt.text(v, i, str(v), ha='left', va='center')
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plt.clf()
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'image/png'
    return response

@app.route('/topsongs')
def topsongs():
    plt.figure(figsize=(10, 5))
    cmap = plt.colormaps.get_cmap('tab20')
    df = pd.read_csv("ratings.csv")
    song_ratings = df.groupby('songid')['ratings'].mean()
    top_songs = song_ratings.sort_values(ascending=False)
    top_song_ids = top_songs.head(5).index.tolist()
    top_songs_info = cbf.df[cbf.df['songid'].isin(top_song_ids)]
    top_songs_info = pd.merge(top_songs_info, top_songs, left_on='songid', right_index=True)
    plt.bar(top_songs_info['name'], top_songs_info['ratings'], color=cmap(np.arange(len(top_song_ids))))
    plt.xlabel('Song Name')
    plt.ylabel('Average Rating')
    plt.title('Top Five Songs by Ratings')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plt.clf()
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'image/png'
    return response

@app.route('/topartists')
def topartists():
    cmap = plt.colormaps.get_cmap('tab10')
    ratings_df = pd.read_csv('ratings.csv')
    merged_df = pd.merge(ratings_df, cbf.df, on='songid')
    artist_avg_ratings = merged_df.groupby('artist')['ratings'].mean().reset_index()
    artist_avg_ratings = artist_avg_ratings.sort_values(by='ratings', ascending=False).head(10)
    plt.figure(figsize=(10, 5))
    plt.barh([' '.join(x.split(' ')[:2]) for x in artist_avg_ratings['artist']], artist_avg_ratings['ratings'], color=cmap(np.arange(len(artist_avg_ratings))))
    plt.xlabel('Average Rating')
    plt.ylabel('Artist')
    plt.yticks(fontsize=7)
    plt.title('Top 10 Artists by Average Rating')
    plt.gca().invert_yaxis()
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plt.clf()
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'image/png'
    return response

@app.route('/ratingsdistribution')
def ratingsdistribution():
    ratings_df = pd.read_csv('ratings.csv')
    plt.figure(figsize=(8, 6))
    plt.hist(ratings_df['ratings'], bins=5, color='skyblue', edgecolor='black')
    plt.xlabel('Rating')
    plt.ylabel('Frequency')
    plt.title('Distribution of Ratings')
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plt.clf()
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'image/png'
    return response

def get_admin(username):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    admin = c.fetchone()
    conn.commit()
    return admin

def delete_user(id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id = ?",(id,))
    conn.commit()

def edit_user(id,username,email,password):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if username != "":
        try:
            c.execute("UPDATE users SET username = ? WHERE id = ?",(username,id,))
        except:
            conn.commit()
            return "Cannot edit because username is already taken!"
    if email != "":
        try:
            c.execute("UPDATE users SET email = ? WHERE id = ?",(email,id,))
        except:
            conn.commit()
            return "Cannot edit because email is already taken!"
    if password != "":
        c.execute("UPDATE users SET password = ? WHERE id = ?",(generate_password_hash(password),id,))
    conn.commit()
    return "ok"

def get_users():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users")
    users = c.fetchall()
    users = [i for i in users if 'admin' not in i]
    conn.commit()
    return users

def get_user(username):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.commit()
    return user

def rate_song(userid,songid,rating):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (str(userid)))
    user = c.fetchone()
    
    if user:
        ratings = json.loads(user[4])
        co = True
        for i in ratings:
            if str(songid) in i.keys():
                i[str(songid)] = int(rating)
                co = False
                break
        if co:
            ratings.append({str(songid):int(rating)})
        c.execute("UPDATE users SET ratings = ? WHERE id=?",(json.dumps(ratings),str(userid)))
        
    c.execute("SELECT * FROM users WHERE id=?", (str(userid)))
    user = c.fetchone()
    if user:
        ratings = json.loads(user[4])
        print(ratings)
        df = pd.read_csv('ratings.csv')
        df['userid'] = df['userid'].astype(str)
        df['songid'] = df['songid'].astype(str)
        mask = (df['userid'] == str(userid)) & (df['songid'] == str(songid))
        if mask.any():
            df.loc[mask, 'ratings'] = int(rating)
            df.to_csv('ratings.csv', index=False)
            cf.refresh()
        else:
            print(f"User {userid} has not rated song {songid} before.")
    conn.commit()

def get_rating(userid,songid):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (str(userid)))
    user = c.fetchone()
    rating = 0
    if user:
        ratings = json.loads(user[4])
        for i in ratings:
            if str(songid) in i.keys():
                rating = int(i[songid])
                break
    conn.commit()
    return rating

def check_playlist(userid,name):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (str(userid)))
    user = c.fetchone()
    exists = False
    #[{n:[{}]}]
    if user:
        playlists = json.loads(user[5])
        for i in playlists:
            if name in i.keys():
                exists = True
                break
    conn.commit()
    return exists

def create_playlist(userid,name):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (str(userid)))
    user = c.fetchone()
    exists = 0
    #[{n:[{}]}]
    if user:
        playlists = json.loads(user[5])
        playlists.append({name:[]})
        playlists = json.dumps(playlists)
        c.execute("UPDATE users SET playlists = ? WHERE id=?",(playlists,str(userid)))
    conn.commit()
    return exists

def get_playlists(userid):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (str(userid)))
    user = c.fetchone()
    #[{n:[{}]}]
    conn.commit()
    if user:
        playlists = json.loads(user[5])
        if len(playlists) > 0:
            _playlists = []
            for i in playlists:
                _playlists.append(list(i.keys())[0])
            return _playlists
    return []

def add_to_playlist(userid,name,songid):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (str(userid)))
    user = c.fetchone()
    #[{n:[{}]}]
    if user:
        playlists = json.loads(user[5])
        for i in playlists:
            if name in i:
                for j in i[name]:
                    if str(j["songid"]) == str(songid):
                        conn.commit()
                        return True
                i[name].append(songs[songid])
                break
        playlists = json.dumps(playlists)
        c.execute("UPDATE users SET playlists = ? WHERE id=?",(playlists,str(userid)))
    conn.commit()
    return True

def remove_from_playlist(userid,name,songid):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (str(userid)))
    user = c.fetchone()
    #[{n:[{}]}]
    if user:
        playlists = json.loads(user[5])
        for i in playlists:
            if name in i:
                for j in i[name]:
                    if str(j["songid"]) == str(songid):
                        i[name].remove(j)
                        break
        playlists = json.dumps(playlists)
        c.execute("UPDATE users SET playlists = ? WHERE id=?",(playlists,str(userid)))
    conn.commit()
    return True

def remove_playlist(userid,name):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (str(userid)))
    user = c.fetchone()
    #[{n:[{}]}]
    if user:
        playlists = json.loads(user[5])
        for i in playlists:
            if name in i:
                playlists.remove(i)
        playlists = json.dumps(playlists)
        c.execute("UPDATE users SET playlists = ? WHERE id=?",(playlists,str(userid)))
    conn.commit()
    return True

def get_playlist(userid,name):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (str(userid)))
    user = c.fetchone()
    #[{n:[{}]}]
    conn.commit()
    if user:
        playlists = json.loads(user[5])
        for i in playlists:
            if name in i:
                return i[name]
    return []

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5000,debug=True)