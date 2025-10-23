from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import base64
import json
from datetime import datetime
import uuid

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://swarm-frontend-indol.vercel.app/"}})
# Student database with valid roll numbers
VALID_ROLL_NUMBERS = set()

# Generate roll numbers from 211-269 and 431-436
for roll in range(201, 270):  # 211-269
    VALID_ROLL_NUMBERS.add(str(roll))
for roll in range(431, 437):  # 431-436
    VALID_ROLL_NUMBERS.add(str(roll))

# In-memory storage
game_data = {
    'admin_logged_in': False,
    'game_active': False,
    'game_ended': False,
    'revealed': False,
    'current_game': None,
    'players': {},
    'guesses': [],
    'swarm_results': {},
    'contribution_log': []
}

# Simple admin credentials
ADMIN_CREDENTIALS = {
    'username': 'admin',
    'password': 'swarm123'
}

def generate_node_id():
    """Generate unique node ID"""
    node_count = len(game_data['players'])
    return f"Node_{str(node_count + 1).zfill(2)}"

def calculate_swarm_confidence(guesses):
    """Calculate swarm confidence from guesses"""
    if not guesses:
        return {}
    
    vote_counts = {}
    for guess in guesses:
        option = guess['guess']
        vote_counts[option] = vote_counts.get(option, 0) + 1
    
    total_votes = sum(vote_counts.values())
    confidence = {}
    
    for option, votes in vote_counts.items():
        confidence[option] = round((votes / total_votes) * 100, 1)
    
    return confidence

def log_contribution(node_id, action, impact=""):
    """Log blockchain-style contribution"""
    log_entry = {
        'block_id': len(game_data['contribution_log']) + 1,
        'node_id': node_id,
        'action': action,
        'timestamp': datetime.now().isoformat(),
        'impact': impact
    }
    game_data['contribution_log'].append(log_entry)

@app.route('/')
def home():
    return jsonify({"message": "Swarm Vision backend is running successfully!"}), 200

@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if username == ADMIN_CREDENTIALS['username'] and password == ADMIN_CREDENTIALS['password']:
        game_data['admin_logged_in'] = True
        return jsonify({'success': True, 'message': 'Admin logged in successfully'})
    
    return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

@app.route('/admin/create_game', methods=['POST'])
def create_game():
    if not game_data['admin_logged_in']:
        return jsonify({'success': False, 'message': 'Admin not logged in'}), 401
    
    data = request.get_json()
    
    # Create uploads directory if it doesn't exist
    uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)
    
    # Handle image upload (base64 for simplicity)
    image_data = data.get('image')
    if image_data:
        # Remove data URL prefix if present
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        # Save image
        image_filename = f"game_image_{uuid.uuid4().hex[:8]}.png"
        image_path = os.path.join(uploads_dir, image_filename)
        
        with open(image_path, 'wb') as f:
            f.write(base64.b64decode(image_data))
    else:
        # Use placeholder image
        image_filename = "placeholder.png"
    
    game_data['current_game'] = {
        'id': str(uuid.uuid4()),
        'image': image_filename,
        'options': data.get('options', []),
        'correct_answer': data.get('correct_answer'),
        'created_at': datetime.now().isoformat()
    }
    
    # Reset game state
    game_data['guesses'] = []
    game_data['swarm_results'] = {}
    game_data['game_ended'] = False
    game_data['revealed'] = False
    
    log_contribution("ADMIN", "Created new game", "Game initialized")
    
    return jsonify({'success': True, 'message': 'Game created successfully'})

@app.route('/start_game', methods=['POST'])
def start_game():
    if not game_data['admin_logged_in']:
        return jsonify({'success': False, 'message': 'Admin not logged in'}), 401
    
    if not game_data['current_game']:
        return jsonify({'success': False, 'message': 'No game created'}), 400
    
    game_data['game_active'] = True
    log_contribution("ADMIN", "Started game", "Game is now live")
    
    return jsonify({'success': True, 'message': 'Game started'})

@app.route('/end_game', methods=['POST'])
def end_game():
    if not game_data['admin_logged_in']:
        return jsonify({'success': False, 'message': 'Admin not logged in'}), 401
    
    game_data['game_active'] = False
    game_data['game_ended'] = True
    
    # Calculate final swarm results
    if game_data['guesses']:
        game_data['swarm_results'] = calculate_swarm_confidence(game_data['guesses'])
    
    log_contribution("ADMIN", "Ended game", "Game ended, ready for reveal")
    
    return jsonify({'success': True, 'message': 'Game ended'})

@app.route('/reveal_answer', methods=['POST'])
def reveal_answer():
    if not game_data['admin_logged_in']:
        return jsonify({'success': False, 'message': 'Admin not logged in'}), 401
    
    if not game_data['game_ended']:
        return jsonify({'success': False, 'message': 'Game not ended yet'}), 400
    
    # Calculate individual results
    individual_results = []
    for guess in game_data['guesses']:
        is_correct = guess['guess'] == game_data['current_game']['correct_answer']
        player_data = game_data['players'][guess['node_id']]
        individual_results.append({
            'node_id': guess['node_id'],
            'player_name': player_data['name'],
            'roll_number': player_data['roll_number'],
            'guess': guess['guess'],
            'correct': is_correct
        })
    
    # Calculate swarm accuracy
    correct_guesses = sum(1 for g in game_data['guesses'] 
                         if g['guess'] == game_data['current_game']['correct_answer'])
    swarm_accuracy = (correct_guesses / len(game_data['guesses']) * 100) if game_data['guesses'] else 0
    
    log_contribution("ADMIN", "Revealed answer", "Results and correct answer shown")
    
    # Mark as revealed
    game_data['revealed'] = True
    
    return jsonify({
        'success': True,
        'individual_results': individual_results,
        'swarm_accuracy': round(swarm_accuracy, 1),
        'correct_answer': game_data['current_game']['correct_answer'],
        'swarm_confidence': game_data['swarm_results'],
        'total_participants': len(game_data['guesses'])
    })

@app.route('/join_game', methods=['POST'])
def join_game():
    data = request.get_json()
    name = data.get('name', '').strip()
    roll_number = data.get('roll_number', '').strip()
    
    if not name:
        return jsonify({'success': False, 'message': 'Name is required'}), 400
    
    if not roll_number:
        return jsonify({'success': False, 'message': 'Roll number is required'}), 400
    
    # Validate roll number
    if roll_number not in VALID_ROLL_NUMBERS:
        return jsonify({'success': False, 'message': 'Invalid roll number. Please enter a valid roll number (211-269 or 431-436)'}), 400
    
    # Check if roll number is already used
    for player_data in game_data['players'].values():
        if player_data.get('roll_number') == roll_number:
            return jsonify({'success': False, 'message': 'Roll number already in use'}), 400
    
    # Generate unique node ID
    node_id = generate_node_id()
    game_data['players'][node_id] = {
        'name': name,
        'roll_number': roll_number,
        'joined_at': datetime.now().isoformat(),
        'avatar': ['🐝', '🤖', '🦾', '🐞', '🦋', '🕷️'][len(game_data['players']) % 6]
    }
    
    log_contribution(node_id, f"Joined as {name} (Roll: {roll_number})", "New node added to swarm")
    
    return jsonify({
        'success': True, 
        'node_id': node_id,
        'roll_number': roll_number,
        'avatar': game_data['players'][node_id]['avatar']
    })

@app.route('/submit_guess', methods=['POST'])
def submit_guess():
    data = request.get_json()
    node_id = data.get('node_id')
    guess = data.get('guess')
    
    if not game_data['game_active']:
        return jsonify({'success': False, 'message': 'Game not active'}), 400
    
    if not node_id or not guess:
        return jsonify({'success': False, 'message': 'Node ID and guess required'}), 400
    
    if node_id not in game_data['players']:
        return jsonify({'success': False, 'message': 'Invalid node ID'}), 400
    
    # Check if already submitted
    existing_guess = next((g for g in game_data['guesses'] if g['node_id'] == node_id), None)
    if existing_guess:
        return jsonify({'success': False, 'message': 'Already submitted'}), 400
    
    # Record guess
    guess_entry = {
        'node_id': node_id,
        'guess': guess,
        'timestamp': datetime.now().isoformat()
    }
    game_data['guesses'].append(guess_entry)
    
    # Calculate current swarm confidence
    current_confidence = calculate_swarm_confidence(game_data['guesses'])
    
    log_contribution(node_id, f"Submitted guess: {guess}", "Contribution added to swarm")
    
    return jsonify({
        'success': True,
        'message': 'Guess submitted successfully',
        'swarm_confidence': current_confidence,
        'total_guesses': len(game_data['guesses'])
    })

@app.route('/get_game_status', methods=['GET'])
def get_game_status():
    return jsonify({
        'game_active': game_data['game_active'],
        'game_ended': game_data['game_ended'],
        'current_game': game_data['current_game'],
        'total_players': len(game_data['players']),
        'total_guesses': len(game_data['guesses'])
    })

@app.route('/get_swarm_results', methods=['GET'])
def get_swarm_results():
    if not game_data['game_ended']:
        return jsonify({'success': False, 'message': 'Game not ended'}), 400
    
    if not game_data.get('revealed', False):
        return jsonify({'success': False, 'message': 'Answer not revealed yet'}), 400
    
    # Calculate swarm accuracy
    correct_guesses = sum(1 for g in game_data['guesses'] 
                         if g['guess'] == game_data['current_game']['correct_answer'])
    swarm_accuracy = (correct_guesses / len(game_data['guesses']) * 100) if game_data['guesses'] else 0
    
    # Return only basic swarm information for students
    return jsonify({
        'success': True,
        'swarm_confidence': game_data['swarm_results'],
        'swarm_accuracy': round(swarm_accuracy, 1),
        'correct_answer': game_data['current_game']['correct_answer'],
        'total_participants': len(game_data['guesses'])
    })

@app.route('/admin/get_detailed_results', methods=['GET'])
def get_detailed_results():
    if not game_data['admin_logged_in']:
        return jsonify({'success': False, 'message': 'Admin not logged in'}), 401
    
    if not game_data['game_ended']:
        return jsonify({'success': False, 'message': 'Game not ended'}), 400
    
    if not game_data.get('revealed', False):
        return jsonify({'success': False, 'message': 'Answer not revealed yet'}), 400
    
    # Calculate individual results for admin only
    individual_results = []
    for guess in game_data['guesses']:
        is_correct = guess['guess'] == game_data['current_game']['correct_answer']
        player_data = game_data['players'][guess['node_id']]
        individual_results.append({
            'node_id': guess['node_id'],
            'player_name': player_data['name'],
            'roll_number': player_data['roll_number'],
            'guess': guess['guess'],
            'correct': is_correct
        })
    
    # Calculate swarm accuracy
    correct_guesses = sum(1 for g in game_data['guesses'] 
                         if g['guess'] == game_data['current_game']['correct_answer'])
    swarm_accuracy = (correct_guesses / len(game_data['guesses']) * 100) if game_data['guesses'] else 0
    
    return jsonify({
        'success': True,
        'swarm_confidence': game_data['swarm_results'],
        'individual_results': individual_results,
        'swarm_accuracy': round(swarm_accuracy, 1),
        'correct_answer': game_data['current_game']['correct_answer'],
        'total_participants': len(game_data['guesses'])
    })

@app.route('/get_dashboard', methods=['GET'])
def get_dashboard():
    if not game_data['game_ended']:
        return jsonify({'success': False, 'message': 'Game not ended'}), 400
    
    # Calculate statistics
    total_players = len(game_data['players'])
    total_guesses = len(game_data['guesses'])
    
    # Individual accuracies
    individual_accuracies = []
    for guess in game_data['guesses']:
        is_correct = guess['guess'] == game_data['current_game']['correct_answer']
        player_data = game_data['players'][guess['node_id']]
        individual_accuracies.append({
            'node_id': guess['node_id'],
            'player_name': player_data['name'],
            'roll_number': player_data['roll_number'],
            'accuracy': 100 if is_correct else 0
        })
    
    # Swarm accuracy
    correct_guesses = sum(1 for g in game_data['guesses'] 
                         if g['guess'] == game_data['current_game']['correct_answer'])
    swarm_accuracy = (correct_guesses / total_guesses * 100) if total_guesses > 0 else 0
    
    return jsonify({
        'success': True,
        'individual_accuracies': individual_accuracies,
        'swarm_accuracy': round(swarm_accuracy, 1),
        'contribution_log': game_data['contribution_log'],
        'total_participants': total_guesses,
        'swarm_confidence': game_data['swarm_results']
    })

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    return send_from_directory(uploads_dir, filename)

@app.route('/reset_game', methods=['POST'])
def reset_game():
    if not game_data['admin_logged_in']:
        return jsonify({'success': False, 'message': 'Admin not logged in'}), 401
    
    # Reset all game data
    game_data.update({
        'game_active': False,
        'game_ended': False,
        'current_game': None,
        'players': {},
        'guesses': [],
        'swarm_results': {},
        'contribution_log': []
    })
    
    return jsonify({'success': True, 'message': 'Game reset successfully'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
