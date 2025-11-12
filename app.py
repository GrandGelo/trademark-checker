from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from difflib import SequenceMatcher
import os

app = Flask(__name__)
CORS(app)

class UkrPatentParser:
    """Парсер конкретних сторінок торговельних марок"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def parse_trademark_page(self, url):
        """Витягує всі дані зі сторінки торговельної марки"""
        try:
            response = self.session.get(url, timeout=15)
            
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Витягуємо основні дані
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
    
    def _extract_number(self, soup):
        """Витягує реєстраційний номер"""
        selectors = [
            '.registration-number',
            '.tm-number',
            '.app-number',
            'td:contains("Номер реєстрації")',
            'span.number'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.text.strip()
        
        # Витягуємо з URL якщо не знайдено
        match = re.search(r'/detail/(\d+)', soup.url if hasattr(soup, 'url') else '')
        return match.group(1) if match else 'UA000000'
    
    def _extract_name(self, soup):
        """Витягує назву марки"""
        selectors = [
            '.trademark-name',
            '.tm-name',
            'h1.title',
            '.mark-name',
            'td:contains("Зображення") + td'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.text.strip()
        
        return "НЕВІДОМА НАЗВА"
    
    def _extract_classes(self, soup):
        """Витягує класи МКТП"""
        selectors = [
            '.nice-classes',
            '.tm-classes',
            'td:contains("Клас") + td',
            'td:contains("МКТП") + td'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.text.strip()
        
        return "35"
    
    def _extract_image(self, soup):
        """Витягує URL зображення"""
        selectors = [
            '.trademark-image img',
            '.tm-image',
            'img[alt*="марк"]',
            '.mark-img img'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem and 'src' in elem.attrs:
                src = elem['src']
                # Перетворюємо відносний URL на абсолютний
                if src.startswith('http'):
                    return src
                elif src.startswith('/'):
                    return 'https://sis.nipo.gov.ua' + src
        
        return None
    
    def _extract_type(self, soup):
        """Визначає тип позначення"""
        type_text = soup.text.lower()
        
        if 'словесн' in type_text:
            return 'словесне'
        elif 'зображувальн' in type_text or 'графічн' in type_text:
            return 'зображувальне'
        elif 'комбінован' in type_text:
            return 'комбіноване'
        elif 'об\'ємн' in type_text or 'тривимірн' in type_text:
            return 'тривимірне'
        
        # Визначаємо автоматично
        has_image = self._extract_image(soup) is not None
        name = self._extract_name(soup)
        has_words = bool(re.search(r'[А-Яа-яA-Za-z]{2,}', name))
        
        if has_image and has_words:
            return 'комбіноване'
        elif has_image:
            return 'зображувальне'
        else:
            return 'словесне'
    
    def _extract_status(self, soup):
        """Витягує статус марки"""
        selectors = [
            '.status',
            'td:contains("Статус") + td',
            '.tm-status'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.text.strip()
        
        return "Зареєстровано"
    
    def _extract_owner(self, soup):
        """Витягує власника"""
        selectors = [
            '.owner',
            'td:contains("Власник") + td',
            '.applicant'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.text.strip()
        
        return None
    
    def _extract_filing_date(self, soup):
        """Витягує дату подання"""
        selectors = [
            '.filing-date',
            'td:contains("Дата подання") + td',
            '.application-date'
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.text.strip()
        
        return None

class DetailedSimilarityAnalyzer:
    """Детальний аналізатор схожості згідно з українським законодавством"""
    
    def analyze_full_comparison(self, trademark1, trademark2_data):
        """Повний аналіз схожості з детальними поясненнями"""
        
        result = {
            'compared_mark': trademark2_data,
            'classification': self._classify_marks(trademark1, trademark2_data),
            'dominant_elements': self._analyze_dominant_elements(trademark1, trademark2_data),
            'identical_test': self._test_identity(trademark1, trademark2_data),
            'similarity_test': self._test_similarity(trademark1, trademark2_data),
            'goods_relatedness': self._check_goods_relatedness(trademark1['classes'], trademark2_data['classes']),
            'confusion_risk': None,
            'detailed_reasoning': []
        }
        
        # Висновок про ризик змішування
        result['confusion_risk'] = self._determine_confusion_risk(result)
        
        return result
    
    def _classify_marks(self, tm1, tm2):
        """Крок 1: Класифікація типів позначень"""
        return {
            'your_mark_type': tm1.get('type', 'словесне'),
            'compared_mark_type': tm2.get('type', 'словесне'),
            'comparable': self._are_types_comparable(tm1.get('type'), tm2.get('type')),
            'explanation': self._get_type_comparison_explanation(tm1.get('type'), tm2.get('type'))
        }
    
    def _are_types_comparable(self, type1, type2):
        """Перевіряє чи можна порівнювати ці типи"""
        comparable_pairs = [
            {'словесне', 'словесне'},
            {'словесне', 'комбіноване'},
            {'зображувальне', 'зображувальне'},
            {'зображувальне', 'комбіноване'},
            {'комбіноване', 'комбіноване'},
            {'тривимірне', 'тривимірне'},
            {'тривимірне', 'комбіноване'}
        ]
        
        return {type1, type2} in comparable_pairs or type1 == type2
    
    def _get_type_comparison_explanation(self, type1, type2):
        """Пояснення про порівнюваність типів"""
        if type1 == type2:
            return f"Обидва позначення {type1} типу - порівняння коректне."
        elif self._are_types_comparable(type1, type2):
            return f"Позначення різних типів ({type1} та {type2}), але містять порівнювані елементи."
        else:
            return f"Позначення різних типів ({type1} та {type2}) - пряме порівняння обмежене."
    
    def _analyze_dominant_elements(self, tm1, tm2):
        """Крок 2: Аналіз домінуючих елементів"""
        name1 = tm1.get('name', '')
        name2 = tm2.get('name', '')
        
        analysis = {
            'your_mark': {
                'dominant': self._find_dominant_elements(name1),
                'weak': self._find_weak_elements(name1)
            },
            'compared_mark': {
                'dominant': self._find_dominant_elements(name2),
                'weak': self._find_weak_elements(name2)
            },
            'explanation': ''
        }
        
        if analysis['your_mark']['dominant'] and analysis['compared_mark']['dominant']:
            analysis['explanation'] = f"Домінуючі елементи: '{analysis['your_mark']['dominant']}' та '{analysis['compared_mark']['dominant']}' - саме вони визначають загальне враження."
        
        return analysis
    
    def _find_dominant_elements(self, text):
        """Знаходить домінуючі елементи"""
        # Вибираємо найдовше слово як домінуюче
        words = re.findall(r'[А-ЯA-Z][а-яa-z]+', text)
        if words:
            return max(words, key=len)
        return text
    
    def _find_weak_elements(self, text):
        """Знаходить слабкі елементи"""
        weak_words = ['товари', 'послуги', 'груп', 'компанія', 'тм', 'ukraine', 'ua']
        found_weak = []
        
        text_lower = text.lower()
        for weak in weak_words:
            if weak in text_lower:
                found_weak.append(weak)
        
        return found_weak
    
    def _test_identity(self, tm1, tm2):
        """Крок 3: Тест тотожності"""
        name1 = tm1.get('name', '').lower().strip()
        name2 = tm2.get('name', '').lower().strip()
        
        # Повна тотожність
        if name1 == name2:
            return {
                'is_identical': True,
                'explanation': 'Позначення **ТОТОЖНІ** - повний збіг всіх елементів без будь-яких змін.',
                'details': 'Відповідно до п.3 Критеріїв, позначення відтворює всі елементи без змін та доповнень.'
            }
        
        # Несуттєві відмінності
        similarity = SequenceMatcher(None, name1, name2).ratio()
        if similarity > 0.95:
            differences = self._find_differences(name1, name2)
            return {
                'is_identical': True,
                'explanation': f'Позначення **ТОТОЖНІ** з несуттєвими відмінностями (схожість {similarity*100:.1f}%).',
                'details': f'Відмінності: {differences}. Пересічний споживач не помітить цих змін (різні шрифти, регістр, незначні зміни).'
            }
        
        return {
            'is_identical': False,
            'explanation': 'Позначення **НЕ є тотожними** - наявні суттєві відмінності.',
            'details': f'Схожість складає {similarity*100:.1f}%, що недостатньо для визнання тотожності (потрібно >95%).'
        }
    
    def _find_differences(self, text1, text2):
        """Знаходить відмінності між текстами"""
        if len(text1) != len(text2):
            return f"різна довжина ({len(text1)} vs {len(text2)} символів)"
        
        diffs = []
        for i, (c1, c2) in enumerate(zip(text1, text2)):
            if c1 != c2:
                diffs.append(f"позиція {i}: '{c1}' vs '{c2}'")
        
        return ', '.join(diffs[:3]) if diffs else "мінімальні"
    
    def _test_similarity(self, tm1, tm2):
        """Крок 5: Детальний тест схожості"""
        name1 = tm1.get('name', '')
        name2 = tm2.get('name', '')
        
        # Словесний аналіз
        phonetic = self._analyze_phonetic(name1, name2)
        graphic = self._analyze_graphic(name1, name2)
        semantic = self._analyze_semantic(name1, name2)
        
        overall = (phonetic['score'] + graphic['score'] + semantic['score']) / 3
        is_confusingly_similar = overall > 60
        
        return {
            'phonetic': phonetic,
            'graphic': graphic,
            'semantic': semantic,
            'overall_score': round(overall, 1),
            'is_confusingly_similar': is_confusingly_similar,
            'conclusion': self._generate_similarity_conclusion(phonetic, graphic, semantic, overall)
        }
    
    def _analyze_phonetic(self, text1, text2):
        """П. 5.1: Фонетична схожість"""
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()
        
        # Базова схожість
        base_score = SequenceMatcher(None, text1, text2).ratio() * 100
        
        # Порівняння складів
        syllables1 = self._count_syllables(text1)
        syllables2 = self._count_syllables(text2)
        syllable_score = 100 - (abs(syllables1 - syllables2) / max(syllables1, syllables2, 1)) * 100
        
        # Схожість звуків
        sound_score = self._compare_sounds(text1, text2)
        
        # Наголос і ритм
        stress_similar = syllables1 == syllables2
        
        final_score = (base_score + syllable_score + sound_score) / 3
        
        details = []
        details.append(f"Базова фонетична схожість: {base_score:.1f}%")
        details.append(f"Кількість складів: {syllables1} vs {syllables2} (схожість {syllable_score:.1f}%)")
        details.append(f"Схожість звуків: {sound_score:.1f}%")
        
        if stress_similar:
            details.append("✓ Однакова кількість складів - подібний ритм")
        
        explanation = self._get_phonetic_explanation(final_score)
        
        return {
            'score': round(final_score, 1),
            'details': details,
            'explanation': explanation
        }
    
    def _count_syllables(self, text):
        """Підрахунок складів"""
        vowels = 'аеєиіїоуюя'
        return sum(1 for c in text.lower() if c in vowels)
    
    def _compare_sounds(self, text1, text2):
        """Порівняння схожості звуків"""
        similar_sounds = [
            ['б', 'п'], ['в', 'ф'], ['г', 'к', 'х'], ['д', 'т'],
            ['з', 'с'], ['ж', 'ш'], ['дз', 'ц'], ['дж', 'ч']
        ]
        
        def normalize(text):
            for group in similar_sounds:
                for sound in group:
                    text = text.replace(sound, group[0])
            return text
        
        norm1 = normalize(text1.lower())
        norm2 = normalize(text2.lower())
        
        return SequenceMatcher(None, norm1, norm2).ratio() * 100
    
    def _get_phonetic_explanation(self, score):
        """Пояснення фонетичної схожості"""
        if score > 80:
            return "**ВИСОКА фонетична схожість** - позначення звучать дуже подібно, пересічний споживач може їх сплутати при усному сприйнятті."
        elif score > 60:
            return "**СЕРЕДНЯ фонетична схожість** - позначення мають помітну звукову подібність, існує ризик плутанини."
        elif score > 40:
            return "**НИЗЬКА фонетична схожість** - позначення звучать по-різному, але мають деякі спільні звукові елементи."
        else:
            return "**ВІДСУТНЯ фонетична схожість** - позначення звучать суттєво по-різному."
    
    def _analyze_graphic(self, text1, text2):
        """П. 5.1: Графічна схожість"""
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()
        
        # Схожість довжини
        len_diff = abs(len(text1) - len(text2))
        len_score = 100 - (len_diff / max(len(text1), len(text2))) * 100
        
        # Схожість літер
        letter_score = SequenceMatcher(None, text1, text2).ratio() * 100
        
        # Спільні частини
        common = self._find_common_substring(text1, text2)
        common_score = (len(common) / max(len(text1), len(text2))) * 100
        
        # Візуальна схожість літер
        visual_score = self._compare_visual_letters(text1, text2)
        
        final_score = (len_score + letter_score + common_score + visual_score) / 4
        
        details = []
        details.append(f"Схожість довжини: {len_score:.1f}% ({len(text1)} vs {len(text2)} символів)")
        details.append(f"Схожість послідовності літер: {letter_score:.1f}%")
        if common:
            details.append(f"Спільна частина: '{common}' (довжина {len(common)})")
        details.append(f"Візуальна схожість літер: {visual_score:.1f}%")
        
        explanation = self._get_graphic_explanation(final_score)
        
        return {
            'score': round(final_score, 1),
            'details': details,
            'explanation': explanation
        }
    
    def _find_common_substring(self, text1, text2):
        """Найдовша спільна підстрока"""
        matcher = SequenceMatcher(None, text1, text2)
        match = matcher.find_longest_match(0, len(text1), 0, len(text2))
        return text1[match.a:match.a + match.size]
    
    def _compare_visual_letters(self, text1, text2):
        """Порівняння візуально схожих літер"""
        similar_letters = [
            ['о', '0', 'о'], ['і', 'i', 'l', '1'], ['а', 'a'],
            ['е', 'e'], ['р', 'p'], ['с', 'c'], ['х', 'x']
        ]
        
        def normalize(text):
            for group in similar_letters:
                for letter in group:
                    text = text.replace(letter, group[0])
            return text
        
        norm1 = normalize(text1.lower())
        norm2 = normalize(text2.lower())
        
        return SequenceMatcher(None, norm1, norm2).ratio() * 100
    
    def _get_graphic_explanation(self, score):
        """Пояснення графічної схожості"""
        if score > 80:
            return "**ВИСОКА графічна схожість** - позначення виглядають візуально дуже схожими, загальне зорове враження подібне."
        elif score > 60:
            return "**СЕРЕДНЯ графічна схожість** - позначення мають помітну візуальну подібність у написанні."
        elif score > 40:
            return "**НИЗЬКА графічна схожість** - позначення візуально відрізняються, але мають деякі спільні графічні елементи."
        else:
            return "**ВІДСУТНЯ графічна схожість** - позначення виглядають суттєво по-різному."
    
    def _analyze_semantic(self, text1, text2):
        """П. 5.1: Семантична схожість"""
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()
        
        # Повний збіг
        if text1 == text2:
            return {
                'score': 100.0,
                'details': ['Повний збіг значення'],
                'explanation': '**ТОТОЖНІ за змістом** - позначення мають ідентичне значення.'
            }
        
        # Часткове входження
        if text1 in text2 or text2 in text1:
            shorter = min(len(text1), len(text2))
            longer = max(len(text1), len(text2))
            score = (shorter / longer) * 100
            
            return {
                'score': round(score, 1),
                'details': [f'Одне позначення містить інше ({shorter}/{longer} символів)'],
                'explanation': f'**ВИСОКА семантична схожість** - одне позначення включає інше, що створює пряму асоціацію.'
            }
        
        # Спільний корінь
        root_score = self._compare_roots(text1, text2)
        
        details = [f'Схожість коренів слів: {root_score:.1f}%']
        
        # Перевірка синонімів/перекладів (спрощено)
        translation_similar = self._check_translations(text1, text2)
        if translation_similar:
            details.append('✓ Можливий переклад або синонім')
            root_score = max(root_score, 70)
        
        explanation = self._get_semantic_explanation(root_score)
        
        return {
            'score': round(root_score, 1),
            'details': details,
            'explanation': explanation
        }
    
    def _compare_roots(self, text1, text2):
        """Порівняння коренів"""
        root1 = text1[:min(4, len(text1))]
        root2 = text2[:min(4, len(text2))]
        return SequenceMatcher(None, root1, root2).ratio() * 100
    
    def _check_translations(self, text1, text2):
        """Перевірка на переклади (дуже спрощено)"""
        # Тут можна додати словник перекладів
        return False
    
    def _get_semantic_explanation(self, score):
        """Пояснення семантичної схожості"""
        if score > 80:
            return "**ВИСОКА семантична схожість** - позначення мають близьке або тотожне значення."
        elif score > 60:
            return "**СЕРЕДНЯ семантична схожість** - позначення пов'язані за змістом."
        elif score > 40:
            return "**НИЗЬКА семантична схожість** - деякий зв'язок за значенням."
        else:
            return "**ВІДСУТНЯ семантична схожість** - позначення мають різне значення."
    
    def _generate_similarity_conclusion(self, phonetic, graphic, semantic, overall):
        """Загальний висновок про схожість"""
        parts = []
        
        if phonetic['score'] > 70:
            parts.append("висока фонетична схожість")
        if graphic['score'] > 70:
            parts.append("висока графічна схожість")
        if semantic['score'] > 70:
            parts.append("висока семантична схожість")
        
        if overall > 70:
            conclusion = f"Позначення **СХОЖІ до ступеня змішування** ({overall:.1f}%). "
            if parts:
                conclusion += f"Виявлено: {', '.join(parts)}. "
            conclusion += "Пересічний споживач може прийняти одне позначення за інше або асоціювати їх зі спільним джерелом."
        elif overall > 50:
            conclusion = f"Позначення **МАЮТЬ СХОЖІСТЬ** ({overall:.1f}%), але не до критичного ступеня. Існує ризик асоціації, проте ймовірність прямого змішування нижча."
        else:
            conclusion = f"Позначення **МАЛО СХОЖІ** ({overall:.1f}%). Ризик змішування низький."
        
        return conclusion
    
    def _check_goods_relatedness(self, classes1, classes2):
        """П. 6: Перевірка спорідненості товарів/послуг"""
        set1 = self._parse_classes(classes1)
        set2 = self._parse_classes(classes2)
        
        # Пряме перетинання
        intersection = set1 & set2
        if intersection:
            return {
                'are_related': True,
                'degree': 'висока',
                'common_classes': sorted(list(intersection)),
                'explanation': f"**ТОВАРИ/ПОСЛУГИ СПОРІДНЕНІ** - прямий збіг класів МКТП: {', '.join(map(str, sorted(intersection)))}. Споживачі можуть сприйняти ці марки як такі, що походять з одного джерела."
            }
        
        # Перевірка споріднених груп
        related_groups = [
            {1, 2, 3, 4, 5},  # Хімія
            {9, 16, 35, 41, 42},  # IT та послуги
            {18, 25},  # Одяг
            {29, 30, 31, 32, 33},  # Харчові
            {6, 19, 37},  # Будматеріали
            {3, 5, 44},  # Краса та здоров'я
        ]
        
        for group in related_groups:
            if set1 & group and set2 & group:
                return {
                    'are_related': True,
                    'degree': 'середня',
                    'common_classes': [],
                    'explanation': f"**ТОВАРИ/ПОСЛУГИ СПОРІДНЕНІ** - класи належать до однієї споріднаної групи. Існує ризик асоціації через подібне призначення, канали збуту або коло споживачів."
                }
        
        return {
            'are_related': False,
            'degree': 'відсутня',
            'common_classes': [],
            'explanation': f"**ТОВАРИ/ПОСЛУГИ НЕ СПОРІДНЕНІ** - класи МКТП не перетинаються ({classes1} vs {classes2}). Різне призначення, канали збуту та коло споживачів."
        }
    
    def _parse_classes(self, classes_str):
        """Парсинг класів МКТП"""
        return set(int(c.strip()) for c in re.findall(r'\d+', str(classes_str)))
    
    def _determine_confusion_risk(self, analysis):
        """П. 9: Визначення ризику змішування"""
        identical = analysis['identical_test']['is_identical']
        similar = analysis['similarity_test']['is_confusingly_similar']
        related_goods = analysis['goods_relatedness']['are_related']
        
        reasoning = []
        risk_level = 'low'
        
        # Правило 1: Тотожність + споріднені товари
        if identical and related_goods:
            risk_level = 'critical'
            reasoning.append("⚠️ **КРИТИЧНИЙ РИЗИК ЗМІШУВАННЯ** (п.9 Критеріїв)")
            reasoning.append("• Позначення ТОТОЖНІ")
            reasoning.append("• Товари/послуги СПОРІДНЕНІ")
            reasoning.append("• **Висновок**: Ризик змішування ПРЕЗЮМУЄТЬСЯ. Висока ймовірність відмови в реєстрації.")
        
        # Правило 2: Схожість до ступеня змішування + споріднені товари
        elif similar and related_goods:
            risk_level = 'high'
            reasoning.append("⚠️ **ВИСОКИЙ РИЗИК ЗМІШУВАННЯ** (п.9 Критеріїв)")
            reasoning.append("• Позначення СХОЖІ до ступеня змішування")
            reasoning.append("• Товари/послуги СПОРІДНЕНІ")
            reasoning.append("• **Висновок**: Споживач може сплутати марки або асоціювати зі спільним джерелом. Ймовірність відмови в реєстрації висока.")
        
        # Правило 3: Схожість + різні товари
        elif similar and not related_goods:
            risk_level = 'medium'
            reasoning.append("⚠️ **СЕРЕДНІЙ РИЗИК**")
            reasoning.append("• Позначення СХОЖІ")
            reasoning.append("• Товари/послуги НЕ СПОРІДНЕНІ")
            reasoning.append("• **Висновок**: Ризик змішування знижений через різні сфери використання, але асоціація можлива.")
        
        # Правило 4: Тотожність + різні товари
        elif identical and not related_goods:
            risk_level = 'medium'
            reasoning.append("⚠️ **СЕРЕДНІЙ РИЗИК**")
            reasoning.append("• Позначення ТОТОЖНІ")
            reasoning.append("• Товари/послуги НЕ СПОРІДНЕНІ")
            reasoning.append("• **Висновок**: Тотожність створює ризик асоціації навіть для неспоріднених товарів.")
        
        # Правило 5: Низька схожість
        else:
            risk_level = 'low'
            reasoning.append("✓ **НИЗЬКИЙ РИЗИК ЗМІШУВАННЯ**")
            reasoning.append("• Позначення НЕ є схожими до ступеня змішування")
            reasoning.append("• **Висновок**: Ризик відмови в реєстрації мінімальний.")
        
        return {
            'level': risk_level,
            'reasoning': reasoning,
            'recommendation': self._get_recommendation(risk_level)
        }
    
    def _get_recommendation(self, risk_level):
        """Рекомендації залежно від ризику"""
        if risk_level == 'critical':
            return "🔴 **НЕ РЕКОМЕНДУЄТЬСЯ** подавати заявку. Майже гарантована відмова. Розгляньте зміну назви марки."
        elif risk_level == 'high':
            return "🟠 **ВИСОКИЙ РИЗИК**. Рекомендується консультація з патентним повіреним та підготовка аргументації щодо відмінностей."
        elif risk_level == 'medium':
            return "🟡 **ПОМІРНИЙ РИЗИК**. Можна подавати заявку, але варто підготувати обґрунтування відмінностей."
        else:
            return "🟢 **МОЖНА ПОДАВАТИ**. Ризик відмови низький."

@app.route('/api/analyze', methods=['POST'])
def analyze_trademarks():
    """Головний ендпоінт для аналізу"""
    try:
        data = request.json
        
        # Дані користувача
        your_trademark = {
            'name': data.get('name'),
            'classes': data.get('classes'),
            'description': data.get('description', ''),
            'type': data.get('type', 'словесне')
        }
        
        # Посилання на конкуруючі марки
        competitor_urls = data.get('competitor_urls', [])
        
        if not your_trademark['name'] or not your_trademark['classes']:
            return jsonify({'error': 'Необхідно вказати назву та класи'}), 400
        
        if not competitor_urls:
            return jsonify({'error': 'Необхідно вказати хоча б одне посилання на конкуруючу марку'}), 400
        
        # Парсимо конкуруючі марки
        parser = UkrPatentParser()
        analyzer = DetailedSimilarityAnalyzer()
        
        results = []
        for url in competitor_urls:
            # Парсимо сторінку марки
            competitor_data = parser.parse_trademark_page(url)
            
            if not competitor_data:
                results.append({
                    'url': url,
                    'error': 'Не вдалося завантажити дані з цього посилання'
                })
                continue
            
            # Детальний аналіз
            analysis = analyzer.analyze_full_comparison(your_trademark, competitor_data)
            results.append(analysis)
        
        # Загальна оцінка ризику
        risk_scores = {
            'critical': 100,
            'high': 75,
            'medium': 50,
            'low': 25
        }
        
        max_risk = 0
        for result in results:
            if 'confusion_risk' in result and result['confusion_risk']:
                risk_level = result['confusion_risk']['level']
                max_risk = max(max_risk, risk_scores.get(risk_level, 0))
        
        success_probability = 100 - max_risk
        
        if max_risk >= 75:
            overall_risk = 'high'
        elif max_risk >= 50:
            overall_risk = 'medium'
        else:
            overall_risk = 'low'
        
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
