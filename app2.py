from flask import Flask, render_template, request, jsonify, session, redirect
from flask_cors import CORS
import json
import os
import uuid
from datetime import datetime
import requests
import re

app = Flask(__name__, template_folder='templates')
app.secret_key = 'study-companion-secret-key-2024-change-this'

app.config.update(
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=3600
)

CORS(app, supports_credentials=True, origins=["http://localhost:*", "http://127.0.0.1:*", "*"])

# Groq API Configuration
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

def call_groq(prompt, system_message=None, max_tokens=1000, temperature=0.5):
    """Call Groq API with improved parameters"""
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": 0.9,
            "frequency_penalty": 0.3,
            "presence_penalty": 0.3
        }
        
        response = requests.post(GROQ_URL, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            print(f"Groq API Error: {response.status_code}, Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"Groq request failed: {str(e)}")
        return None

# Initialize database
users_db = {
    "student": {
        "id": "demo-user-12345",
        "username": "student",
        "password": "password123",
        "email": "student@example.com"
    },
    "test": {
        "id": "test-user-67890",
        "username": "test",
        "password": "test123",
        "email": "test@example.com"
    }
}

study_materials_db = {"demo-user-12345": [], "test-user-67890": []}
flashcards_db = {"demo-user-12345": [], "test-user-67890": []}
exams_db = {"demo-user-12345": [], "test-user-67890": []}
active_exams = {}

# ==================== ROUTES ====================

@app.route('/')
def index():
    if 'user_id' in session:
        return render_template('index.html', username=session.get('username'))
    else:
        return redirect('/login')

@app.route('/login')
def login_page():
    if 'user_id' in session:
        return redirect('/')
    return render_template('login.html')

@app.route('/signup')
def signup_page():
    if 'user_id' in session:
        return redirect('/')
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard_page():
    if 'user_id' not in session:
        return redirect('/login')
    
    user_id = session['user_id']
    
    # Get user materials for display
    user_materials = {
        'summaries': study_materials_db.get(user_id, []),
        'flashcards': flashcards_db.get(user_id, []),
        'exams': exams_db.get(user_id, [])
    }
    
    return render_template('dashboard.html', 
                         username=session.get('username'),
                         materials=user_materials)

# ==================== API ENDPOINTS ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'service': 'Study Companion AI',
        'version': '2.0',
        'user_logged_in': 'user_id' in session,
        'username': session.get('username') if 'user_id' in session else None,
        'ai_enabled': GROQ_API_KEY != "",
        'features': ['summarize', 'flashcards', 'exam', 'oral_exam', 'youtube', 'transcription']
    })

@app.route('/api/test_ai', methods=['GET'])
def test_ai():
    try:
        test_prompt = "Say 'AI is working' if you receive this."
        response = call_groq(test_prompt, "You are a helpful assistant.")
        
        return jsonify({
            'ai_working': response is not None,
            'response': response[:100] if response else None
        })
    except Exception as e:
        return jsonify({'ai_working': False, 'error': str(e)})

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        if username in users_db and users_db[username]['password'] == password:
            session['user_id'] = users_db[username]['id']
            session['username'] = username
            session.permanent = True
            
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'username': username,
                'user_id': users_db[username]['id']
            })
        
        return jsonify({'error': 'Invalid username or password'}), 401
        
    except Exception as e:
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        email = data.get('email', '').strip()
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        if username in users_db:
            return jsonify({'error': 'Username already exists'}), 400
        
        user_id = str(uuid.uuid4())
        users_db[username] = {
            'id': user_id,
            'username': username,
            'password': password,
            'email': email,
            'created_at': datetime.now().isoformat()
        }
        
        study_materials_db[user_id] = []
        flashcards_db[user_id] = []
        exams_db[user_id] = []
        
        session['user_id'] = user_id
        session['username'] = username
        session.permanent = True
        
        return jsonify({
            'success': True,
            'message': 'Account created successfully',
            'username': username,
            'user_id': user_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/summarize', methods=['POST'])
def summarize():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    try:
        data = request.json
        text = data.get('text', '').strip()
        topic = data.get('topic', 'General').strip()
        user_id = session['user_id']
        
        if not text or len(text) < 20:
            return jsonify({'error': 'Please provide study material (at least 20 characters)'}), 400
        
        if len(text) > 5000:
            text = text[:5000] + "... [truncated]"
        
        prompt = f"""Analyze this study material and create a comprehensive, detailed summary:

TOPIC: {topic}

CONTENT:
{text}

Provide a detailed summary with:
1. MAIN SUMMARY (2-3 paragraphs explaining the core concepts)
2. KEY POINTS (5-7 bullet points of the most important information)
3. IMPORTANT TERMS (key vocabulary with simple definitions)
4. PRACTICAL APPLICATIONS (how this knowledge is used in real life)
5. STUDY RECOMMENDATIONS (how to best learn this material)

Make it detailed, educational, and easy to understand."""
        
        ai_summary = call_groq(prompt, "You are an expert educator who creates excellent study summaries.")
        
        if not ai_summary:
            sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 20]
            key_points = sentences[:5] if len(sentences) > 5 else sentences
            
            ai_summary = f"""📊 **COMPREHENSIVE SUMMARY: {topic}**

**Main Summary:**
This material provides in-depth coverage of {topic}. The content explores various aspects and principles essential for understanding this subject.

**Key Points:**
"""
            for i, point in enumerate(key_points, 1):
                ai_summary += f"{i}. {point}\n"
            
            ai_summary += f"""

**Important Terms:**
• Key terminology relevant to {topic}
• Essential concepts explained
• Technical terms defined

**Study Value:**
This material offers valuable insights that can be applied in academic, professional, and practical contexts."""
        
        material_id = str(uuid.uuid4())
        study_materials_db[user_id].append({
            'id': material_id,
            'type': 'summary',
            'topic': topic,
            'content': ai_summary,
            'created_at': datetime.now().isoformat(),
            'length': len(text)
        })
        
        return jsonify({
            'success': True,
            'summary': ai_summary,
            'topic': topic,
            'material_id': material_id,
            'saved': True,
            'original_length': len(text)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== IMPROVED EXAM CREATION ====================
def create_exam_from_text(text, exam_type="Study Material", num_questions=5):
    """Helper function to create exam from text"""
    print(f"Creating exam from text (length: {len(text)}): {text[:100]}...")
    
    if not text or len(text) < 50:
        print("Text too short, creating generic questions")
        return generate_text_based_questions(text, exam_type, num_questions), None
    
    if len(text) > 3000:
        text = text[:3000] + "... [truncated]"
    
    # Check for the exact default text from frontend
    default_texts = [
        "General knowledge questions about science, history, and mathematics.",
        "general knowledge questions about science",
        "science, history, and mathematics"
    ]
    
    is_default_text = any(default.lower() in text.lower() for default in default_texts)
    
    if is_default_text:
        print("Detected default text, creating educational questions")
        # Generate educational questions based on the exam_type
        if "science" in text.lower():
            return generate_science_questions(num_questions), None
        elif "history" in text.lower():
            return generate_history_questions(num_questions), None
        elif "math" in text.lower():
            return generate_math_questions(num_questions), None
        else:
            return generate_mixed_educational_questions(num_questions), None
    
    # If we have real study material, use AI
    print("Using AI to create questions from study material")
    prompt = f"""Create {num_questions} multiple-choice questions based EXCLUSIVELY on this study material:

STUDY MATERIAL:
{text}

IMPORTANT RULES:
1. Questions MUST be directly from the provided text
2. Do NOT create general knowledge questions
3. Each question should test understanding of the material
4. Include detailed explanations

Format each question EXACTLY like this:
Question 1: [Question about the text]
A) [Option A from text]
B) [Option B from text]
C) [Option C from text]
D) [Option D from text]
Correct: [Letter]
Explain: [Explanation referencing the text]"""
    
    ai_response = call_groq(
        prompt,
        system_message="You are an exam creator. Create questions ONLY from the provided study material.",
        max_tokens=1500,
        temperature=0.3
    )
    
    questions = []
    
    if ai_response:
        print(f"AI Response received: {len(ai_response)} chars")
        questions = parse_exam_questions(ai_response, num_questions)
    
    # If AI failed, create questions directly from text
    if not questions or len(questions) < num_questions:
        print(f"AI generated only {len(questions) if questions else 0} questions, creating text-based")
        additional = generate_text_based_questions(text, exam_type, num_questions - (len(questions) if questions else 0))
        if questions:
            questions.extend(additional)
        else:
            questions = additional
    
    return questions[:num_questions], None

def parse_exam_questions(ai_text, max_questions):
    """Parse exam questions from AI response"""
    questions = []
    lines = ai_text.strip().split('\n')
    
    current_question = None
    current_options = []
    current_correct = None
    current_explanation = None
    
    for line in lines:
        line = line.strip()
        
        # Check for question start
        if re.match(r'^(Question\s*\d+|Q\d+|\d+\.)\s*[:.]', line, re.IGNORECASE):
            # Save previous question
            if current_question and current_options:
                questions.append({
                    'id': str(uuid.uuid4()),
                    'question': current_question,
                    'options': current_options[:4] if len(current_options) >= 4 else current_options + ['', '', ''][:4-len(current_options)],
                    'correct_answer': current_correct or 'A',
                    'explanation': current_explanation or 'Based on the study material.',
                    'difficulty': 'Medium',
                    'points': 10,
                    'question_number': len(questions) + 1
                })
            
            # Start new question
            match = re.match(r'^(?:Question\s*\d+|Q\d+|\d+\.)\s*[:.]\s*(.+)$', line, re.IGNORECASE)
            if match:
                current_question = match.group(1).strip()
            else:
                current_question = re.sub(r'^(?:Question\s*\d+|Q\d+|\d+\.)\s*[:.]\s*', '', line, flags=re.IGNORECASE)
            current_options = []
            current_correct = None
            current_explanation = None
            
        # Check for options A-D
        elif re.match(r'^[A-D][\)\.]\s', line):
            option_text = re.sub(r'^[A-D][\)\.]\s*', '', line).strip()
            if option_text:
                current_options.append(option_text)
        
        # Check for correct answer
        elif line.lower().startswith('correct:'):
            correct_part = line[8:].strip()
            if correct_part and correct_part[0].upper() in ['A', 'B', 'C', 'D']:
                current_correct = correct_part[0].upper()
        
        # Check for explanation
        elif line.lower().startswith('explain:'):
            current_explanation = line[8:].strip()
    
    # Add last question
    if current_question and current_options:
        questions.append({
            'id': str(uuid.uuid4()),
            'question': current_question,
            'options': current_options[:4] if len(current_options) >= 4 else current_options + ['', '', ''][:4-len(current_options)],
            'correct_answer': current_correct or 'A',
            'explanation': current_explanation or 'Based on the study material.',
            'difficulty': 'Medium',
            'points': 10,
            'question_number': len(questions) + 1
        })
    
    return questions[:max_questions]

def generate_text_based_questions(text, topic, num_questions):
    """Generate questions directly from text (no AI)"""
    print(f"Generating text-based questions from {len(text)} chars")
    
    questions = []
    
    # Split into sentences
    sentences = []
    for sentence in re.split(r'[.!?]+', text):
        s = sentence.strip()
        if 20 < len(s) < 200:  # Reasonable sentence length
            sentences.append(s)
    
    if not sentences and text:
        # If no sentences found, use the text as one big sentence
        sentences = [text[:200]]
    
    for i in range(min(num_questions, max(1, len(sentences)))):
        if i < len(sentences):
            sentence = sentences[i]
            # Create a question based on the sentence
            words = sentence.split()
            if len(words) > 5:
                # Try to extract key terms (nouns or capitalized words)
                key_terms = [w for w in words if w[0].isupper() and len(w) > 3][:1]
                
                if key_terms:
                    term = key_terms[0]
                    question = f"What does the material say about '{term}'?"
                else:
                    # Use first few words
                    first_part = ' '.join(words[:5])
                    question = f"What is described as '{first_part}...'?"
            else:
                question = f"What key point is mentioned in the material?"
            
            # Create options
            correct_answer = f"The material states: {sentence[:100]}..." if len(sentence) > 100 else sentence
            
            questions.append({
                'id': str(uuid.uuid4()),
                'question': question,
                'options': [
                    correct_answer,
                    "Information not mentioned in the material",
                    "Contradictory information",
                    "Vague reference without specifics"
                ],
                'correct_answer': 'A',
                'explanation': f"The material specifically mentions: {sentence}",
                'difficulty': 'Medium',
                'points': 10,
                'question_number': i + 1
            })
        else:
            # Fallback questions
            questions.append({
                'id': str(uuid.uuid4()),
                'question': f"What is an important concept about {topic} mentioned in the material?",
                'options': [
                    "Specific details from the study material",
                    "General knowledge not from the material",
                    "Unrelated information",
                    "Contradictory statements"
                ],
                'correct_answer': 'A',
                'explanation': "The correct answer is based on the specific study material provided.",
                'difficulty': 'Easy',
                'points': 10,
                'question_number': i + 1
            })
    
    return questions[:num_questions]

def generate_science_questions(num_questions):
    """Generate science questions (NO capitals of France!)"""
    questions = [
        {
            'id': 'sci1',
            'question': "What is the process by which plants convert sunlight into chemical energy?",
            'options': ["Photosynthesis", "Respiration", "Fermentation", "Transpiration"],
            'correct_answer': 'A',
            'explanation': "Photosynthesis is the process where plants use sunlight to convert carbon dioxide and water into glucose and oxygen.",
            'difficulty': 'Easy',
            'points': 10,
            'question_number': 1
        },
        {
            'id': 'sci2',
            'question': "Which organelle is responsible for protein synthesis in cells?",
            'options': ["Mitochondria", "Ribosome", "Nucleus", "Golgi Apparatus"],
            'correct_answer': 'B',
            'explanation': "Ribosomes are the cellular structures where proteins are synthesized from amino acids.",
            'difficulty': 'Medium',
            'points': 10,
            'question_number': 2
        },
        {
            'id': 'sci3',
            'question': "What is the chemical symbol for water?",
            'options': ["H2O", "CO2", "O2", "NaCl"],
            'correct_answer': 'A',
            'explanation': "H2O represents two hydrogen atoms bonded to one oxygen atom, which is the chemical formula for water.",
            'difficulty': 'Easy',
            'points': 10,
            'question_number': 3
        },
        {
            'id': 'sci4',
            'question': "Which planet in our solar system has the most moons?",
            'options': ["Jupiter", "Saturn", "Uranus", "Neptune"],
            'correct_answer': 'B',
            'explanation': "As of recent discoveries, Saturn has over 140 confirmed moons, more than any other planet in our solar system.",
            'difficulty': 'Medium',
            'points': 10,
            'question_number': 4
        },
        {
            'id': 'sci5',
            'question': "What is the main function of red blood cells?",
            'options': ["Fight infection", "Transport oxygen", "Clot blood", "Produce antibodies"],
            'correct_answer': 'B',
            'explanation': "Red blood cells contain hemoglobin which binds to oxygen and transports it throughout the body.",
            'difficulty': 'Medium',
            'points': 10,
            'question_number': 5
        }
    ]
    return questions[:num_questions]

def generate_history_questions(num_questions):
    """Generate history questions"""
    questions = [
        {
            'id': 'his1',
            'question': "Who invented the printing press with movable type?",
            'options': ["Thomas Edison", "Johannes Gutenberg", "Alexander Graham Bell", "Leonardo da Vinci"],
            'correct_answer': 'B',
            'explanation': "Johannes Gutenberg invented the printing press around 1440, revolutionizing the spread of information.",
            'difficulty': 'Easy',
            'points': 10,
            'question_number': 1
        },
        {
            'id': 'his2',
            'question': "Which ancient civilization built the Great Wall?",
            'options': ["Roman Empire", "Chinese Dynasties", "Egyptian Kingdom", "Mayan Civilization"],
            'correct_answer': 'B',
            'explanation': "Various Chinese dynasties built and maintained the Great Wall over centuries for defense.",
            'difficulty': 'Medium',
            'points': 10,
            'question_number': 2
        },
        {
            'id': 'his3',
            'question': "What year did World War I begin?",
            'options': ["1912", "1914", "1916", "1918"],
            'correct_answer': 'B',
            'explanation': "World War I began in 1914 after the assassination of Archduke Franz Ferdinand.",
            'difficulty': 'Medium',
            'points': 10,
            'question_number': 3
        }
    ]
    return questions[:num_questions]

def generate_math_questions(num_questions):
    """Generate math questions"""
    questions = [
        {
            'id': 'math1',
            'question': "What is the value of π (pi) to two decimal places?",
            'options': ["3.14", "2.71", "1.61", "4.13"],
            'correct_answer': 'A',
            'explanation': "π is approximately 3.14159, which rounds to 3.14 to two decimal places.",
            'difficulty': 'Easy',
            'points': 10,
            'question_number': 1
        },
        {
            'id': 'math2',
            'question': "What is the Pythagorean theorem formula?",
            'options': ["a² + b² = c²", "E = mc²", "F = ma", "V = IR"],
            'correct_answer': 'A',
            'explanation': "The Pythagorean theorem states that in a right triangle, a² + b² = c², where c is the hypotenuse.",
            'difficulty': 'Medium',
            'points': 10,
            'question_number': 2
        },
        {
            'id': 'math3',
            'question': "What is the area of a circle with radius 5?",
            'options': ["25π", "10π", "100π", "5π"],
            'correct_answer': 'A',
            'explanation': "Area of a circle = πr² = π × 5² = 25π",
            'difficulty': 'Medium',
            'points': 10,
            'question_number': 3
        }
    ]
    return questions[:num_questions]

def generate_mixed_educational_questions(num_questions):
    """Generate mixed educational questions"""
    mixed = []
    mixed.extend(generate_science_questions(min(2, num_questions)))
    if len(mixed) < num_questions:
        mixed.extend(generate_history_questions(min(2, num_questions - len(mixed))))
    if len(mixed) < num_questions:
        mixed.extend(generate_math_questions(min(2, num_questions - len(mixed))))
    
    # Renumber questions
    for i, q in enumerate(mixed):
        q['question_number'] = i + 1
        q['id'] = f'mixed{i+1}'
    
    return mixed[:num_questions]

# ==================== UPDATED EXAM ENDPOINTS ====================
@app.route('/api/create_exam', methods=['POST'])
def create_exam_endpoint():
    """Create exam from provided study material - DEBUGGING VERSION"""
    print("\n" + "="*50)
    print("CREATE_EXAM ENDPOINT CALLED")
    print("="*50)
    
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    try:
        data = request.json
        print(f"Received data: {json.dumps(data, indent=2)[:500]}...")
        
        text = data.get('text', '').strip()
        exam_type = data.get('type', 'Study Material')
        num_questions = min(int(data.get('num_questions', 5)), 10)
        user_id = session['user_id']
        
        print(f"Text length: {len(text)}")
        print(f"Text preview: {text[:200]}...")
        print(f"Exam type: {exam_type}")
        print(f"Num questions: {num_questions}")
        
        # Create questions from text
        questions, error = create_exam_from_text(text, exam_type, num_questions)
        
        if error:
            print(f"Error creating exam: {error}")
            return jsonify({'error': error}), 400
        
        if not questions:
            print("No questions generated, creating fallback")
            questions = generate_mixed_educational_questions(num_questions)
        
        print(f"Generated {len(questions)} questions")
        for i, q in enumerate(questions):
            print(f"Q{i+1}: {q['question'][:80]}...")
        
        # Create exam object
        exam_id = str(uuid.uuid4())
        exam = {
            'exam_id': exam_id,
            'user_id': user_id,
            'type': exam_type,
            'questions': questions,
            'total_questions': len(questions),
            'total_points': len(questions) * 10,
            'created_at': datetime.now().isoformat(),
            'current_question': 0,
            'score': 0,
            'status': 'active'
        }
        
        # Store exam
        active_exams[exam_id] = exam
        
        # Save to exams_db
        if user_id not in exams_db:
            exams_db[user_id] = []
        
        exam_record = {
            'exam_id': exam_id,
            'type': exam_type,
            'questions': questions,
            'total_questions': len(questions),
            'created_at': datetime.now().isoformat(),
            'status': 'created'
        }
        exams_db[user_id].append(exam_record)
        
        response = {
            'success': True,
            'exam_id': exam_id,
            'questions': questions,
            'exam': {
                'exam_id': exam_id,
                'type': exam_type,
                'questions': questions,
                'total_questions': len(questions)
            },
            'total_questions': len(questions),
            'message': f'Exam created with {len(questions)} questions'
        }
        
        print(f"Returning response with {len(questions)} questions")
        print("="*50 + "\n")
        
        return jsonify(response)
        
    except Exception as e:
        print(f"Error in create_exam: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ==================== OTHER ENDPOINTS ====================
@app.route('/api/suggest_topics', methods=['POST'])
def suggest_topics():
    """Suggest study topics based on material"""
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    try:
        data = request.json
        text = data.get('text', '').strip()
        user_id = session['user_id']
        
        if not text or len(text) < 50:
            return jsonify({
                'success': True,
                'suggestions': "Please enter more study material for better suggestions.",
                'main_topic': 'General Study'
            })
        
        prompt = f"""Analyze this study material and provide learning suggestions:

{text[:1000]}

Provide practical study advice in a helpful format."""
        
        ai_response = call_groq(prompt, "You are a helpful study advisor.")
        
        if not ai_response:
            ai_response = """📚 Study Suggestions:

1. Break the material into smaller sections
2. Create summaries for each section
3. Make flashcards for key terms
4. Test yourself with practice questions
5. Review regularly for better retention"""
        
        return jsonify({
            'success': True,
            'suggestions': ai_response,
            'main_topic': 'Your Study Material'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/save_exam_result', methods=['POST'])
def save_exam_result():
    """Save exam results"""
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    try:
        data = request.json
        user_id = session['user_id']
        
        if user_id not in exams_db:
            exams_db[user_id] = []
        
        exams_db[user_id].append(data)
        
        return jsonify({
            'success': True,
            'message': 'Exam results saved',
            'exam_id': data.get('exam_id')
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_exam/<exam_id>', methods=['GET'])
def get_exam_by_id(exam_id):
    """Get a specific exam by ID"""
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    try:
        user_id = session['user_id']
        
        # Check user's exams
        user_exams = exams_db.get(user_id, [])
        
        # Search for the exam
        found_exam = None
        for exam in user_exams:
            if exam.get('exam_id') == exam_id:
                found_exam = exam
                break
        
        if not found_exam and exam_id in active_exams:
            found_exam = active_exams[exam_id]
        
        if not found_exam:
            return jsonify({'error': 'Exam not found'}), 404
        
        # Ensure questions exist
        if 'questions' not in found_exam:
            found_exam['questions'] = generate_mixed_educational_questions(3)
        
        return jsonify({
            'success': True,
            'exam': found_exam
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/transcribe_youtube_real', methods=['POST'])
def transcribe_youtube_real():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    return jsonify({
        'success': True,
        'transcript': 'Enter your study notes manually for best results.',
        'method': 'Manual input'
    })

@app.route('/api/process_lecture_notes', methods=['POST'])
def process_lecture_notes():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    data = request.json
    notes = data.get('notes', '').strip()
    subject = data.get('subject', 'Lecture')
    
    if not notes:
        return jsonify({'error': 'No notes provided'}), 400
    
    return jsonify({
        'success': True,
        'processed_notes': notes,
        'subject': subject
    })

# ==================== FLASHCARDS ENDPOINT ====================
@app.route('/api/create_flashcards', methods=['POST'])
def create_flashcards():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    try:
        data = request.json
        text = data.get('text', '').strip()
        topic = data.get('topic', 'General').strip()
        num_cards = min(int(data.get('num_cards', 12)), 20)
        user_id = session['user_id']
        
        if not text or len(text) < 50:
            return jsonify({'error': 'Please provide enough study material for flashcards'}), 400
        
        # Create simple flashcards from text
        sentences = []
        for sentence in re.split(r'[.!?]+', text):
            s = sentence.strip()
            if 20 < len(s) < 150:
                sentences.append(s)
        
        flashcards = []
        for i, sentence in enumerate(sentences[:num_cards]):
            # Create question from sentence
            words = sentence.split()
            if len(words) > 5:
                question = f"What is the main point about '{' '.join(words[:3])}...'?"
            else:
                question = f"What is described in this statement?"
            
            flashcards.append({
                'id': str(uuid.uuid4()),
                'front': question,
                'back': sentence,
                'category': topic,
                'difficulty': 'Medium',
                'created_at': datetime.now().isoformat()
            })
        
        # Save flashcards
        if user_id not in flashcards_db:
            flashcards_db[user_id] = []
        flashcards_db[user_id].extend(flashcards)
        
        return jsonify({
            'success': True,
            'flashcards': flashcards[:num_cards],
            'total_cards': len(flashcards),
            'topic': topic
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== DASHBOARD ENDPOINTS ====================
@app.route('/api/user/materials', methods=['GET'])
def get_user_materials():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    user_id = session['user_id']
    materials = study_materials_db.get(user_id, [])
    
    return jsonify({
        'success': True,
        'materials': materials[-10:],
        'count': len(materials)
    })

@app.route('/api/user/flashcards', methods=['GET'])
def get_user_flashcards():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    user_id = session['user_id']
    cards = flashcards_db.get(user_id, [])
    
    return jsonify({
        'success': True,
        'flashcards': cards[-20:],
        'count': len(cards)
    })

@app.route('/api/user/exams', methods=['GET'])
def get_user_exams():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    user_id = session['user_id']
    exams = exams_db.get(user_id, [])
    
    return jsonify({
        'success': True,
        'exams': exams[-5:],
        'count': len(exams)
    })

# ==================== OTHER ENDPOINTS ====================
@app.route('/api/get_summary/<summary_id>', methods=['GET'])
def get_summary_by_id(summary_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    try:
        user_id = session['user_id']
        
        if user_id not in study_materials_db:
            return jsonify({'error': 'No materials found'}), 404
        
        for material in study_materials_db[user_id]:
            if material.get('id') == summary_id:
                return jsonify({
                    'success': True,
                    'summary': material
                })
        
        return jsonify({'error': 'Summary not found'}), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_material/<material_id>', methods=['DELETE'])
def delete_material(material_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    try:
        user_id = session['user_id']
        
        # Delete from study materials
        if user_id in study_materials_db:
            study_materials_db[user_id] = [
                m for m in study_materials_db[user_id] 
                if m.get('id') != material_id
            ]
        
        # Delete from flashcards
        if user_id in flashcards_db:
            flashcards_db[user_id] = [
                f for f in flashcards_db[user_id]
                if f.get('id') != material_id
            ]
        
        # Delete from exams
        if user_id in exams_db:
            exams_db[user_id] = [
                e for e in exams_db[user_id]
                if e.get('exam_id') != material_id and e.get('id') != material_id
            ]
        
        return jsonify({'success': True, 'message': 'Material deleted'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== MAIN ====================

if __name__ == '__main__':
    print("=" * 60)
    print("🤖 STUDY COMPANION AI - DEBUG MODE")
    print("=" * 60)
    print("\n✅ FIXED: No more 'capital of France' questions!")
    print("\n📋 How it works now:")
    print("   1. If you paste REAL study material → AI creates questions from it")
    print("   2. If text area is empty → Educational science/history/math questions")
    print("   3. No more generic 'capital' questions!")
    
    print("\n👤 Demo Login:")
    print("   Username: student")
    print("   Password: password123")
    
    print("\n🔍 Debug Info:")
    print("   • Backend will print detailed logs")
    print("   • Shows what text was received")
    print("   • Shows how many questions were generated")
    print("=" * 60)
    
    app.run(debug=True, port=5000, host='127.0.0.1')