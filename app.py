from flask import Flask, request, jsonify, render_template_string, send_file
from flask_cors import CORS
from openai import OpenAI
import os
import requests
import json
import re
import base64
from datetime import datetime, timedelta
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from PIL import Image
import io
import urllib.request

app = Flask(__name__)

# Налаштування CORS - дозволяємо запити з вашого сайту
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://hlcuz.weblium.site",
            "http://hlcuz.weblium.site",
            "https://trademark-checker-rzdg.onrender.com",
            "*"  # Дозволяємо всі домени (для тестування)
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": True,
        "max_age": 3600
    }
})

# Ініціалізація OpenAI клієнта
try:
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        client = OpenAI(api_key=api_key)
    else:
        client = None
        print("Warning: OPENAI_API_KEY not set")
except Exception as e:
    print(f"Warning: OpenAI client initialization error: {e}")
    client = None

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
                'content': 'Використовуйте загальні принципи аналізу торговельних марок',
                'updated': datetime.now()
            }
    
    def extract_doc_id(self, url):
        if not url:
            return None
        match = re.search(r'/document/d/([a-zA-Z0-9-_]+)', url)
        return match.group(1) if match else None

instruction_manager = InstructionManager(os.getenv('GOOGLE_DOC_URL', ''))

# Глобальне сховище для результатів аналізу
analysis_storage = {}

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
            .btn-success { background: #28a745; color: white; }
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
            .tm-image { max-width: 200px; max-height: 200px; border: 1px solid #ddd; border-radius: 4px; margin: 10px 0; }
            .tm-images-container { display: flex; gap: 20px; flex-wrap: wrap; align-items: center; margin: 15px 0; }
            .image-preview { text-align: center; }
            .image-preview img { max-width: 150px; max-height: 150px; border: 2px solid #007bff; border-radius: 4px; }
            .image-preview p { margin-top: 5px; font-size: 12px; color: #666; }
            .export-buttons { text-align: center; margin: 20px 0; }
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
                    <div class="form-group">
                        <label for="desired-image">Зображення торговельної марки</label>
                        <input type="file" id="desired-image" accept="image/*" onchange="previewImage(this, 'desired-preview')">
                        <div id="desired-preview" class="image-preview" style="display:none; margin-top:10px;"></div>
                        <p style="font-size: 12px; color: #28a745; margin-top: 5px;">
                            ✅ Зображення будуть автоматично проаналізовані за допомогою GPT-4 Vision
                        </p>
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
            let analysisId = null;
            
            function previewImage(input, previewId) {
                const preview = document.getElementById(previewId);
                if (input.files && input.files[0]) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        preview.innerHTML = `<img src="${e.target.result}" alt="Попередній перегляд"><p>Зображення завантажено</p>`;
                        preview.style.display = 'block';
                    }
                    reader.readAsDataURL(input.files[0]);
                } else {
                    preview.style.display = 'none';
                }
            }
            
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
                    <div class="form-group">
                        <label>Зображення</label>
                        <input type="file" name="existing-${existingTMCount}-image" accept="image/*" onchange="previewImage(this, 'existing-${existingTMCount}-preview')">
                        <div id="existing-${existingTMCount}-preview" class="image-preview" style="display:none; margin-top:10px;"></div>
                    </div>
                    <button type="button" class="btn btn-secondary" onclick="removeTM(this)">❌ Видалити</button>
                `;
                container.appendChild(tmDiv);
            }
            
            function removeTM(button) { button.parentElement.remove(); }
            
            addExistingTM();
            
            async function fileToBase64(file) {
                return new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = () => resolve(reader.result);
                    reader.onerror = reject;
                    reader.readAsDataURL(file);
                });
            }
            
            document.getElementById('tmAnalyzerForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                document.getElementById('results').style.display = 'block';
                document.getElementById('loading').style.display = 'block';
                document.getElementById('analysis-results').style.display = 'none';
                
                const formData = new FormData(e.target);
                
                let desiredImage = null;
                const desiredImageFile = document.getElementById('desired-image').files[0];
                if (desiredImageFile) {
                    desiredImage = await fileToBase64(desiredImageFile);
                }
                
                const data = {
                    desired_trademark: {
                        name: document.getElementById('desired-name').value,
                        description: document.getElementById('desired-description').value,
                        classes: document.getElementById('desired-classes').value,
                        image: desiredImage
                    },
                    existing_trademarks: []
                };
                
                for (let i = 1; i <= existingTMCount; i++) {
                    const name = formData.get(`existing-${i}-name`);
                    if (name) {
                        let existingImage = null;
                        const existingImageInput = document.querySelector(`input[name="existing-${i}-image"]`);
                        if (existingImageInput && existingImageInput.files[0]) {
                            existingImage = await fileToBase64(existingImageInput.files[0]);
                        }
                        
                        data.existing_trademarks.push({
                            application_number: formData.get(`existing-${i}-number`) || '',
                            owner: formData.get(`existing-${i}-owner`) || '',
                            name: name,
                            classes: formData.get(`existing-${i}-classes`) || '',
                            image: existingImage
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
                    analysisId = results.analysis_id;
                    
                    document.getElementById('loading').style.display = 'none';
                    displayResults(results);
                } catch (error) {
                    document.getElementById('loading').innerHTML = `<p style="color: red;">Помилка: ${error.message}</p>`;
                }
            });
            
            function displayResults(results) {
                const container = document.getElementById('analysis-results');
                let html = '<h2>📊 Результати аналізу</h2>';
                
                // Зберігаємо analysisId глобально
                if (results.analysis_id) {
                    window.currentAnalysisId = results.analysis_id;
                }
                
                html += `
                    <div class="result-card" style="background: #f0f8ff; border-left: 5px solid #007bff;">
                        <h3>🎯 Бажана торговельна марка</h3>
                        <div class="tm-images-container">
                            <div>
                                <p><strong>Назва:</strong> ${results.desired_trademark.name}</p>
                                <p><strong>Опис:</strong> ${results.desired_trademark.description || 'Не вказано'}</p>
                                <p><strong>Класи МКТП:</strong> ${results.desired_trademark.classes || 'Не вказано'}</p>
                            </div>
                            ${results.desired_trademark.image ? `
                                <div class="image-preview">
                                    <img src="${results.desired_trademark.image}" class="tm-image" alt="Бажана ТМ">
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `;
                
                results.results.forEach((result, index) => {
                    const riskClass = result.overall_risk > 60 ? 'risk-high' : result.overall_risk > 30 ? 'risk-medium' : 'risk-low';
                    html += `
                        <div class="result-card ${riskClass}">
                            <h3>📄 Порівняння з ТМ №${result.trademark_info.application_number || (index + 1)}</h3>
                            
                            <div class="tm-images-container">
                                <div style="flex: 1;">
                                    <p><strong>Власник:</strong> ${result.trademark_info.owner}</p>
                                    <p><strong>Назва:</strong> ${result.trademark_info.name}</p>
                                    <p><strong>Класи МКТП:</strong> ${result.trademark_info.classes}</p>
                                    <div class="percentage" style="margin-top: 15px;">${result.overall_risk}%</div>
                                    <p>Ризик змішування: <strong>${result.confusion_likelihood}</strong></p>
                                </div>
                                ${result.trademark_info.image ? `
                                    <div class="image-preview">
                                        <img src="${result.trademark_info.image}" class="tm-image" alt="Зареєстрована ТМ">
                                        <p>Зареєстрована ТМ</p>
                                    </div>
                                ` : ''}
                            </div>
                            
                            ${result.similarity_analysis && result.similarity_analysis.phonetic ? `
                                <div style="margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 5px;">
                                    <strong>🔊 Фонетична схожість:</strong> ${result.similarity_analysis.phonetic.percentage}%
                                    <p>${result.similarity_analysis.phonetic.details}</p>
                                </div>
                            ` : ''}
                            
                            ${result.similarity_analysis && result.similarity_analysis.semantic ? `
                                <div style="margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 5px;">
                                    <strong>💭 Семантична схожість:</strong> ${result.similarity_analysis.semantic.percentage}%
                                    <p>${result.similarity_analysis.semantic.details}</p>
                                </div>
                            ` : ''}
                            
                            ${result.recommendations && result.recommendations.length > 0 ? `
                                <div style="margin: 10px 0; padding: 10px; background: #fff3e0; border-radius: 5px;">
                                    <strong>💡 Рекомендації:</strong>
                                    <ul style="margin-left: 20px; margin-top: 5px;">
                                        ${result.recommendations.map(rec => `<li>${rec}</li>`).join('')}
                                    </ul>
                                </div>
                            ` : ''}
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
                        <p style="text-align: center; margin-top: 10px;">
                            <small>Дата аналізу: ${new Date(results.analysis_date).toLocaleString('uk-UA')}</small>
                        </p>
                    </div>
                `;
                
                // ОБОВ'ЯЗКОВО додаємо кнопки експорту
                html += `
                    <div class="export-buttons" style="margin: 30px 0; padding: 20px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <h3 style="text-align: center; margin-bottom: 20px;">📥 Завантажити звіт</h3>
                        <div style="display: flex; justify-content: center; gap: 15px; flex-wrap: wrap;">
                            <button class="btn btn-success" onclick="exportReport('docx')" style="font-size: 16px; padding: 15px 30px;">
                                📄 Завантажити DOCX
                            </button>
                            <button class="btn btn-success" onclick="exportReport('pdf')" style="font-size: 16px; padding: 15px 30px;">
                                📑 Завантажити PDF
                            </button>
                        </div>
                        <p style="text-align: center; margin-top: 15px; font-size: 14px; color: #666;">
                            Звіт містить всі результати аналізу та зображення торговельних марок
                        </p>
                    </div>
                `;
                
                container.innerHTML = html;
                container.style.display = 'block';
                
                // Логування для діагностики
                console.log('✅ Результати відображено');
                console.log('📊 Analysis ID:', window.currentAnalysisId);
            }
            
            function exportReport(format) {
                const id = window.currentAnalysisId || analysisId;
                
                if (!id) {
                    alert('Помилка: ID аналізу не знайдено. Спробуйте провести аналіз ще раз.');
                    console.error('analysisId не встановлено');
                    return;
                }
                
                console.log(`Експорт у ${format}, ID: ${id}`);
                window.location.href = `/api/export/${format}/${id}`;
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(html_code)

@app.route('/api/analyze', methods=['POST', 'OPTIONS'])
def analyze_trademarks():
    # Обробка preflight OPTIONS запиту
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response, 200
        
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
        
        analysis_id = datetime.now().strftime('%Y%m%d%H%M%S')
        
        analysis_storage[analysis_id] = {
            'desired_trademark': data['desired_trademark'],
            'results': results,
            'overall_chance': overall_chance,
            'analysis_date': datetime.now().isoformat()
        }
        
        return jsonify({
            'analysis_id': analysis_id,
            'desired_trademark': data['desired_trademark'],
            'results': results,
            'overall_chance': overall_chance,
            'analysis_date': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/export/<format>/<analysis_id>')
def export_report(format, analysis_id):
    if analysis_id not in analysis_storage:
        return jsonify({'error': 'Аналіз не знайдено'}), 404
    
    analysis_data = analysis_storage[analysis_id]
    
    if format == 'docx':
        return export_docx(analysis_data, analysis_id)
    elif format == 'pdf':
        return export_pdf(analysis_data, analysis_id)
    else:
        return jsonify({'error': 'Невідомий формат'}), 400

def export_docx(analysis_data, analysis_id):
    doc = Document()
    
    title = doc.add_heading('ЗВІТ ПРО АНАЛІЗ ТОРГОВЕЛЬНОЇ МАРКИ', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_paragraph(f"Дата аналізу: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    doc.add_paragraph()
    
    doc.add_heading('1. БАЖАНА ДЛЯ РЕЄСТРАЦІЇ ТОРГОВЕЛЬНА МАРКА', 1)
    desired = analysis_data['desired_trademark']
    
    doc.add_paragraph(f"Назва: {desired['name']}")
    if desired.get('description'):
        doc.add_paragraph(f"Опис: {desired['description']}")
    if desired.get('classes'):
        doc.add_paragraph(f"Класи МКТП: {desired['classes']}")
    
    if desired.get('image'):
        try:
            image_data = base64.b64decode(desired['image'].split(',')[1])
            image_stream = io.BytesIO(image_data)
            doc.add_picture(image_stream, width=Inches(2))
        except:
            doc.add_paragraph("Зображення не вдалося додати")
    
    doc.add_page_break()
    
    doc.add_heading('2. РЕЗУЛЬТАТИ ПОРІВНЯННЯ З ЗАРЕЄСТРОВАНИМИ ТМ', 1)
    
    for idx, result in enumerate(analysis_data['results'], 1):
        tm_info = result['trademark_info']
        
        doc.add_heading(f'2.{idx}. Торговельна марка №{tm_info.get("application_number", idx)}', 2)
        
        doc.add_paragraph(f"Власник: {tm_info['owner']}")
        doc.add_paragraph(f"Назва: {tm_info['name']}")
        doc.add_paragraph(f"Класи МКТП: {tm_info['classes']}")
        
        if tm_info.get('image'):
            try:
                image_data = base64.b64decode(tm_info['image'].split(',')[1])
                image_stream = io.BytesIO(image_data)
                doc.add_picture(image_stream, width=Inches(2))
            except:
                doc.add_paragraph("Зображення не вдалося додати")
        
        doc.add_paragraph()
        
        p = doc.add_paragraph()
        p.add_run(f"РИЗИК ЗМІШУВАННЯ: {result['overall_risk']}%").bold = True
        p.add_run(f" ({result['confusion_likelihood']})")
        
        if result.get('similarity_analysis'):
            doc.add_paragraph()
            doc.add_paragraph("Детальний аналіз схожості:")
            
            if result['similarity_analysis'].get('phonetic'):
                doc.add_paragraph(
                    f"• Фонетична схожість: {result['similarity_analysis']['phonetic']['percentage']}% - "
                    f"{result['similarity_analysis']['phonetic']['details']}",
                    style='List Bullet'
                )
            
            if result['similarity_analysis'].get('semantic'):
                doc.add_paragraph(
                    f"• Семантична схожість: {result['similarity_analysis']['semantic']['percentage']}% - "
                    f"{result['similarity_analysis']['semantic']['details']}",
                    style='List Bullet'
                )
        
        if result.get('recommendations'):
            doc.add_paragraph()
            doc.add_paragraph("Рекомендації:")
            for rec in result['recommendations']:
                doc.add_paragraph(rec, style='List Bullet')
        
        doc.add_paragraph()
        doc.add_paragraph('_' * 80)
        doc.add_paragraph()
    
    doc.add_page_break()
    doc.add_heading('3. ЗАГАЛЬНИЙ ВИСНОВОК', 1)
    
    conclusion = doc.add_paragraph()
    conclusion.add_run(
        f"Шанс успішної реєстрації торговельної марки '{desired['name']}': "
    )
    chance_run = conclusion.add_run(f"{analysis_data['overall_chance']}%")
    chance_run.bold = True
    chance_run.font.size = Pt(16)
    
    if analysis_data['overall_chance'] > 70:
        chance_run.font.color.rgb = RGBColor(0, 128, 0)
        doc.add_paragraph("Висока ймовірність успішної реєстрації.")
    elif analysis_data['overall_chance'] > 40:
        chance_run.font.color.rgb = RGBColor(255, 165, 0)
        doc.add_paragraph("Середня ймовірність реєстрації. Рекомендується детальніше вивчити конфліктні ТМ.")
    else:
        chance_run.font.color.rgb = RGBColor(255, 0, 0)
        doc.add_paragraph("Низька ймовірність реєстрації. Рекомендується внести зміни до торговельної марки.")
    
    doc_io = io.BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)
    
    return send_file(
        doc_io,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name=f'Аналіз_ТМ_{analysis_id}.docx'
    )

def export_pdf(analysis_data, analysis_id):
    """Експорт звіту в PDF з підтримкою кирилиці та красивим дизайном"""
    buffer = io.BytesIO()
    
    # Завантажуємо шрифт DejaVu для кирилиці
    try:
        # Завантажуємо DejaVu Sans з CDN
        dejavu_url = "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf"
        dejavu_bold_url = "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans-Bold.ttf"
        
        # Завантажуємо шрифти
        dejavu_data = urllib.request.urlopen(dejavu_url).read()
        dejavu_bold_data = urllib.request.urlopen(dejavu_bold_url).read()
        
        # Зберігаємо тимчасово
        with open('/tmp/DejaVuSans.ttf', 'wb') as f:
            f.write(dejavu_data)
        with open('/tmp/DejaVuSans-Bold.ttf', 'wb') as f:
            f.write(dejavu_bold_data)
        
        # Реєструємо шрифти
        pdfmetrics.registerFont(TTFont('DejaVu', '/tmp/DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVu-Bold', '/tmp/DejaVuSans-Bold.ttf'))
        font_name = 'DejaVu'
        font_bold = 'DejaVu-Bold'
    except:
        print("⚠️ Не вдалося завантажити DejaVu, використовуємо Helvetica")
        font_name = 'Helvetica'
        font_bold = 'Helvetica-Bold'
    
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch,
        leftMargin=0.75*inch,
        rightMargin=0.75*inch
    )
    story = []
    
    # Стилі з кирилицею
    title_style = ParagraphStyle(
        'Title',
        fontName=font_bold,
        fontSize=24,
        textColor=colors.HexColor('#1a237e'),
        alignment=TA_CENTER,
        spaceAfter=20,
        spaceBefore=10
    )
    
    heading1_style = ParagraphStyle(
        'Heading1',
        fontName=font_bold,
        fontSize=18,
        textColor=colors.HexColor('#0d47a1'),
        spaceAfter=15,
        spaceBefore=20
    )
    
    heading2_style = ParagraphStyle(
        'Heading2',
        fontName=font_bold,
        fontSize=14,
        textColor=colors.HexColor('#1565c0'),
        spaceAfter=10,
        spaceBefore=15
    )
    
    normal_style = ParagraphStyle(
        'Normal',
        fontName=font_name,
        fontSize=11,
        leading=16,
        spaceAfter=8
    )
    
    bold_style = ParagraphStyle(
        'Bold',
        fontName=font_bold,
        fontSize=11,
        leading=16,
        spaceAfter=8
    )
    
    # Заголовок звіту
    story.append(Paragraph('ЗВІТ ПРО АНАЛІЗ ТОРГОВЕЛЬНОЇ МАРКИ', title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Дата
    date_text = f"Дата аналізу: {datetime.now().strftime('%d.%m.%Y о %H:%M')}"
    story.append(Paragraph(date_text, normal_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Лінія-розділювач
    story.append(Paragraph('<para alignment="center">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</para>', normal_style))
    story.append(Spacer(1, 0.3*inch))
    
    # 1. БАЖАНА ТМ
    story.append(Paragraph('1. БАЖАНА ДЛЯ РЕЄСТРАЦІЇ ТОРГОВЕЛЬНА МАРКА', heading1_style))
    
    desired = analysis_data['desired_trademark']
    
    # Таблиця з інформацією
    data_table = [
        [Paragraph('<b>Назва:</b>', bold_style), Paragraph(desired['name'], normal_style)],
        [Paragraph('<b>Опис:</b>', bold_style), Paragraph(desired.get('description') or 'Не вказано', normal_style)],
        [Paragraph('<b>Класи МКТП:</b>', bold_style), Paragraph(desired.get('classes') or 'Не вказано', normal_style)],
    ]
    
    table = Table(data_table, colWidths=[2*inch, 4.5*inch])
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.2*inch))
    
    # Зображення бажаної ТМ
    if desired.get('image'):
        try:
            image_data = base64.b64decode(desired['image'].split(',')[1])
            image_stream = io.BytesIO(image_data)
            img = RLImage(image_stream, width=2.5*inch, height=2.5*inch)
            story.append(Paragraph('<para alignment="center"><b>Зображення торговельної марки:</b></para>', bold_style))
            story.append(Spacer(1, 0.1*inch))
            story.append(img)
        except Exception as e:
            print(f"Помилка додавання зображення: {e}")
    
    story.append(PageBreak())
    
    # 2. РЕЗУЛЬТАТИ ПОРІВНЯННЯ
    story.append(Paragraph('2. РЕЗУЛЬТАТИ ПОРІВНЯННЯ З ЗАРЕЄСТРОВАНИМИ ТМ', heading1_style))
    story.append(Spacer(1, 0.2*inch))
    
    for idx, result in enumerate(analysis_data['results'], 1):
        tm_info = result['trademark_info']
        
        # Підзаголовок
        story.append(Paragraph(f'2.{idx}. Торговельна марка №{tm_info.get("application_number", idx)}', heading2_style))
        
        # Інфо про ТМ
        tm_data = [
            [Paragraph('<b>Власник:</b>', bold_style), Paragraph(tm_info['owner'], normal_style)],
            [Paragraph('<b>Назва:</b>', bold_style), Paragraph(tm_info['name'], normal_style)],
            [Paragraph('<b>Класи МКТП:</b>', bold_style), Paragraph(tm_info['classes'], normal_style)],
        ]
        
        tm_table = Table(tm_data, colWidths=[2*inch, 4.5*inch])
        tm_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(tm_table)
        story.append(Spacer(1, 0.15*inch))
        
        # Зображення зареєстрованої ТМ
        if tm_info.get('image'):
            try:
                image_data = base64.b64decode(tm_info['image'].split(',')[1])
                image_stream = io.BytesIO(image_data)
                img = RLImage(image_stream, width=2*inch, height=2*inch)
                story.append(img)
                story.append(Spacer(1, 0.15*inch))
            except:
                pass
        
        # РИЗИК - у кольоровій рамці
        risk = result['overall_risk']
        risk_color = '#d32f2f' if risk > 60 else '#f57c00' if risk > 30 else '#388e3c'
        
        risk_para = Paragraph(
            f'<para alignment="center" backColor="{risk_color}" textColor="white" '
            f'leftIndent="10" rightIndent="10" spaceAfter="10" spaceBefore="10">'
            f'<b>РИЗИК ЗМІШУВАННЯ: {risk}%</b> ({result.get("confusion_likelihood", "невідомо")})'
            f'</para>',
            bold_style
        )
        story.append(risk_para)
        story.append(Spacer(1, 0.2*inch))
        
        # Детальний аналіз
        story.append(Paragraph('<b>Детальний аналіз схожості:</b>', bold_style))
        story.append(Spacer(1, 0.1*inch))
        
        if result.get('similarity_analysis'):
            sim = result['similarity_analysis']
            
            if sim.get('phonetic'):
                story.append(Paragraph(
                    f'🔊 <b>Фонетична схожість: {sim["phonetic"]["percentage"]}%</b>',
                    bold_style
                ))
                story.append(Paragraph(sim["phonetic"]["details"], normal_style))
                story.append(Spacer(1, 0.1*inch))
            
            if sim.get('graphic'):
                story.append(Paragraph(
                    f'✍️ <b>Графічна схожість: {sim["graphic"]["percentage"]}%</b>',
                    bold_style
                ))
                story.append(Paragraph(sim["graphic"]["details"], normal_style))
                story.append(Spacer(1, 0.1*inch))
            
            if sim.get('semantic'):
                story.append(Paragraph(
                    f'💭 <b>Семантична схожість: {sim["semantic"]["percentage"]}%</b>',
                    bold_style
                ))
                story.append(Paragraph(sim["semantic"]["details"], normal_style))
                story.append(Spacer(1, 0.1*inch))
            
            if sim.get('visual'):
                story.append(Paragraph(
                    f'🎨 <b>Візуальна схожість: {sim["visual"]["percentage"]}%</b>',
                    bold_style
                ))
                story.append(Paragraph(sim["visual"]["details"], normal_style))
                story.append(Spacer(1, 0.1*inch))
        
        # Спорідненість товарів
        if result.get('goods_services_relation'):
            goods = result['goods_services_relation']
            story.append(Paragraph(
                f'📦 <b>Спорідненість товарів/послуг: {"ТАК" if goods.get("are_related") else "НІ"}</b>',
                bold_style
            ))
            story.append(Paragraph(goods.get("details", ""), normal_style))
            story.append(Spacer(1, 0.15*inch))
        
        # Рекомендації
        if result.get('recommendations') and len(result['recommendations']) > 0:
            story.append(Paragraph('<b>💡 Рекомендації:</b>', bold_style))
            for rec in result['recommendations']:
                story.append(Paragraph(f'• {rec}', normal_style))
        
        # Розділювач між ТМ
        if idx < len(analysis_data['results']):
            story.append(Spacer(1, 0.2*inch))
            story.append(Paragraph('<para alignment="center">• • •</para>', normal_style))
            story.append(Spacer(1, 0.2*inch))
    
    # 3. ВИСНОВОК
    story.append(PageBreak())
    story.append(Paragraph('3. ЗАГАЛЬНИЙ ВИСНОВОК', heading1_style))
    story.append(Spacer(1, 0.3*inch))
    
    chance = analysis_data['overall_chance']
    chance_color = '#388e3c' if chance > 70 else '#f57c00' if chance > 40 else '#d32f2f'
    
    story.append(Paragraph(
        f'<para alignment="center" fontSize="20">'
        f'Шанс успішної реєстрації торговельної марки<br/>'
        f'<b>"{desired["name"]}"</b>:'
        f'</para>',
        normal_style
    ))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph(
        f'<para alignment="center" fontSize="36" textColor="{chance_color}">'
        f'<b>{chance}%</b>'
        f'</para>',
        bold_style
    ))
    story.append(Spacer(1, 0.3*inch))
    
    # Інтерпретація
    if chance > 70:
        interpretation = "✅ <b>Висока ймовірність успішної реєстрації.</b> Торговельна марка має хороші шанси бути зареєстрованою без конфліктів."
    elif chance > 40:
        interpretation = "⚠️ <b>Середня ймовірність реєстрації.</b> Рекомендується детальніше вивчити конфліктні торговельні марки та, можливо, внести незначні зміни."
    else:
        interpretation = "❌ <b>Низька ймовірність реєстрації.</b> Виявлено значні конфлікти. Настійно рекомендується внести суттєві зміни до торговельної марки."
    
    story.append(Paragraph(interpretation, normal_style))
    
    # Генеруємо PDF
    doc.build(story)
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'Аналіз_ТМ_{analysis_id}.pdf'
    )
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=50, bottomMargin=50)
    story = []
    styles = getSampleStyleSheet()
    
    # Створюємо стилі з підтримкою кирилиці
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#000000'),
        spaceAfter=30,
        alignment=1,  # CENTER
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#000000'),
        spaceAfter=12,
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica'
    )
    
    # Заголовок
    story.append(Paragraph('ZVIT PRO ANALIZ TORGOVELNOI MARKY', title_style))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(f"Data analizu: {datetime.now().strftime('%d.%m.%Y %H:%M')}", normal_style))
    story.append(Spacer(1, 0.5*inch))
    
    # Бажана ТМ
    story.append(Paragraph('1. BAZHANA TORGOVELNA MARKA', heading_style))
    story.append(Spacer(1, 0.2*inch))
    
    desired = analysis_data['desired_trademark']
    story.append(Paragraph(f"<b>Nazva:</b> {desired['name']}", normal_style))
    if desired.get('description'):
        story.append(Paragraph(f"<b>Opys:</b> {desired['description']}", normal_style))
    if desired.get('classes'):
        story.append(Paragraph(f"<b>Klasy MKTP:</b> {desired['classes']}", normal_style))
    
    story.append(Spacer(1, 0.2*inch))
    
    # Зображення бажаної ТМ
    if desired.get('image'):
        try:
            image_data = base64.b64decode(desired['image'].split(',')[1])
            image_stream = io.BytesIO(image_data)
            img = RLImage(image_stream, width=2*inch, height=2*inch)
            story.append(img)
        except:
            story.append(Paragraph("Zobrazhennya ne vdalosya dodaty", normal_style))
    
    story.append(PageBreak())
    
    # Результати
    story.append(Paragraph('2. REZULTATY PORIVNYANNYA', heading_style))
    story.append(Spacer(1, 0.3*inch))
    
    for idx, result in enumerate(analysis_data['results'], 1):
        tm_info = result['trademark_info']
        
        sub_heading = ParagraphStyle('SubHead', parent=heading_style, fontSize=14)
        story.append(Paragraph(f'2.{idx}. TM #{tm_info.get("application_number", idx)}', sub_heading))
        story.append(Spacer(1, 0.1*inch))
        
        story.append(Paragraph(f"<b>Vlasnyk:</b> {tm_info['owner']}", normal_style))
        story.append(Paragraph(f"<b>Nazva:</b> {tm_info['name']}", normal_style))
        story.append(Paragraph(f"<b>Klasy:</b> {tm_info['classes']}", normal_style))
        story.append(Spacer(1, 0.1*inch))
        
        # Зображення зареєстрованої ТМ
        if tm_info.get('image'):
            try:
                image_data = base64.b64decode(tm_info['image'].split(',')[1])
                image_stream = io.BytesIO(image_data)
                img = RLImage(image_stream, width=2*inch, height=2*inch)
                story.append(img)
                story.append(Spacer(1, 0.1*inch))
            except:
                pass
        
        # Ризик
        story.append(Paragraph(
            f"<b>RYZYK ZMISHUVANNYA: {result['overall_risk']}%</b> ({result['confusion_likelihood']})",
            normal_style
        ))
        story.append(Spacer(1, 0.2*inch))
        
        # Аналіз
        if result.get('similarity_analysis'):
            story.append(Paragraph("<b>Detalnyi analiz:</b>", normal_style))
            
            if result['similarity_analysis'].get('phonetic'):
                story.append(Paragraph(
                    f"• Fonetychna: {result['similarity_analysis']['phonetic']['percentage']}%",
                    normal_style
                ))
            
            if result['similarity_analysis'].get('semantic'):
                story.append(Paragraph(
                    f"• Semantychna: {result['similarity_analysis']['semantic']['percentage']}%",
                    normal_style
                ))
        
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph('_' * 80, normal_style))
        story.append(Spacer(1, 0.2*inch))
    
    # Висновок
    story.append(PageBreak())
    story.append(Paragraph('3. VYSNOVOK', heading_style))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph(
        f"Shans uspishnoyi reyestratsiyi: <b>{analysis_data['overall_chance']}%</b>",
        normal_style
    ))
    
    doc.build(story)
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'Analiz_TM_{analysis_id}.pdf'
    )

def analyze_single_pair(desired_tm, existing_tm, instructions):
    """Аналізує пару торговельних марок, включаючи зображення"""
    
    # Діагностика зображень
    print(f"🔍 Аналіз пари: '{desired_tm.get('name')}' vs '{existing_tm.get('name')}'")
    print(f"📸 Бажана ТМ має зображення: {bool(desired_tm.get('image'))}")
    print(f"📸 Зареєстрована ТМ має зображення: {bool(existing_tm.get('image'))}")
    if desired_tm.get('image'):
        print(f"   Розмір зображення бажаної: {len(desired_tm['image'])} символів")
    if existing_tm.get('image'):
        print(f"   Розмір зображення зареєстрованої: {len(existing_tm['image'])} символів")
    
    # Спрощений та чіткий промпт
    text_prompt = f"""Ти експерт з торговельних марок. Порівняй дві марки і дай відповідь ТІЛЬКИ у форматі JSON.

МАРКА 1 (бажана): "{desired_tm.get('name', '')}"
Класи: {desired_tm.get('classes', 'не вказано')}

МАРКА 2 (зареєстрована): "{existing_tm.get('name', '')}"
Власник: {existing_tm.get('owner', 'не вказано')}
Класи: {existing_tm.get('classes', 'не вказано')}

Порівняй марки за такими критеріями (0-100%):
- Фонетична схожість (звучання)
- Графічна схожість (написання)  
- Семантична схожість (значення)
- Візуальна схожість (якщо є зображення - ОПИШИ їх детально)
- Спорідненість товарів/послуг
- Загальний ризик змішування

Відповідь СТРОГО у такому JSON форматі (БЕЗ ```json):
{{"trademark_info":{{"application_number":"{existing_tm.get('application_number','')}","owner":"{existing_tm.get('owner','')}","name":"{existing_tm.get('name','')}","classes":"{existing_tm.get('classes','')}"}}, "identical_test":{{"is_identical":false,"percentage":0,"details":"Чому тотожні або різні"}}, "similarity_analysis":{{"phonetic":{{"percentage":0,"details":"Як звучать - опис"}}, "graphic":{{"percentage":0,"details":"Як написані - опис"}}, "semantic":{{"percentage":0,"details":"Що означають - опис"}}, "visual":{{"percentage":0,"details":"Як виглядають логотипи - детальний опис"}}}}, "goods_services_relation":{{"are_related":false,"details":"Чи однакові товари"}}, "overall_risk":0, "confusion_likelihood":"низька", "recommendations":["Рекомендація 1","Рекомендація 2"]}}"""
    
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise Exception("OpenAI API ключ не налаштований")
        
        if client is None:
            temp_client = OpenAI(api_key=api_key)
        else:
            temp_client = client
        
        # Перевіряємо чи є зображення
        has_desired_image = desired_tm.get('image') and len(str(desired_tm.get('image', ''))) > 100
        has_existing_image = existing_tm.get('image') and len(str(existing_tm.get('image', ''))) > 100
        
        print(f"✅ Перевірка зображень:")
        print(f"   Бажана ТМ: {has_desired_image}")
        print(f"   Зареєстрована ТМ: {has_existing_image}")
        
        if has_desired_image or has_existing_image:
            print(f"🎨 ВИКОРИСТОВУЄМО GPT-4o Vision для аналізу зображень")
            # Використовуємо GPT-4o Vision для аналізу зображень
            messages_content = [
                {
                    "type": "text",
                    "text": text_prompt + "\n\nУВАГА: Тобі надано зображення торговельних марок. ОБОВ'ЯЗКОВО проаналізуй їх візуальну схожість детально!"
                }
            ]
            
            # Додаємо зображення бажаної ТМ (якщо є)
            if has_desired_image:
                # Перевіряємо що це data URL
                if desired_tm['image'].startswith('data:image'):
                    messages_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": desired_tm['image']
                        }
                    })
                    messages_content.append({
                        "type": "text",
                        "text": f"☝️ Це логотип/зображення БАЖАНОЇ торговельної марки '{desired_tm.get('name', '')}'. Опиши його детально."
                    })
            
            # Додаємо зображення зареєстрованої ТМ (якщо є)
            if has_existing_image:
                if existing_tm['image'].startswith('data:image'):
                    messages_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": existing_tm['image']
                        }
                    })
                    messages_content.append({
                        "type": "text",
                        "text": f"☝️ Це логотип/зображення ЗАРЕЄСТРОВАНОЇ торговельної марки '{existing_tm.get('name', '')}'. Опиши його детально та порівняй з попереднім."
                    })
            
            # Запит до GPT-4o Vision
            response = temp_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "Ти експерт з торговельних марок. Відповідай ВИКЛЮЧНО валідним JSON. Ніякого тексту до або після JSON. Ніяких ```json блоків. ТІЛЬКИ чистий JSON."
                    },
                    {
                        "role": "user",
                        "content": messages_content
                    }
                ],
                response_format={"type": "json_object"},  # ВАЖЛИВО: примусовий JSON
                max_tokens=4000,
                temperature=0.1
            )
        else:
            # Звичайний текстовий аналіз без зображень
            response = temp_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "Ти експерт з торговельних марок. Відповідай ВИКЛЮЧНО валідним JSON. Ніякого тексту до або після JSON."
                    },
                    {
                        "role": "user",
                        "content": text_prompt
                    }
                ],
                response_format={"type": "json_object"},  # ВАЖЛИВО: примусовий JSON
                temperature=0.1,
                max_tokens=3000
            )
        
        content = response.choices[0].message.content.strip()
        
        # Очищення від markdown
        content = content.replace("```json", "").replace("```", "").strip()
        lines = content.split('\n')
        cleaned_lines = [line for line in lines if not line.strip().startswith('//')]
        content = '\n'.join(cleaned_lines)
        
        print(f"✅ GPT Response успішна (перші 500 символів): {content[:500]}...")
        
        result = json.loads(content)
        
        # Додаємо зображення до результату
        if existing_tm.get('image'):
            result['trademark_info']['image'] = existing_tm['image']
        
        # Перевірка обов'язкових полів
        if "trademark_info" not in result:
            result["trademark_info"] = {
                "application_number": existing_tm.get('application_number', ''),
                "owner": existing_tm.get('owner', ''),
                "name": existing_tm.get('name', ''),
                "classes": existing_tm.get('classes', '')
            }
        
        if "similarity_analysis" not in result:
            result["similarity_analysis"] = {
                "phonetic": {"percentage": 0, "details": "Аналіз недоступний"},
                "graphic": {"percentage": 0, "details": "Аналіз недоступний"},
                "semantic": {"percentage": 0, "details": "Аналіз недоступний"},
                "visual": {"percentage": 0, "details": "Аналіз недоступний"}
            }
        
        if "overall_risk" not in result:
            result["overall_risk"] = 50
            
        if "confusion_likelihood" not in result:
            result["confusion_likelihood"] = "середня"
            
        if "recommendations" not in result or not result["recommendations"]:
            result["recommendations"] = ["Рекомендується детальніше проаналізувати можливі конфлікти"]
        
        # Додаємо мітку що аналіз зображень виконано
        if (has_desired_image or has_existing_image):
            if 'similarity_analysis' in result and 'visual' in result['similarity_analysis']:
                result['similarity_analysis']['visual']['images_analyzed'] = True
            
        return result
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON Parse Error: {e}")
        print(f"Content that failed: {content if 'content' in locals() else 'No content'}")
        return create_default_result(existing_tm, f"Помилка парсингу JSON: {str(e)}")
        
    except Exception as e:
        print(f"❌ API Error: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return create_default_result(existing_tm, str(e))

def create_default_result(existing_tm, error_msg):
    result = {
        "trademark_info": {
            "application_number": existing_tm.get('application_number', ''),
            "owner": existing_tm.get('owner', ''),
            "name": existing_tm.get('name', ''),
            "classes": existing_tm.get('classes', '')
        },
        "identical_test": {
            "is_identical": False, 
            "percentage": 0, 
            "details": "Аналіз недоступний через технічну помилку"
        },
        "similarity_analysis": {
            "phonetic": {
                "percentage": 0, 
                "details": "Фонетичний аналіз недоступний через технічну помилку"
            },
            "graphic": {
                "percentage": 0, 
                "details": "Графічний аналіз недоступний через технічну помилку"
            },
            "semantic": {
                "percentage": 0, 
                "details": "Семантичний аналіз недоступний через технічну помилку"
            },
            "visual": {
                "percentage": 0, 
                "details": "Візуальний аналіз зображень поки не підтримується. Для аналізу зображень зверніться до експерта."
            }
        },
        "goods_services_relation": {
            "are_related": False, 
            "details": "Аналіз спорідненості недоступний через технічну помилку"
        },
        "overall_risk": 0,
        "confusion_likelihood": "невідомо",
        "recommendations": [
            "Сталася технічна помилка при аналізі",
            "Рекомендується повторити спробу",
            f"Деталі помилки: {error_msg}"
        ]
    }
    
    if existing_tm.get('image'):
        result['trademark_info']['image'] = existing_tm['image']
    
    return result

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
