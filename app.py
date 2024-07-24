import json
import os
import socket
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, render_template_string
import requests
import time
import mysql.connector

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure key

CONFIG_DIR = 'configurations/'  # Directory where configuration files are stored
IMAGES_FOLDER = 'static/images/'  # Path to the images folder

def get_db_connection():
    """MySQL database connection."""
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='Passw0rd123',
        database='PickByLight'
    )

def get_machine_name():
    """Get the hostname of the machine."""
    return socket.gethostname()

def load_predefined_materials(machine_name):
    """Load predefined materials based on the machine name."""
    config_path = os.path.join(CONFIG_DIR, f'config_{machine_name}.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config.get('predefined_materials', [])
    return []

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form['user_id'].strip()
        if user_id:  # Here you can add more user validation if needed
            session['user_id'] = user_id
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='User ID is required.')
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/compare_materials', methods=['POST'])
def compare_materials():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    car_id = request.form['car_id'].strip()
    machine_name = get_machine_name()
    if not car_id:
        return jsonify({'error': 'Please enter a car ID.'}), 400

    predefined_materials = load_predefined_materials(machine_name)

    start_time = time.time()  # Start time

    response = requests.get(f'http://localhost:5000/fetch_jit_components_api?PRODN={car_id}')
    if response.status_code != 200:
        return jsonify({'error': 'Failed to fetch data from the existing API.'}), 500

    data = response.json()
    execution_time = time.time() - start_time  # Calculate execution time

    matched_materials = set()

    for item in data.get('results', []):
        bom = item.get('BOM', [])
        for component in bom:
            material = component.get('Material', '')
            if material in predefined_materials:
                matched_materials.add(material)

    if not matched_materials:
        return jsonify({'error': 'No matching materials found.'}), 404

    matched_materials_list = list(matched_materials)
    materials_with_pictures = {material: f"{IMAGES_FOLDER}{material}.png" for material in matched_materials_list}

    # Insert scan data into the database
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute('''
        INSERT INTO scans (car_id, user_id, machine_name, scan_time, execution_time)
        VALUES (%s, %s, %s, NOW(), %s)
    ''', (car_id, session['user_id'], machine_name, execution_time))
    connection.commit()
    cursor.close()
    connection.close()

    return render_template_string('''
    <table class="materials-table">
        {% for material, picture in materials_with_pictures.items() %}
            {% if loop.index % 2 == 1 %}
            <tr>
            {% endif %}
            <td class="material-item">
                <img src="{{ url_for('static', filename='images/' + material + '.png') }}" alt="Picture of {{ material }}" class="material-image">
                <p>{{ material }}</p>
            </td>
            {% if loop.index % 2 == 0 or loop.last %}
            </tr>
            {% endif %}
        {% endfor %}
    </table>
    ''', materials_with_pictures=materials_with_pictures)

if __name__ == '__main__':
    app.run(port=5001, debug=True)
