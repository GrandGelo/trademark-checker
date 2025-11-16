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
        # Кешування на 1 годину
        if self.cache_expiry and datetime.now() < self.cache_expiry:
            return self.cache
            
        try:
            # Конвертуємо Google Docs URL в plain text API
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
            # Fallback до останніх кешованих інструкцій
            return self.cache if self.cache else {
                'content': 'Помилка завантаження інструкцій з Google Docs',
                'updated': datetime.now()
            }
    
    def extract_doc_id(self, url):
        # Витягує ID документа з Google Docs URL
        match = re.search(r'/document/d/([a-zA-Z0-9-_]+)', url)
        return match.group(1) if match else None

# Ініціалізація менеджера інструкцій
instruction_manager = InstructionManager(os.getenv('GOOGLE_DOC_URL', ''))

@app.route('/')
def index():
    # HTML код для головної сторінки
    html_code = """
    <!DOCTYPE html>
    <html lang="uk">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Аналіз торговельних марок</title>
        <style>
            .tm-analyzer {
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                font-family: Arial, sans-serif;
            }
            
            .form-section {
                background: #f8f9fa;
                padding: 20px;
                margin: 20px 0;
                border-radius: 8px;
                border: 1px solid #dee2e6;
            }
            
            .form-group {
                margin-bottom: 15px;
            }
            
            .form-group label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
            }
            
            .form-group input,
            .form-group textarea {
                width: 100%;
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 4px;
                box-sizing: border-box;
            }
            
            .existing-tm {
                border: 1px solid #007bff;
                margin: 10px 0;
                padding: 15px;
                border-radius: 5px;
                background: #f0f8ff;
            }
            
            .btn {
                padding: 12px 24px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
                margin: 5px;
            }
            
            .btn-primary {
                background: #007bff;
                color: white;
            }
            
            .btn-success {
                background: #28a745;
                color: white;
            }
            
            .btn-secondary {
                background: #6c757d;
                color: white;
            }
            
            .results {
                margin-top: 30px;
            }
            
            .result-card {
                border: 1px solid #ddd;
                margin: 15px 0;
                padding: 20px;
                border-radius: 8px;
                background: white;
            }
            
            .risk-high { border-left: 5px solid #dc3545; }
            .risk-medium { border-left: 5px solid #ffc107; }
            .risk-low { border-left: 5px solid #28a745; }
            
            .percentage {
                font-size: 24px;
                font-weight: bold;
                color: #007bff;
            }
            
            .loading {
                text-align: center;
                padding: 40px;
            }
            
            .spinner {
                border: 4px solid #f3f3f3;
                border-top: 4px solid #3498db;
                border-radius: 50%;
                width: 50px;
                height: 50px;
                animation: spin 2s linear infinite;
                margin: 0 auto;
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            
            .export-buttons {
                margin: 20px 0;
                text-align: center;
            }
            
            .final-conclusion {
                background: #e8f5e8;
                border: 1px solid #4caf50;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
            }
            
            .success-chance {
                font-size: 28px;
                font-weight: bold;
                text-align: center;
                color: #2e7d32;
            }
        </style>
    </head>
    <body>
        <div class="tm-analyzer">
            <h1>🔍 Аналізатор торговельних марок</h1>
            
            <form id="tmAnalyzerForm">
                <!-- Бажана ТМ -->
                <div class="form-section">
                    <h2>📝 Бажана для реєстрації торговельна марка</h2>
                    
                    <div class="form-group">
                        <label for="desired-name">Назва торговельної марки *</label>
                        <input type="text" id="desired-name" name="desired-name" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="desired-description">Опис</label>
                        <textarea id="desired-description" name="desired-description" rows="3"></textarea>
                    </div>
                    
                    <div class="form-group">
                        <label for="desired-classes">Класи МКТП (через кому)</label>
                        <input type="text" id="desired-classes" name="desired-classes" placeholder="наприклад: 25, 35, 42">
                    </div>
                    
                    <div class="form-group">
                        <label for="desired-image">Зображення торговельної марки</label>
                        <input type="file" id="desired-image" name="desired-image" accept="image/*">
                    </div>
                </div>
                
                <!-- Зареєстровані ТМ -->
                <div class="form-section">
                    <h2>📋 Зареєстровані торговельні марки для порівняння</h2>
                    
                    <div id="existing-trademarks">
                        <!-- Тут будуть додаватися поля для зареєстрованих ТМ -->
                    </div>
                    
                    <button type="button" class="btn btn-secondary" onclick="addExistingTM()">
                        ➕ Додати торговельну марку
                    </button>
                </div>
                
                <div style="text-align: center;">
                    <button type="submit" class="btn btn-primary">
                        🔍 Провести аналіз
                    </button>
                </div>
            </form>
            
            <!-- Результати -->
            <div id="results" class="results" style="display: none;">
                <div id="loading" class="loading">
                    <div class="spinner"></div>
                    <p>Аналізуємо торговельні марки...</p>
                </div>
                
                <div id="analysis-results" style="display: none;">
                    <!-- Тут будуть результати аналізу -->
                </div>
            </div>
        </div>

        <script>
            let existingTMCount = 0;
            
            // Додавання нової зареєстрованої ТМ
            function addExistingTM() {
                existingTMCount++;
                const container = document.getElementById('existing-trademarks');
                
                const tmDiv = document.createElement('div');
                tmDiv.className = 'existing-tm';
                tmDiv.innerHTML = `
                    <h3>Торговельна марка #${existingTMCount}</h3>
                    
                    <div class="form-group">
                        <label>Номер заявки</label>
                        <input type="text" name="existing-${existingTMCount}-number" placeholder="№123456">
                    </div>
                    
                    <div class="form-group">
                        <label>Власник</label>
                        <input type="text" name="existing-${existingTMCount}-owner" placeholder="Назва компанії">
                    </div>
                    
                    <div class="form-group">
                        <label>Назва ТМ</label>
                        <input type="text" name="existing-${existingTMCount}-name" required>
                    </div>
                    
                    <div class="form-group">
                        <label>Класи МКТП</label>
                        <input type="text" name="existing-${existingTMCount}-classes" placeholder="25, 35">
                    </div>
                    
                    <div class="form-group">
                        <label>Зображення</label>
                        <input type="file" name="existing-${existingTMCount}-image" accept="image/*">
                    </div>
                    
                    <button type="button" class="btn btn-secondary" onclick="removeTM(this)">
                        ❌ Видалити
                    </button>
                `;
                
                container.appendChild(tmDiv);
            }
            
            function removeTM(button) {
                button.parentElement.remove();
            }
            
            // Додаємо першу зареєстровану ТМ за замовчуванням
            addExistingTM();
            
            // Обробка форми
            document.getElementById('tmAnalyzerForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                
                // Показуємо завантаження
                document.getElementById('results').style.display = 'block';
                document.getElementById('loading').style.display = 'block';
                document.getElementById('analysis-results').style.display = 'none';
                
                // Збираємо дані форми
                const formData = new FormData(e.target);
                const data = {
                    desired_trademark: {
                        name: formData.get('desired-name'),
                        description: formData.get('desired-description'),
                        classes: formData.get('desired-classes'),
                        image: formData.get('desired-image') ? 'uploaded' : null
                    },
                    existing_trademarks: []
                };
                
                // Збираємо дані про зареєстровані ТМ
                for (let i = 1; i <= existingTMCount; i++) {
                    const name = formData.get(`existing-${i}-name`);
                    if (name) {
                        data.existing_trademarks.push({
                            application_number: formData.get(`existing-${i}-number`) || '',
                            owner: formData.get(`existing-${i}-owner`) || '',
                            name: name,
                            classes: formData.get(`existing-${i}-classes`) || '',
                            image: formData.get(`existing-${i}-image`) ? 'uploaded' : null
                        });
                    }
                }
                
                try {
                    // Відправляємо запит на аналіз
                    const response = await fetch('/api/analyze', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(data)
                    });
                    
                    const results = await response.json();
                    
                    // Приховуємо завантаження
                    document.getElementById('loading').style.display = 'none';
                    
                    // Показуємо результати
                    displayResults(results);
                    
                } catch (error) {
                    console.error('Помилка:', error);
                    document.getElementById('loading').innerHTML = `
                        <p style="color: red;">Помилка при аналізі: ${error.message}</p>
                    `;
                }
            });
            
            function displayResults(results) {
                const container = document.getElementById('analysis-results');
                let html = '<h2>📊 Результати аналізу</h2>';
                
                // Результати по кожній ТМ
                results.results.forEach((result, index) => {
                    const riskClass = result.overall_risk > 60 ? 'risk-high' : 
                                    result.overall_risk > 30 ? 'risk-medium' : 'risk-low';
                    
                    html += `
                        <div class="result-card ${riskClass}">
                            <h3>📄 Торговельна марка №${result.trademark_info.application_number || (index + 1)}</h3>
                            
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                                <div>
                                    <p><strong>Власник:</strong> ${result.trademark_info.owner}</p>
                                    <p><strong>Назва:</strong> ${result.trademark_info.name}</p>
                                    <p><strong>Класи МКТП:</strong> ${result.trademark_info.classes}</p>
                                </div>
                                
                                <div style="text-align: center;">
                                    <div class="percentage">${result.overall_risk}%</div>
                                    <p>Ризик змішування</p>
                                </div>
                            </div>
                            
                            <h4>🔍 Детальний аналіз схожості</h4>
                            
                            ${result.identical_test.is_identical ? `
                                <div style="background: #ffebee; padding: 15px; border-radius: 5px; margin: 10px 0;">
                                    <h5>⚠️ Тест тотожності: ТОТОЖНІ (${result.identical_test.percentage}%)</h5>
                                    <p>${result.identical_test.details}</p>
                                </div>
                            ` : ''}
                            
                            ${result.similarity_analysis.phonetic ? `
                                <div style="margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 5px;">
                                    <h5>🔊 Фонетична схожість: ${result.similarity_analysis.phonetic.percentage}%</h5>
                                    <p>${result.similarity_analysis.phonetic.details}</p>
                                </div>
                            ` : ''}
                            
                            ${result.similarity_analysis.graphic ? `
                                <div style="margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 5px;">
                                    <h5>👁️ Графічна схожість: ${result.similarity_analysis.graphic.percentage}%</h5>
                                    <p>${result.similarity_analysis.graphic.details}</p>
                                </div>
                            ` : ''}
                            
                            ${result.similarity_analysis.semantic ? `
                                <div style="margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 5px;">
                                    <h5>💭 Семантична схожість: ${result.similarity_analysis.semantic.percentage}%</h5>
                                    <p>${result.similarity_analysis.semantic.details}</p>
                                </div>
                            ` : ''}
                            
                            ${result.similarity_analysis.visual ? `
                                <div style="margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 5px;">
                                    <h5>🎨 Візуальна схожість: ${result.similarity_analysis.visual.percentage}%</h5>
                                    <p>${result.similarity_analysis.visual.details}</p>
                                </div>
                            ` : ''}
                            
                            <div style="margin: 15px 0; padding: 10px; background: #e3f2fd; border-radius: 5px;">
                                <h5>📦 Спорідненість товарів/послуг: ${result.goods_services_relation.are_related ? 'ТАК' : 'НІ'}</h5>
                                <p>${result.goods_services_relation.details}</p>
                            </div>
                            
                            ${result.recommendations && result.recommendations.length > 0 ? `
                                <div style="margin: 15px 0; padding: 10px; background: #fff3e0; border-radius: 5px;">
                                    <h5>💡 Рекомендації:</h5>
                                    <ul>
                                        ${result.recommendations.map(rec => `<li>${rec}</li>`).join('')}
                                    </ul>
                                </div>
                            ` : ''}
                        </div>
                    `;
                });
                
                // Загальний висновок
                const chanceColor = results.overall_chance > 70 ? '#4caf50' : 
                                  results.overall_chance > 40 ? '#ff9800' : '#f44336';
                
                html += `
                    <div class="final-conclusion">
                        <h2>📋 Загальний висновок</h2>
                        <div class="success-chance" style="color: ${chanceColor}">
                            ✅ Шанс успішної реєстрації: ${results.overall_chance}%
                        </div>
                        
                        <div style="margin-top: 20px; text-align: center;">
                            <p><strong>Дата аналізу:</strong> ${new Date(results.analysis_date).toLocaleString('uk-UA')}</p>
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
    # Обробка preflight запиту
    if request.method == 'OPTIONS':
        return '', 204
        
    try:
        data = request.json
        
        # Отримуємо свіжі інструкції з Google Docs
        instructions = instruction_manager.get_instructions()
        
        # Аналізуємо кожну зареєстровану ТМ
        results = []
        for existing_tm in data['existing_trademarks']:
            analysis = analyze_single_pair(
                desired_tm=data['desired_trademark'],
                existing_tm=existing_tm,
                instructions=instructions['content']
            )
            results.append(analysis)
        
        # Розраховуємо загальний шанс реєстрації
        overall_chance = calculate_registration_chance(results)
        
        return jsonify({
            'results': results,
            'overall_chance': overall_chance,
            'analysis_date': datetime.now().isoformat()
        })
    
    except Exception as e:
        print(f"Error in analyze_trademarks: {e}")
        return jsonify({'error': str(e)}), 500

def analyze_single_pair(desired_tm, existing_tm, instructions):
    prompt = f"""
Ти - експерт з інтелектуальної власності. Проаналізуй схожість торговельних марок.

БАЖАНА ДЛЯ РЕЄСТРАЦІЇ ТМ:
- Назва: {desired_tm.get('name', '')}
- Опис: {desired_tm.get('description', '')}
- Класи МКТП: {desired_tm.get('classes', '')}

ЗАРЕЄСТРОВАНА ТМ:
- Номер заявки: {existing_tm.get('application_number', '')}
- Власник: {existing_tm.get('owner', '')}
- Назва: {existing_tm.get('name', '')}
- Класи МКТП: {existing_tm.get('classes', '')}

ІНСТРУКЦІЇ ДЛЯ АНАЛІЗУ:
{instructions[:2000]}

Надай аналіз ТІЛЬКИ у валідному JSON форматі без будь-якого іншого тексту:
{{
    "trademark_info": {{
        "application_number": "{existing_tm.get('application_number', '')}",
        "owner": "{existing_tm.get('owner', '')}",
        "name": "{existing_tm.get('name', '')}",
        "classes": "{existing_tm.get('classes', '')}"
    }},
    "identical_test": {{
        "is_identical": false,
        "percentage": 0,
        "details": "Детальне обгрунтування"
    }},
    "similarity_analysis": {{
        "phonetic": {{"percentage": 0, "details": "Аналіз звучання"}},
        "graphic": {{"percentage": 0, "details": "Аналіз написання"}},
        "semantic": {{"percentage": 0, "details": "Аналіз значення"}},
        "visual": {{"percentage": 0, "details": "Аналіз зображень"}}
    }},
    "goods_services_relation": {{
        "are_related": false,
        "details": "Аналіз спорідненості"
    }},
    "overall_risk": 0,
    "confusion_likelihood": "низька",
    "recommendations": ["рекомендація"]
}}
"""
    
    try:
        # Перевірка API ключа
        if not openai.api_key or openai.api_key == "":
            raise Exception("OpenAI API ключ не налаштований")
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system", 
                    "content": "Ти експерт з торговельних марок. Відповідай ТІЛЬКИ валідним JSON без додаткового тексту."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=2000
        )
        
        content = response.choices[0].message.content.strip()
        
        # Видалення markdown форматування якщо є
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        elif content.startswith("```"):
            content = content.replace("```", "").strip()
        
        # Парсинг JSON
        result = json.loads(content)
        
        # Перевірка обов'язкових полів
        if "trademark_info" not in result:
            result["trademark_info"] = existing_tm
        if "overall_risk" not in result:
            result["overall_risk"] = 50
            
        return result
        
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {e}")
        print(f"Response content: {content if 'content' in locals() else 'No content'}")
        return create_default_result(existing_tm, f"Помилка парсингу JSON: {str(e)}")
        
    except Exception as e:
        print(f"API Error: {e}")
        return create_default_result(existing_tm, str(e))

def create_default_result(existing_tm, error_msg):
    """Створює стандартну відповідь у випадку помилки"""
    return {
        "trademark_info": {
            "application_number": existing_tm.get('application_number', ''),
            "owner": existing_tm.get('owner', ''),
            "name": existing_tm.get('name', ''),
            "classes": existing_tm.get('classes', '')
        },
        "identical_test": {
            "is_identical": False,
            "percentage": 0,
            "details": f"Помилка аналізу: {error_msg}"
        },
        "similarity_analysis": {
            "phonetic": {"percentage": 0, "details": "Аналіз недоступний через помилку"},
            "graphic": {"percentage": 0, "details": "Аналіз недоступний через помилку"},
            "semantic": {"percentage": 0, "details": "Аналіз недоступний через помилку"},
            "visual": {"percentage": 0, "details": "Аналіз недоступний через помилку"}
        },
        "goods_services_relation": {
            "are_related": False,
            "details": "Аналіз недоступний через помилку"
        },
        "overall_risk": 0,
        "confusion_likelihood": "невідомо",
        "recommendations": [
            "Перевірте налаштування API",
            f"Деталі помилки: {error_msg}"
        ]
    }

def calculate_registration_chance(results):
    """Розраховує шанс успішної реєстрації"""
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
```

---

## 📁 Файл 2: `requirements.txt`
```
Flask==2.3.3
openai==1.12.0
requests==2.31.0
gunicorn==21.2.0
flask-cors==4.0.0
