from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import openai
import os
import requests
import json
import re
from datetime import datetime, timedelta

app = Flask(__name__)

# Налаштування CORS
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": True
    }
})

# Налаштування OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

class InstructionManager:
    def __init__(self, google_doc_url):
        self.doc_url = google_doc_url
        self.cache = {}
        self.cache_expiry = None
        
    def get_instructions(self):
        if self.cache_expiry and datetime.now() < self.cache_expiry:
            return self.cache
            
        try:
            doc_id = self.extract_doc_id(self.doc_url)
            if not doc_id:
                raise Exception("Неправильний URL Google Docs")
                
            export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
            response = requests.get(export_url)
            response.raise_for_status()
            
            instructions = response.text
            
            self.cache = {
                'content': instructions,
                'updated': datetime.now()
            }
            self.cache_expiry = datetime.now() + timedelta(hours=1)
            
            return self.cache
        except Exception as e:
            print(f"Помилка завантаження інструкцій: {e}")
            return self.cache if self.cache else {
                'content': 'Помилка завантаження інструкцій з Google Docs',
                'updated': datetime.now()
            }
    
    def extract_doc_id(self, url):
        match = re.search(r'/document/d/([a-zA-Z0-9-_]+)', url)
        return match.group(1) if match else None

instruction_manager = InstructionManager(os.getenv('GOOGLE_DOC_URL', ''))

@app.route('/')
def index():
    html_code = """
    <!DOCTYPE html>
    <html lang="uk">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Аналіз торговельних марок</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: Arial, sans-serif; background: #f5f5f5; }
            .tm-analyzer { max-width: 1200px; margin: 0 auto; padding: 20px; }
            h1 { color: #333; margin-bottom: 30px; }
            .form-section { background: white; padding: 25px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .form-group { margin-bottom: 15px; }
            .form-group label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; }
            .form-group input, .form-group textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
            .existing-tm { border: 2px solid #007bff; margin: 15px 0; padding: 20px; border-radius: 5px; background: #f0f8ff; }
            .btn { padding: 12px 24px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; margin: 5px; transition: 0.3s; }
            .btn:hover { opacity: 0.9; }
            .btn-primary { background: #007bff; color: white; }
            .btn-secondary { background: #6c757d; color: white; }
            .loading { text-align: center; padding: 40px; }
            .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; margin: 0 auto; }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            .results { margin-top: 30px; }
            .result-card { background: white; border: 1px solid #ddd; margin: 15px 0; padding: 20px; border-radius: 8px; }
            .risk-high { border-left: 5px solid #dc3545; }
            .risk-medium { border-left: 5px solid #ffc107; }
            .risk-low { border-left: 5px solid #28a745; }
            .percentage { font-size: 32px; font-weight: bold; color: #007bff; }
            .final-conclusion { background: #e8f5e8; border: 2px solid #4caf50; padding: 25px; border-radius: 8px; margin: 20px 0; }
            .success-chance { font-size: 28px; font-weight: bold; text-align: center; margin: 20px 0; }
        </style>
    </head>
    <body>
        <div class="tm-analyzer">
            <h1>🔍 Аналізатор торговельних марок</h1>
            
            <form id="tmAnalyzerForm">
                <div class="form-section">
                    <h2>📝 Бажана торговельна марка</h2>
                    <div class="form-group">
                        <label for="desired-name">Назва *</label>
                        <input type="text" id="desired-name" required>
                    </div>
                    <div class="form-group">
                        <label for="desired-description">Опис</label>
                        <textarea id="desired-description" rows="3"></textarea>
                    </div>
                    <div class="form-group">
                        <label for="desired-classes">Класи МКТП</label>
                        <input type="text" id="desired-classes" placeholder="25, 35, 42">
                    </div>
                </div>
                
                <div class="form-section">
                    <h2>📋 Зареєстровані торговельні марки</h2>
                    <div id="existing-trademarks"></div>
                    <button type="button" class="btn btn-secondary" onclick="addExistingTM()">➕ Додати ТМ</button>
                </div>
                
                <div style="text-align: center;">
                    <button type="submit" class="btn btn-primary">🔍 Провести аналіз</button>
                </div>
            </form>
            
            <div id="results" class="results" style="display: none;">
                <div id="loading" class="loading">
                    <div class="spinner"></div>
                    <p>Аналізуємо торговельні марки...</p>
                </div>
                <div id="analysis-results" style="display: none;"></div>
            </div>
        </div>

        <script>
            let existingTMCount = 0;
            
            function addExistingTM() {
                existingTMCount++;
                const container = document.getElementById('existing-trademarks');
                const tmDiv = document.createElement('div');
                tmDiv.className = 'existing-tm';
                tmDiv.innerHTML = `
                    <h3>ТМ #${existingTMCount}</h3>
                    <div class="form-group">
                        <label>Номер заявки</label>
                        <input type="text" name="existing-${existingTMCount}-number">
                    </div>
                    <div class="form-group">
                        <label>Власник</label>
                        <input type="text" name="existing-${existingTMCount}-owner">
                    </div>
                    <div class="form-group">
                        <label>Назва *</label>
                        <input type="text" name="existing-${existingTMCount}-name" required>
                    </div>
                    <div class="form-group">
                        <label>Класи МКТП</label>
                        <input type="text" name="existing-${existingTMCount}-classes">
                    </div>
                    <button type="button" class="btn btn-secondary" onclick="removeTM(this)">❌ Видалити</button>
                `;
                container.appendChild(tmDiv);
            }
            
            function removeTM(button) { button.parentElement.remove(); }
            
            addExistingTM();
            
            document.getElementById('tmAnalyzerForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                document.getElementById('results').style.display = 'block';
                document.getElementById('loading').style.display = 'block';
                document.getElementById('analysis-results').style.display = 'none';
                
                const formData = new FormData(e.target);
                const data = {
                    desired_trademark: {
                        name: document.getElementById('desired-name').value,
                        description: document.getElementById('desired-description').value,
                        classes: document.getElementById('desired-classes').value
                    },
                    existing_trademarks: []
                };
                
                for (let i = 1; i <= existingTMCount; i++) {
                    const name = formData.get(`existing-${i}-name`);
                    if (name) {
                        data.existing_trademarks.push({
                            application_number: formData.get(`existing-${i}-number`) || '',
                            owner: formData.get(`existing-${i}-owner`) || '',
                            name: name,
                            classes: formData.get(`existing-${i}-classes`) || ''
                        });
                    }
                }
                
                try {
                    const response = await fetch('/api/analyze', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });
                    
                    if (!response.ok) throw new Error(`HTTP ${response.status}`);
                    
                    const results = await response.json();
                    document.getElementById('loading').style.display = 'none';
                    displayResults(results);
                } catch (error) {
                    document.getElementById('loading').innerHTML = `<p style="color: red;">Помилка: ${error.message}</p>`;
                }
            });
            
            function displayResults(results) {
                const container = document.getElementById('analysis-results');
                let html = '<h2>📊 Результати аналізу</h2>';
                
                results.results.forEach((result, index) => {
                    const riskClass = result.overall_risk > 60 ? 'risk-high' : result.overall_risk > 30 ? 'risk-medium' : 'risk-low';
                    html += `
                        <div class="result-card ${riskClass}">
                            <h3>📄 ТМ №${result.trademark_info.application_number || (index + 1)}</h3>
                            <p><strong>Власник:</strong> ${result.trademark_info.owner}</p>
                            <p><strong>Назва:</strong> ${result.trademark_info.name}</p>
                            <div class="percentage">${result.overall_risk}%</div>
                            <p>Ризик змішування: ${result.confusion_likelihood}</p>
                            ${result.recommendations ? `<p><strong>Рекомендації:</strong> ${result.recommendations.join(', ')}</p>` : ''}
                        </div>
                    `;
                });
                
                const chanceColor = results.overall_chance > 70 ? '#4caf50' : results.overall_chance > 40 ? '#ff9800' : '#f44336';
                html += `
                    <div class="final-conclusion">
                        <h2>📋 Загальний висновок</h2>
                        <div class="success-chance" style="color: ${chanceColor}">
                            ✅ Шанс успішної реєстрації: ${results.overall_chance}%
                        </div>
                    </div>
                `;
                
                container.innerHTML = html;
                container.style.display = 'block';
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(html_code)

@app.route('/api/analyze', methods=['POST', 'OPTIONS'])
def analyze_trademarks():
    if request.method == 'OPTIONS':
        return '', 204
        
    try:
        data = request.json
        instructions = instruction_manager.get_instructions()
        
        results = []
        for existing_tm in data['existing_trademarks']:
            analysis = analyze_single_pair(
                desired_tm=data['desired_trademark'],
                existing_tm=existing_tm,
                instructions=instructions['content']
            )
            results.append(analysis)
        
        overall_chance = calculate_registration_chance(results)
        
        return jsonify({
            'results': results,
            'overall_chance': overall_chance,
            'analysis_date': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

def analyze_single_pair(desired_tm, existing_tm, instructions):
    prompt = f"""Проаналізуй схожість торговельних марок.

БАЖАНА: {desired_tm.get('name', '')} (класи: {desired_tm.get('classes', '')})
ЗАРЕЄСТРОВАНА: {desired_tm.get('name', '')} (класи: {existing_tm.get('classes', '')})

Відповідь ТІЛЬКИ у JSON форматі:
{{"trademark_info": {{"application_number": "{existing_tm.get('application_number', '')}", "owner": "{existing_tm.get('owner', '')}", "name": "{existing_tm.get('name', '')}", "classes": "{existing_tm.get('classes', '')}"}}, "identical_test": {{"is_identical": false, "percentage": 0, "details": ""}}, "similarity_analysis": {{"phonetic": {{"percentage": 0, "details": ""}}, "graphic": {{"percentage": 0, "details": ""}}, "semantic": {{"percentage": 0, "details": ""}}}}, "goods_services_relation": {{"are_related": false, "details": ""}}, "overall_risk": 0, "confusion_likelihood": "низька", "recommendations": []}}"""
    
    try:
        if not openai.api_key:
            raise Exception("API ключ не налаштований")
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Відповідай ТІЛЬКИ валідним JSON без додаткового тексту."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=2000
        )
        
        content = response.choices[0].message.content.strip()
        
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        elif content.startswith("```"):
            content = content.replace("```", "").strip()
        
        result = json.loads(content)
        
        if "trademark_info" not in result:
            result["trademark_info"] = existing_tm
        if "overall_risk" not in result:
            result["overall_risk"] = 50
            
        return result
        
    except Exception as e:
        print(f"API Error: {e}")
        return create_default_result(existing_tm, str(e))

def create_default_result(existing_tm, error_msg):
    return {
        "trademark_info": {
            "application_number": existing_tm.get('application_number', ''),
            "owner": existing_tm.get('owner', ''),
            "name": existing_tm.get('name', ''),
            "classes": existing_tm.get('classes', '')
        },
        "identical_test": {"is_identical": False, "percentage": 0, "details": f"Помилка: {error_msg}"},
        "similarity_analysis": {
            "phonetic": {"percentage": 0, "details": "Недоступно"},
            "graphic": {"percentage": 0, "details": "Недоступно"},
            "semantic": {"percentage": 0, "details": "Недоступно"}
        },
        "goods_services_relation": {"are_related": False, "details": "Недоступно"},
        "overall_risk": 0,
        "confusion_likelihood": "невідомо",
        "recommendations": [f"Помилка: {error_msg}"]
    }

def calculate_registration_chance(results):
    if not results:
        return 95
    max_risk = max([result.get('overall_risk', 0) for result in results])
    if max_risk > 80:
        return 10
    elif max_risk > 60:
        return 30
    elif max_risk > 40:
        return 60
    elif max_risk > 20:
        return 80
    else:
        return 95

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
