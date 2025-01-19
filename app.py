import os
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import pandas as pd
import numpy as np
from salesforce_analyzer import SalesforceAnalyzer
import threading
import uuid
import json
import tempfile
from flask_cors import CORS
import logging

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuration
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Custom JSON encoder to handle NaN values
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer, np.floating)):
            return int(obj) if isinstance(obj, np.integer) else float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif pd.isna(obj):
            return None
        return super().default(obj)

app.json_encoder = CustomJSONEncoder

# Store analysis tasks
analysis_tasks = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'csv'

def clean_results_for_json(results):
    """Clean results to ensure JSON serialization works properly."""
    cleaned = []
    for result in results:
        cleaned_result = {}
        for key, value in result.items():
            if pd.isna(value):
                cleaned_result[key] = None
            elif isinstance(value, (np.integer, np.floating)):
                cleaned_result[key] = float(value) if isinstance(value, np.floating) else int(value)
            else:
                cleaned_result[key] = value
        cleaned.append(cleaned_result)
    return cleaned

def analyze_domains(file_path, task_id):
    try:
        # Update task status
        analysis_tasks[task_id]['status'] = 'processing'
        
        # Read input CSV
        df = pd.read_csv(file_path)
        if 'domain' not in df.columns:
            raise ValueError("Input CSV must have a 'domain' column")
        
        analyzer = SalesforceAnalyzer()
        results = []
        total_domains = len(df)
        
        for idx, domain in enumerate(df['domain']):
            score, status, stats = analyzer.analyze_domain(domain)
            if not isinstance(stats, dict):
                stats = {}
            
            results.append({
                'domain': domain,
                'score': float(score) if not pd.isna(score) else 0.0,
                'status': status,
                'pages_crawled': int(stats.get('pages_crawled', 0)),
                'total_mentions': int(stats.get('total_mentions', 0)),
                'redirected_to': stats.get('redirected_to', None)
            })
            
            # Update progress
            progress = ((idx + 1) / total_domains) * 100
            analysis_tasks[task_id]['progress'] = progress
        
        # Save results
        results_df = pd.DataFrame(results)
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], f'results_{task_id}.csv')
        results_df.to_csv(output_path, index=False)
        
        # Update task status
        analysis_tasks[task_id]['status'] = 'completed'
        analysis_tasks[task_id]['result_file'] = output_path
        analysis_tasks[task_id]['results'] = results  # Store results in memory
        
    except Exception as e:
        analysis_tasks[task_id]['status'] = 'failed'
        analysis_tasks[task_id]['error'] = str(e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Please upload a CSV file'}), 400
    
    try:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Create new analysis task
        task_id = str(uuid.uuid4())
        analysis_tasks[task_id] = {
            'status': 'starting',
            'progress': 0,
            'file_path': file_path
        }
        
        # Start analysis in background
        thread = threading.Thread(target=analyze_domains, args=(file_path, task_id))
        thread.start()
        
        return jsonify({'task_id': task_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analyze', methods=['POST'])
def analyze_text_input():
    try:
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
            
        data = request.get_json()
        if not data or 'domains' not in data:
            return jsonify({'error': 'No domains provided'}), 400
        
        domains = data['domains']
        if not domains or not isinstance(domains, list):
            return jsonify({'error': 'Invalid domains format. Expected a list of domains'}), 400
        
        # Create a temporary CSV file
        temp_file = os.path.join(app.config['UPLOAD_FOLDER'], f'temp_{uuid.uuid4()}.csv')
        df = pd.DataFrame({'domain': domains})
        df.to_csv(temp_file, index=False)
        
        # Create new analysis task
        task_id = str(uuid.uuid4())
        analysis_tasks[task_id] = {
            'status': 'starting',
            'progress': 0,
            'file_path': temp_file
        }
        
        # Start analysis in background
        thread = threading.Thread(target=analyze_domains, args=(temp_file, task_id))
        thread.start()
        
        return jsonify({'task_id': task_id})
        
    except Exception as e:
        app.logger.error(f"Error in analyze_text_input: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/status/<task_id>')
def get_status(task_id):
    if task_id not in analysis_tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    task = analysis_tasks[task_id]
    response = {
        'status': task['status'],
        'progress': task.get('progress', 0),
        'error': task.get('error')
    }
    
    # Include results data if analysis is complete
    if task['status'] == 'completed':
        try:
            results = task.get('results', [])
            if not results:
                # If results not in memory, read from file
                df = pd.read_csv(task['result_file'])
                results = df.to_dict('records')
            
            # Clean results for JSON serialization
            cleaned_results = clean_results_for_json(results)
            
            # Calculate summary statistics
            total_domains = len(cleaned_results)
            successful_domains = sum(1 for r in cleaned_results if 'Error' not in str(r['status']))
            success_rate = (successful_domains / total_domains * 100) if total_domains > 0 else 0
            average_score = sum(r['score'] for r in cleaned_results) / total_domains if total_domains > 0 else 0
            
            response.update({
                'results': cleaned_results,
                'summary': {
                    'total_domains': total_domains,
                    'success_rate': round(success_rate, 1),
                    'average_score': round(average_score, 1)
                }
            })
        except Exception as e:
            response['error'] = f"Error loading results: {str(e)}"
    
    return jsonify(response)

@app.route('/download/<task_id>')
def download_results(task_id):
    if task_id not in analysis_tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    task = analysis_tasks[task_id]
    if task['status'] != 'completed':
        return jsonify({'error': 'Results not ready'}), 400
    
    return send_file(
        task['result_file'],
        as_attachment=True,
        download_name='salesforce_analysis_results.csv'
    )

if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 5001))
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        app.logger.error(f"Error starting server: {e}") 