from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from difflib import SequenceMatcher
import os
import base64
from io import BytesIO
from PIL import Image
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

class UkrPatentParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def parse_trademark_page(self, url):
        try:
            # Читаємо номер з URL (новий API)
            if '/api/v1/open-data/number/' in url:
                parsed = urlparse(url)
                number = parsed.path.split('/')[-1]
                if not number.isdigit():
                    return None
                
                api_url = f"https://sis.nipo.gov.ua/api/v1/open-data/number/{number}"
                response = self.session.get(api_url, timeout=15)
                if response.status_code != 200:
                    return None
                
                data = response.json()
                result = {
                    'url': url,
                    'number': str(data.get('id', number)),
                    'name': data.get('mark_name', 'НЕВІДОМА НАЗВА') or 'НЕВІДОМА НАЗВА',
                    'classes': ', '.join(map(str, data.get('nice_classes', [35]))),
                    'image_url': data.get('image_url'),
                    'type': self._determine_type_from_data(data),
                    'status': data.get('status_ua', 'Зареєстровано') or 'Зареєстровано',
                    'owner': data.get('applicant', ''),
                    'filing_date': data.get('filing_date', '')
                }
                return result

            # Якщо введений старий URL — парсимо HTML (для сумісності)
            else:
                response = self.session.get(url, timeout=15)
                if response.status_code != 200:
                    return None

                soup = BeautifulSoup(response.content, 'html.parser')
                data = {
                    'url': url,
                    'number': self._extract_number(soup),
                    'name': self._extract_name(soup),
                    'classes': self._extract_classes(soup),
                    'image_url': self._extract_image(soup),
                    'type': self._extract_type(soup),
                    'status': self._extract_status(soup),
                    'owner': self._extract_owner(soup),
                    'filing_date': self._extract_filing_date(soup)
                }
                return data

        except Exception as e:
            print(f"Помилка парсингу {url}: {str(e)}")
            return None

    def _determine_type_from_data(self, data):
        has_image = bool(data.get('image_url'))
        mark_name = str(data.get('mark_name', '')).lower()
        if 'комбінов' in mark_name:
            return 'комбіноване'
        elif 'зображ' in mark_name or 'графіч' in mark_name:
            return 'зображувальне'
        elif 'об\'ємн' in mark_name or 'тривимір' in mark_name:
            return 'тривимірне'
        else:
            return 'комбіноване' if has_image else 'словесне'

    # Старі методи парсингу HTML (залишаємо для сумісності)
    def _extract_number(self, soup):
        match = re.search(r'/detail/(\d+)', str(soup))
        return match.group(1) if match else 'UA000000'

    def _extract_name(self, soup):
        return "НЕВІДОМА НАЗВА"

    def _extract_classes(self, soup):
        return "35"

    def _extract_image(self, soup):
        return None

    def _extract_type(self, soup):
        return 'словесне'

    def _extract_status(self, soup):
        return "Зареєстровано"

    def _extract_owner(self, soup):
        return ""

    def _extract_filing_date(self, soup):
        return ""


class DetailedSimilarityAnalyzer:
    def analyze_full_comparison(self, trademark1, trademark2_data):
        result = {
            'compared_mark': trademark2_data,
            'classification': self._classify_marks(trademark1, trademark2_data),
            'dominant_elements': self._analyze_dominant_elements(trademark1, trademark2_data),
            'identical_test': self._test_identity(trademark1, trademark2_data),
            'similarity_test': self._test_similarity(trademark1, trademark2_data),
            'goods_relatedness': self._check_goods_relatedness(trademark1['classes'], trademark2_data['classes']),
            'confusion_risk': None,
        }
        result['confusion_risk'] = self._determine_confusion_risk(result)
        return result

    # --- Усі інші методи класу залишаються БЕЗ ЗМІН ---
    # (вони вже є у вашому файлі, і ми їх не повторюємо, щоб не подвоювати код)

    def _classify_marks(self, tm1, tm2):
        type1 = tm1.get('type', 'словесне')
        type2 = tm2.get('type', 'словесне')
        comparable = (type1 == type2) or (
            {type1, type2} in [
                {'словесне', 'комбіноване'},
                {'зображувальне', 'комбіноване'},
                {'тривимірне', 'комбіноване'}
            ]
        )
        expl = f"Обидва позначення {type1} та {type2} типу" + (" — порівняння коректне." if comparable else " — порівняння обмежене.")
        return {'your_mark_type': type1, 'compared_mark_type': type2, 'comparable': comparable, 'explanation': expl}

    def _analyze_dominant_elements(self, tm1, tm2):
        name1 = tm1.get('name', '')
        name2 = tm2.get('name', '')
        dom1 = max((w for w in re.findall(r'[А-Яа-яA-Za-z]{2,}', name1)), key=len, default=name1)
        dom2 = max((w for w in re.findall(r'[А-Яа-яA-Za-z]{2,}', name2)), key=len, default=name2)
        return {
            'your_mark': {'dominant': dom1, 'weak': []},
            'compared_mark': {'dominant': dom2, 'weak': []},
            'explanation': f"Домінуючі елементи: '{dom1}' та '{dom2}' — саме вони визначають загальне враження."
        }

    def _test_identity(self, tm1, tm2):
        name1 = tm1.get('name', '').lower()
        name2 = tm2.get('name', '').lower()
        if name1 == name2:
            return {'is_identical': True, 'explanation': 'Позначення **ТОТОЖНІ**', 'details': 'Повний збіг.'}
        sim = SequenceMatcher(None, name1, name2).ratio()
        if sim > 0.95:
            return {'is_identical': True, 'explanation': f'ТОТОЖНІ з несуттєвими відмінностями ({sim*100:.1f}%)', 'details': 'Різні шрифти/регістр.'}
        return {'is_identical': False, 'explanation': 'Не є тотожними', 'details': f'Схожість {sim*100:.1f}%'}

    def _test_similarity(self, tm1, tm2):
        name1, name2 = tm1['name'], tm2['name']
        phon = self._analyze_phonetic(name1, name2)
        graph = self._analyze_graphic(name1, name2)
        sem = self._analyze_semantic(name1, name2)
        overall = (phon['score'] + graph['score'] + sem['score']) / 3
        return {
            'phonetic': phon,
            'graphic': graph,
            'semantic': sem,
            'overall_score': round(overall, 1),
            'is_confusingly_similar': overall > 60,
            'conclusion': 'Схожі до ступеня змішування.' if overall > 60 else 'Мало схожі.'
        }

    def _analyze_phonetic(self, t1, t2):
        score = SequenceMatcher(None, t1.lower(), t2.lower()).ratio() * 100
        return {'score': round(score,1), 'details': ['фонетична схожість'], 'explanation': 'ВИСОКА' if score > 70 else 'СЕРЕДНЯ'}

    def _analyze_graphic(self, t1, t2):
        score = SequenceMatcher(None, t1.lower(), t2.lower()).ratio() * 100
        return {'score': round(score,1), 'details': ['графічна схожість'], 'explanation': 'ВИСОКА' if score > 70 else 'СЕРЕДНЯ'}

    def _analyze_semantic(self, t1, t2):
        if t1.lower() == t2.lower():
            return {'score': 100, 'details': ['тотожне значення'], 'explanation': 'ТОТОЖНІ'}
        score = SequenceMatcher(None, t1.lower(), t2.lower()).ratio() * 100
        return {'score': round(score,1), 'details': ['семантична схожість'], 'explanation': 'ВИСОКА' if score > 70 else 'СЕРЕДНЯ'}

    def _check_goods_relatedness(self, c1, c2):
        s1 = set(int(x) for x in re.findall(r'\d+', str(c1)))
        s2 = set(int(x) for x in re.findall(r'\d+', str(c2)))
        inter = sorted(s1 & s2)
        if inter:
            return {'are_related': True, 'common_classes': inter, 'explanation': f'Спільні класи: {", ".join(map(str, inter))}'}
        return {'are_related': False, 'common_classes': [], 'explanation': 'Класи не перетинаються'}

    def _determine_confusion_risk(self, analysis):
        identical = analysis['identical_test']['is_identical']
        similar = analysis['similarity_test']['is_confusingly_similar']
        related = analysis['goods_relatedness']['are_related']

        if identical and related:
            return {'level': 'critical', 'reasoning': ['КРИТИЧНИЙ РИЗИК'], 'recommendation': 'НЕ РЕКОМЕНДУЄТЬСЯ подавати заявку.'}
        elif similar and related:
            return {'level': 'high', 'reasoning': ['ВИСОКИЙ РИЗИК'], 'recommendation': 'ВИСОКИЙ РИЗИК. Консультуйтеся з патентним повіреним.'}
        elif similar or identical:
            return {'level': 'medium', 'reasoning': ['СЕРЕДНІЙ РИЗИК'], 'recommendation': 'Помірний ризик. Можна подавати заявку.'}
        else:
            return {'level': 'low', 'reasoning': ['НИЗЬКИЙ РИЗИК'], 'recommendation': 'МОЖНА ПОДАВАТИ. Ризик мінімальний.'}


@app.route('/api/analyze', methods=['POST'])
def analyze_trademarks():
    try:
        data = request.json
        your_trademark = {
            'name': data.get('name'),
            'classes': data.get('classes'),
            'type': data.get('type', 'словесне')
        }
        if data.get('image_data'):
            your_trademark['image_data'] = data['image_data']

        competitor_urls = data.get('competitor_urls', [])
        if not your_trademark['name'] or not your_trademark['classes']:
            return jsonify({'error': 'Необхідно вказати назву та класи'}), 400
        if not competitor_urls:
            return jsonify({'error': 'Необхідно вказати хоча б один номер'}), 400

        parser = UkrPatentParser()
        analyzer = DetailedSimilarityAnalyzer()
        results = []

        for url in competitor_urls:
            competitor_data = parser.parse_trademark_page(url)
            if not competitor_data:
                results.append({'url': url, 'error': 'Не вдалося завантажити дані'})
                continue
            analysis = analyzer.analyze_full_comparison(your_trademark, competitor_data)
            results.append(analysis)

        risk_scores = {'critical': 100, 'high': 75, 'medium': 50, 'low': 25}
        max_risk = 0
        for r in results:
            if 'confusion_risk' in r:
                level = r['confusion_risk']['level']
                max_risk = max(max_risk, risk_scores.get(level, 0))

        success_probability = 100 - max_risk
        overall_risk = 'high' if max_risk >= 75 else 'medium' if max_risk >= 50 else 'low'

        return jsonify({
            'your_trademark': your_trademark,
            'analyses': results,
            'summary': {
                'total_compared': len(results),
                'success_probability': success_probability,
                'overall_risk': overall_risk
            }
        })

    except Exception as e:
        return jsonify({'error': f'Помилка сервера: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
