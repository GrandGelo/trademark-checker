from flask import Flask, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import re
from difflib import SequenceMatcher

app = Flask(__name__)
CORS(app)

class UkrPatentScraper:
    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
    
    def search_trademarks(self, query, classes):
        try:
            self.driver.get('https://sis.ukrpatent.org/uk/search/simple/')
            time.sleep(2)
            
            search_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='search']"))
            )
            search_input.clear()
            search_input.send_keys(query)
            
            search_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            search_button.click()
            
            time.sleep(3)
            
            results = []
            try:
                result_items = self.driver.find_elements(By.CSS_SELECTOR, ".search-result-item")
                
                for item in result_items[:10]:
                    try:
                        number = item.find_element(By.CSS_SELECTOR, ".tm-number").text
                        name = item.find_element(By.CSS_SELECTOR, ".tm-name").text
                        tm_classes = item.find_element(By.CSS_SELECTOR, ".tm-classes").text
                        
                        image_url = None
                        try:
                            img_element = item.find_element(By.CSS_SELECTOR, "img.tm-image")
                            image_url = img_element.get_attribute('src')
                        except:
                            pass
                        
                        results.append({
                            'number': number,
                            'name': name,
                            'classes': tm_classes,
                            'image_url': image_url
                        })
                    except Exception as e:
                        continue
            except:
                pass
            
            return results
            
        except Exception as e:
            print(f"Помилка скрапінгу: {str(e)}")
            return []
        finally:
            self.driver.quit()

class SimilarityAnalyzer:
    def analyze_phonetic_similarity(self, text1, text2):
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()
        
        base_similarity = SequenceMatcher(None, text1, text2).ratio() * 100
        syllable_similarity = self._compare_syllables(text1, text2)
        sound_similarity = self._compare_sounds(text1, text2)
        
        return round((base_similarity + syllable_similarity + sound_similarity) / 3, 2)
    
    def analyze_graphic_similarity(self, text1, text2):
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()
        
        len_diff = abs(len(text1) - len(text2)) / max(len(text1), len(text2))
        len_similarity = (1 - len_diff) * 100
        
        letter_similarity = SequenceMatcher(None, text1, text2).ratio() * 100
        
        common_parts = self._find_common_parts(text1, text2)
        common_similarity = (len(common_parts) / max(len(text1), len(text2))) * 100
        
        return round((len_similarity + letter_similarity + common_similarity) / 3, 2)
    
    def analyze_semantic_similarity(self, text1, text2):
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()
        
        if text1 == text2:
            return 100.0
        
        if text1 in text2 or text2 in text1:
            shorter = min(len(text1), len(text2))
            longer = max(len(text1), len(text2))
            return round((shorter / longer) * 100, 2)
        
        root_similarity = self._compare_roots(text1, text2)
        return root_similarity
    
    def _compare_syllables(self, text1, text2):
        vowels = 'аеєиіїоуюя'
        
        def count_syllables(text):
            return sum(1 for c in text if c in vowels)
        
        syllables1 = count_syllables(text1)
        syllables2 = count_syllables(text2)
        
        if syllables1 == 0 and syllables2 == 0:
            return 100
        
        diff = abs(syllables1 - syllables2) / max(syllables1, syllables2, 1)
        return (1 - diff) * 100
    
    def _compare_sounds(self, text1, text2):
        similar_sounds = [
            ['б', 'п'], ['в', 'ф'], ['г', 'к', 'х'], ['д', 'т'],
            ['з', 'с'], ['ж', 'ш'], ['дз', 'ц'], ['дж', 'ч']
        ]
        
        def normalize_sounds(text):
            for group in similar_sounds:
                for sound in group:
                    text = text.replace(sound, group[0])
            return text
        
        norm1 = normalize_sounds(text1)
        norm2 = normalize_sounds(text2)
        
        return SequenceMatcher(None, norm1, norm2).ratio() * 100
    
    def _find_common_parts(self, text1, text2):
        matcher = SequenceMatcher(None, text1, text2)
        match = matcher.find_longest_match(0, len(text1), 0, len(text2))
        return text1[match.a:match.a + match.size]
    
    def _compare_roots(self, text1, text2):
        root1 = text1[:min(4, len(text1))]
        root2 = text2[:min(4, len(text2))]
        return SequenceMatcher(None, root1, root2).ratio() * 100
    
    def check_identical(self, text1, text2):
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()
        
        if text1 == text2:
            return True
        
        similarity = SequenceMatcher(None, text1, text2).ratio()
        if similarity > 0.95:
            return True
        
        return False
    
    def check_similarity(self, text1, text2):
        phonetic = self.analyze_phonetic_similarity(text1, text2)
        graphic = self.analyze_graphic_similarity(text1, text2)
        semantic = self.analyze_semantic_similarity(text1, text2)
        
        overall = (phonetic + graphic + semantic) / 3
        is_similar = overall > 60
        
        return {
            'phonetic': round(phonetic, 2),
            'graphic': round(graphic, 2),
            'semantic': round(semantic, 2),
            'overall': round(overall, 2),
            'is_similar': is_similar
        }
    
    def check_related_goods(self, classes1, classes2):
        def parse_classes(classes_str):
            return set(int(c.strip()) for c in re.findall(r'\d+', classes_str))
        
        set1 = parse_classes(classes1)
        set2 = parse_classes(classes2)
        
        intersection = set1 & set2
        if intersection:
            return True
        
        related_classes = [
            {1, 2, 3, 4, 5},
            {9, 16, 35, 41, 42},
            {18, 25},
            {29, 30, 31, 32, 33},
        ]
        
        for group in related_classes:
            if set1 & group and set2 & group:
                return True
        
        return False
    
    def generate_reasoning(self, similarity_data, name1, name2):
        reasoning_parts = []
        
        if similarity_data['phonetic'] > 75:
            reasoning_parts.append(f"Висока фонетична схожість ({similarity_data['phonetic']}%)")
        elif similarity_data['phonetic'] > 50:
            reasoning_parts.append(f"Помірна фонетична схожість ({similarity_data['phonetic']}%)")
        
        if similarity_data['graphic'] > 75:
            reasoning_parts.append(f"висока графічна схожість ({similarity_data['graphic']}%)")
        elif similarity_data['graphic'] > 50:
            reasoning_parts.append(f"помірна графічна схожість ({similarity_data['graphic']}%)")
        
        if similarity_data['semantic'] > 75:
            reasoning_parts.append(f"висока семантична схожість ({similarity_data['semantic']}%)")
        elif similarity_data['semantic'] > 50:
            reasoning_parts.append(f"помірна семантична схожість ({similarity_data['semantic']}%)")
        
        if similarity_data['overall'] > 70:
            conclusion = "Споживач може сплутати марки або асоціювати їх зі спільним джерелом."
        elif similarity_data['overall'] > 50:
            conclusion = "Існує ризик асоціації між марками."
        else:
            conclusion = "Марки мають певну схожість, але ризик змішування низький."
        
        reasoning = ". ".join(reasoning_parts).capitalize() + ". " + conclusion
        return reasoning

@app.route('/api/search', methods=['POST'])
def search_and_analyze():
    try:
        data = request.json
        trademark_name = data.get('name')
        trademark_classes = data.get('classes')
        trademark_description = data.get('description', '')
        trademark_image = data.get('image')
        
        if not trademark_name or not trademark_classes:
            return jsonify({'error': 'Необхідно вказати назву та класи'}), 400
        
        scraper = UkrPatentScraper()
        found_marks = scraper.search_trademarks(trademark_name, trademark_classes)
        
        analyzer = SimilarityAnalyzer()
        analyzed_marks = []
        
        for mark in found_marks:
            is_identical = analyzer.check_identical(trademark_name, mark['name'])
            similarity = analyzer.check_similarity(trademark_name, mark['name'])
            related_goods = analyzer.check_related_goods(trademark_classes, mark['classes'])
            reasoning = analyzer.generate_reasoning(similarity, trademark_name, mark['name'])
            
            analyzed_marks.append({
                'number': mark['number'],
                'name': mark['name'],
                'classes': mark['classes'],
                'image': mark.get('image_url', 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="150" height="150"%3E%3Crect fill="%23ddd" width="150" height="150"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" fill="%23999"%3ETM%3C/text%3E%3C/svg%3E'),
                'similarity': {
                    'identical': is_identical,
                    'similar': similarity['is_similar'],
                    'phonetic': similarity['phonetic'],
                    'graphic': similarity['graphic'],
                    'semantic': similarity['semantic'],
                    'overall': similarity['overall'],
                    'reasoning': reasoning
                },
                'relatedGoods': related_goods
            })
        
        risk_score = 0
        for mark in analyzed_marks:
            if mark['similarity']['identical'] and mark['relatedGoods']:
                risk_score += 40
            elif mark['similarity']['similar'] and mark['relatedGoods']:
                risk_score += 25
            elif mark['similarity']['similar']:
                risk_score += 10
        
        risk_score = min(risk_score, 100)
        success_probability = 100 - risk_score
        
        if risk_score > 60:
            risk_level = 'high'
        elif risk_score > 30:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        return jsonify({
            'searchQuery': trademark_name,
            'foundMarks': analyzed_marks,
            'successProbability': success_probability,
            'riskLevel': risk_level
        })
    
    except Exception as e:
        return jsonify({'error': f'Помилка сервера: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
