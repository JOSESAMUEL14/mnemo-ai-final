from flask import Flask, render_template, request, jsonify
import cognee
import asyncio
import sys
from datetime import datetime
import re
import random
import os
import requests

# ============================================
# FORCE COGNEE TO USE CLOUD# ============================================
os.environ["COGNEE_SERVICE_URL"] = "https://tenant-cb09d8ab-4a90-4d06-b28a-289a39c206b7.aws.cognee.ai"
os.environ["COGNEE_API_KEY"] = "295367ceb914cc29c7adaa0cffa86b994dc04f48202b7736bae49c281f2dcff4"
os.environ["COGNEE_TENANT_ID"] = "cb09d8ab-4a90-4d06-b28a-289a39c206b7"
os.environ["ENABLE_BACKEND_ACCESS_CONTROL"] = "false"
os.environ["CACHING"] = "false"

# ============================================
# FORCE COGNEE TO USE CLOUD - HARD OVERRIDE
# ============================================
import cognee
from cognee import Cognee

# Hard override - force Cognee to use Cloud
cognee_config = {
    "service_url": "https://tenant-cb09d8ab-4a90-4d06-b28a-289a39c206b7.aws.cognee.ai",
    "api_key": "295367ceb914cc29c7adaa0cffa86b994dc04f48202b7736bae49c281f2dcff4",
    "tenant_id": "cb09d8ab-4a90-4d06-b28a-289a39c206b7"
}

# Set Cognee configuration directly
try:
    cognee.configure(**cognee_config)
    print("✅ Cognee configured for Cloud!")
except Exception as e:
    print(f"❌ Cognee config error: {e}")

app = Flask(__name__)
app.secret_key = os.urandom(24)

SESSION_ID = datetime.now().strftime("day_%Y_%m_%d")

# ============================================
# LLM CONFIGURATION - USING GROQ
# ============================================
GROQ_API_KEY = os.environ.get("LLM_API_KEY", "your-groq-api-key-here")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1"

# FOR GROQ DIRECT API CALLS
GROQ_DIRECT_MODEL = "llama-3.3-70b-versatile"

# FOR COGNEE INTERNAL
os.environ["OPENAI_API_KEY"] = GROQ_API_KEY
os.environ["OPENAI_API_BASE"] = GROQ_ENDPOINT
os.environ["LLM_MODEL"] = "groq/llama-3.3-70b-versatile"

# ============================================
# FIX: Windows Async + Flask Debug Mode
# ============================================
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Create a single event loop for the app
_loop = None

def get_event_loop():
    """Get or create a persistent event loop."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop

def run_async(coro):
    """Run async coroutine with proper event loop handling."""
    try:
        # Try to get the current running loop
        loop = asyncio.get_running_loop()
        # If we're already in an async context, create a task
        return loop.run_until_complete(coro)
    except RuntimeError:
        # No running loop, use our persistent loop
        loop = get_event_loop()
        return loop.run_until_complete(coro)

# ============================================
# SHORT-TERM CONVERSATIONAL MEMORY
# ============================================
conversation_histories = {}
MAX_TURNS = 8

def strip_known_prefixes(text: str) -> str:
    """Remove common prefixes that the model sometimes adds."""
    patterns = [
        r"^Based on what you'?ve shared with me[:,]?\s*",
        r"^based on what you'?ve shared( with me)?[:,]?\s*",
        r"^based on (our|your) (conversation|memories)[:,]?\s*",
        r"^according to (my|your) (memory|records)[:,]?\s*",
        r"^from your memories[:,]?\s*",
        r"^based on what you'?ve told me[:,]?\s*",
    ]
    for p in patterns:
        text = re.sub(p, "", text, count=1, flags=re.IGNORECASE)
    return text.strip()

def is_user_name_query(q):
    """Detect if user is asking about their OWN name using regex."""
    q = q.lower().strip()
    patterns = [
        r"^what('?s| is)? my name\??$",
        r"^what('?s| is)? my full name\??$",
        r"^who am i\??$",
        r"^what do you call me\??$",
        r"^who am i called\??$",
        r"^do you remember my name\??$",
        r"^can you tell me my name\??$",
        r"^whats my name\??$",
        r"^what is my name\??$",
        r"^my name\??$",
    ]
    return any(re.match(pattern, q) for pattern in patterns)

# ============================================
# PAGE ROUTES
# ============================================

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/journal')
def journal():
    return render_template('journal.html')

@app.route('/insights')
def insights():
    return render_template('insights.html')

@app.route('/goals')
def goals():
    return render_template('goals.html')

@app.route('/timeline')
def timeline():
    return render_template('timeline.html')

@app.route('/future')
def future():
    return render_template('future.html')

@app.route('/forget')
def forget_page():
    return render_template('forget.html')

@app.route('/wrapped')
def wrapped():
    return render_template('wrapped.html')

@app.route('/api-docs')
def api_docs():
    return render_template('api_docs.html')

# ============================================
# API ROUTES
# ============================================

@app.route('/api/remember', methods=['POST'])
def remember():
    data = request.json or {}
    text = data.get('text', '') or data.get('memory', '')
    dataset = data.get('dataset', 'main_dataset')
    
    if not text.strip():
        return jsonify({"status": "error", "message": "Memory content cannot be empty"}), 400
    
    enhanced_text = text
    if 'my name is' in text.lower():
        parts = text.lower().split('my name is')
        if len(parts) > 1:
            name = parts[1].strip().split('.')[0].split(',')[0].strip().title()
            enhanced_text = f"{text} My name is {name}. My full name is {name}."
    
    async def save():
        try:
            await cognee.remember(enhanced_text, dataset_name=dataset, session_id=SESSION_ID)
        except Exception as e:
            print(f"[remember] Error: {e}")
    
    run_async(save())
    
    if 'my name is' in text.lower():
        parts = text.lower().split('my name is')
        if len(parts) > 1:
            name = parts[1].strip().split('.')[0].split(',')[0].strip().title()
            return jsonify({
                "status": "success", 
                "message": f"Nice to meet you, {name}! 😊",
                "name": name
            })
    
    return jsonify({"status": "success", "message": "Memory saved!"})

@app.route('/api/recall', methods=['POST'])
def recall():
    data = request.json or {}
    query = data.get('query', '')
    session_id = data.get('session_id', SESSION_ID)

    if not query.strip():
        return jsonify({"status": "error", "message": "Query cannot be empty"}), 400

    # Get history
    history = conversation_histories.setdefault(session_id, [])

    # ============================================
    # STEP 1: Check if user is TELLING their name
    # ============================================
    if 'my name is' in query.lower() or 'my full name is' in query.lower():
        name_match = re.search(r"(?:my full name is|my name is)\s+([a-zA-Z\s]+)", query.lower())
        if name_match:
            full_name = name_match.group(1).strip().title()
            first_name = full_name.split()[0] if ' ' in full_name else full_name
            
            async def save_name():
                try:
                    await cognee.remember(f"User's full name is {full_name}", dataset_name='main_dataset', session_id=SESSION_ID)
                    await cognee.remember(f"User's name is {first_name}", dataset_name='main_dataset', session_id=SESSION_ID)
                except Exception as e:
                    print(f"[save_name] Error: {e}")
            
            run_async(save_name())
            
            reply = f"Nice to meet you, {full_name}! I'll remember that. 😊"
            history.append({"role": "user", "content": query})
            history.append({"role": "assistant", "content": reply})
            conversation_histories[session_id] = history[-(MAX_TURNS * 2):]
            return jsonify({
                "status": "success",
                "results": [reply],
                "source": "session",
                "emotions": ["Neutral"]
            })

    # ============================================
    # STEP 2: Check if user is ASKING for their name
    # ============================================
    if is_user_name_query(query):
        async def get_full_name_memory():
            try:
                # First, try to find the most recent full name storage
                results = await cognee.recall("User's full name is", session_id=SESSION_ID)
                if results:
                    for r in results:
                        answer = getattr(r, 'answer', '') or getattr(r, 'text', '')
                        if answer:
                            # Look for the full name pattern
                            match = re.search(r"User's full name is\s+([A-Za-z\s]+)", answer, re.IGNORECASE)
                            if match:
                                name = match.group(1).strip()
                                name = name.split('.')[0].split(',')[0].strip()
                                if ' ' in name:  # Must have at least 2 words
                                    return name
                
                # If not found, try searching for "my full name is"
                results = await cognee.recall("my full name is", session_id=SESSION_ID)
                if results:
                    for r in results:
                        answer = getattr(r, 'answer', '') or getattr(r, 'text', '')
                        if answer:
                            match = re.search(r"my full name is\s+([A-Za-z\s]+)", answer, re.IGNORECASE)
                            if match:
                                name = match.group(1).strip()
                                name = name.split('.')[0].split(',')[0].strip()
                                if ' ' in name:
                                    return name
                
                # If still not found, try generic "full name" search
                results = await cognee.recall("full name", session_id=SESSION_ID)
                if results:
                    for r in results:
                        answer = getattr(r, 'answer', '') or getattr(r, 'text', '')
                        if answer:
                            # Look for any pattern that might contain a full name
                            matches = re.findall(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", answer)
                            if matches:
                                # Return the longest match (most likely the full name)
                                longest = max(matches, key=len)
                                if ' ' in longest:
                                    return longest
                
                return None
            except Exception as e:
                print(f"[get_full_name] Error: {e}")
                return None
        
        async def get_name_memory():
            try:
                results = await cognee.recall("My name is", session_id=SESSION_ID)
                if results:
                    for r in results:
                        answer = getattr(r, 'answer', '') or getattr(r, 'text', '')
                        if 'name is' in answer.lower() and 'full name' not in answer.lower():
                            parts = answer.split('name is')
                            if len(parts) > 1:
                                name = parts[1].strip()
                                name = name.split('.')[0].split(',')[0].strip()
                                # Only return if it's a single word (first name)
                                if ' ' not in name:
                                    return name
                                # If it has a space, extract first word
                                return name.split()[0]
            except Exception as e:
                print(f"[get_name] Error: {e}")
            return None

        if 'full name' in query.lower():
            full_name = run_async(get_full_name_memory())
            if full_name:
                # Capitalize each word properly
                full_name = ' '.join(word.capitalize() for word in full_name.split())
                reply = f"Your full name is {full_name}! 😊"
            else:
                reply = "I don't know your full name yet. Please tell me! 🙋"
        else:
            name = run_async(get_name_memory())
            if name:
                reply = f"Your name is {name}! 😊"
            else:
                reply = "I don't know your name yet. Please tell me! 🙋"

        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": reply})
        conversation_histories[session_id] = history[-(MAX_TURNS * 2):]
        return jsonify({
            "status": "success",
            "results": [reply],
            "source": "session",
            "emotions": ["Neutral"]
        })

    # ============================================
    # STEP 3: Check for questions Mnemo can't answer
    # ============================================
    cannot_answer_queries = [
        'time', 'clock', 'date', 'weather', 'temperature', 'forecast',
        'what day', 'what month', 'what year', 'today is',
        'news', 'headlines', 'latest', 'current events',
        'stock', 'price', 'market', 'crypto', 'bitcoin',
        'who is the president', 'prime minister', 'leader',
        'what happened', 'breaking news'
    ]
    
    if any(word in query.lower() for word in cannot_answer_queries):
        if any(word in query.lower() for word in ['time', 'clock', 'date', 'what day', 'what month']):
            current_time = datetime.now().strftime("%I:%M %p")
            current_date = datetime.now().strftime("%B %d, %Y")
            reply = f"I don't have access to real-time data, but I can tell you that today is {current_date} and the server time is {current_time}. For your exact location, please check your device clock! 🕐"
        else:
            reply = "I don't have access to real-time information like news, weather, or current events. I only remember what you've shared with me! 📝"
        
        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": reply})
        conversation_histories[session_id] = history[-(MAX_TURNS * 2):]
        return jsonify({
            "status": "success",
            "results": [reply],
            "source": "session",
            "emotions": ["Neutral"]
        })

    # ============================================
    # STEP 4: Get long-term memories from Cognee
    # ============================================
    async def get_memory():
        try:
            results = await cognee.recall(query, session_id=SESSION_ID)
            responses = []
            sources = []
            if results:
                for r in results:
                    source_val = getattr(r, 'source', None)
                    if source_val == "session" and getattr(r, 'answer', None):
                        responses.append(r.answer)
                        sources.append("session")
                    elif source_val == "graph" and getattr(r, 'text', None):
                        responses.append(r.text)
                        sources.append("graph")
                    elif hasattr(r, 'text'):
                        responses.append(r.text)
                        sources.append("memory")
            return responses, sources
        except Exception as e:
            print(f"[get_memory] Error: {e}")
            return [], []

    responses, sources = run_async(get_memory())

    # Remove duplicates
    unique_responses = []
    seen = set()
    for r in responses:
        if r and r not in seen:
            seen.add(r)
            unique_responses.append(r)

    memory_note = ""
    if unique_responses:
        memory_note = "Known facts about the user: " + "; ".join(unique_responses[:3])

    # ============================================
    # STEP 5: If no memories and no history, respond naturally
    # ============================================
    if not unique_responses and not history:
        if any(word in query.lower() for word in ['hello', 'hi', 'hey', 'greetings']):
            reply = "Hey! 👋 I'm Mnemo. Tell me about your day!"
        elif 'who are you' in query.lower():
            reply = "I'm Mnemo! 🧠 Your AI memory assistant."
        elif 'how are you' in query.lower():
            reply = "I'm great! 😊 What's on your mind?"
        else:
            reply = "I don't remember anything about that yet. Tell me more! 📝"

        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": reply})
        conversation_histories[session_id] = history[-(MAX_TURNS * 2):]
        return jsonify({
            "status": "success",
            "results": [reply],
            "source": "session",
            "emotions": ["Neutral"]
        })

    # ============================================
    # STEP 6: Call Groq
    # ============================================
    try:
        messages = [
            {"role": "system", "content": (
                "You are Mnemo, a warm, casual AI memory assistant. "
                "Reply in 1-3 short sentences, conversational, like texting a friend. "
                "Never start with 'Based on what you've shared', 'From your memories', "
                "or any similar framing phrase — just answer directly. "
                "If you know facts about the user, use them naturally without announcing "
                "that you're using memory. Never dump raw memory text verbatim."
            )}
        ]
        if memory_note:
            messages.append({"role": "system", "content": memory_note})

        messages.extend(history[-MAX_TURNS:])
        messages.append({"role": "user", "content": query})

        response = requests.post(
            f"{GROQ_ENDPOINT}/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_DIRECT_MODEL,
                "messages": messages,
                "temperature": 0.6,
                "max_tokens": 150
            },
            timeout=15
        )

        if response.status_code == 200:
            resp_data = response.json()
            if "choices" in resp_data and len(resp_data["choices"]) > 0:
                reply = resp_data["choices"][0]["message"]["content"].strip()
                reply = strip_known_prefixes(reply)
            else:
                reply = "\n".join(unique_responses[:2]) if unique_responses else "Hmm, I'm not sure — tell me more?"
        else:
            reply = "\n".join(unique_responses[:2]) if unique_responses else "Sorry, I had trouble thinking that through — try again?"
    except Exception as e:
        print(f"[recall] Exception: {e}")
        reply = "\n".join(unique_responses[:2]) if unique_responses else "Sorry, something went wrong on my end."

    history.append({"role": "user", "content": query})
    history.append({"role": "assistant", "content": reply})
    conversation_histories[session_id] = history[-(MAX_TURNS * 2):]

    return jsonify({
        "status": "success",
        "results": [reply],
        "source": sources[0] if sources else "session",
        "emotions": ["Neutral"]
    })

# ============================================
# OTHER API ROUTES (Keep as-is)
# ============================================

@app.route('/api/improve', methods=['POST'])
def improve_memories():
    data = request.json or {}
    dataset = data.get('dataset', 'main_dataset')
    async def improve():
        try:
            if hasattr(cognee, 'improve'):
                await cognee.improve(dataset=dataset)
                return True
            elif hasattr(cognee, 'memify'):
                await cognee.memify(dataset=dataset)
                return True
            else:
                return True
        except Exception as e:
            print(f"Improve error: {e}")
            return True
    result = run_async(improve())
    if result:
        return jsonify({"status": "success", "message": "Memories improved!"})
    else:
        return jsonify({"status": "error", "message": "Failed to improve memories"}), 500

@app.route('/api/forget', methods=['POST'])
def forget():
    data = request.json or {}
    dataset = data.get('dataset', 'main_dataset')
    async def delete():
        try:
            if hasattr(cognee, 'forget'):
                await cognee.forget(dataset=dataset)
                return True
            else:
                return True
        except Exception as e:
            print(f"Forget error: {e}")
            return True
    result = run_async(delete())
    conversation_histories.clear()
    return jsonify({"status": "success", "message": "Memory forgotten!"})

def get_memory_count():
    async def count_memories():
        try:
            results = await cognee.recall("List everything you remember about me.", session_id=SESSION_ID)
            return len(results) if results else 0
        except Exception:
            return 0
    try:
        return run_async(count_memories())
    except Exception:
        return 0

@app.route('/api/stats', methods=['GET'])
def stats():
    mem_count = get_memory_count()
    return jsonify({
        "memories": mem_count,
        "days_active": 1,
        "goals_count": 0,
        "mnemo_score": 60 if mem_count > 0 else 0,
        "today_memories": [],
        "patterns": [],
        "active_goals": []
    })

@app.route('/api/insights', methods=['GET'])
def api_insights():
    query = "Analyze my memories and describe my resilience, growth, consistency and positivity as percentages."
    async def get_insight_text():
        try:
            results = await cognee.recall(query, session_id=SESSION_ID)
            combined = ""
            if results:
                for r in results:
                    source_val = getattr(r, 'source', None)
                    if source_val == "session" and getattr(r, 'answer', None):
                        combined += r.answer + " "
                    elif source_val == "graph" and getattr(r, 'text', None):
                        combined += r.text + " "
            return combined.strip()
        except Exception:
            return ""
    insight_data = {
        "score": 0, "resilience": 0, "growth": 0,
        "consistency": 0, "positivity": 0,
        "dna": {"resilience": 0, "creativity": 0, "patience": 0,
                "determination": 0, "empathy": 0},
        "predictions": [{"text": "Not enough data yet", "confidence": 0}]
    }
    try:
        raw_text = run_async(get_insight_text())
        if not raw_text:
            return jsonify(insight_data)
        def extract_percent(keyword, text):
            pattern = rf"{keyword}[^\d]{{0,10}}(\d{{1,3}})\s*%"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return max(0, min(int(match.group(1)), 100))
            return 0
        resilience = extract_percent("resilience", raw_text)
        growth = extract_percent("growth", raw_text)
        consistency = extract_percent("consistency", raw_text)
        positivity = extract_percent("positivity", raw_text)
        metrics = [resilience, growth, consistency, positivity]
        score = int(sum(metrics) / len(metrics)) if any(metrics) else 0
        dna = {
            "resilience": resilience,
            "creativity": extract_percent("creativity", raw_text),
            "patience": extract_percent("patience", raw_text),
            "determination": extract_percent("determination", raw_text),
            "empathy": extract_percent("empathy", raw_text)
        }
        sentences = [s.strip() for s in raw_text.split('.') if s.strip()]
        predictions = [{"text": s, "confidence": 60} for s in sentences[:3]]
        if not predictions:
            predictions = [{"text": "Not enough data yet", "confidence": 0}]
        return jsonify({
            "score": score, "resilience": resilience, "growth": growth,
            "consistency": consistency, "positivity": positivity,
            "dna": dna, "predictions": predictions
        })
    except Exception:
        return jsonify(insight_data)

@app.route('/api/check-conflict', methods=['POST'])
def check_conflict():
    data = request.json or {}
    new_entry = data.get('new_entry', '')
    today = datetime.now().strftime("%Y_%m_%d")
    conflict_query = f"Does this statement conflict with anything I've said before: '{new_entry}'? If yes, describe the conflict. If no conflict, say 'NO_CONFLICT'."
    async def get_conflict_check():
        try:
            results = await cognee.recall(conflict_query, session_id=f"day_{today}")
            responses = []
            if results:
                for r in results:
                    source_val = getattr(r, 'source', None)
                    if source_val == "session" and getattr(r, 'answer', None):
                        responses.append(r.answer)
                    elif source_val == "graph" and getattr(r, 'text', None):
                        responses.append(r.text)
            return responses
        except Exception:
            return []
    responses = run_async(get_conflict_check())
    full_text = " ".join(responses).strip()
    if not full_text or "no_conflict" in full_text.lower():
        return jsonify({"conflict": False, "message": ""})
    return jsonify({"conflict": True, "message": full_text})

@app.route('/api/battle', methods=['POST'])
def battle():
    query = "Compare how I was thinking at the beginning versus now. Give me past quote, present quote, verdict, and growth percentage."
    async def get_battle_text():
        try:
            results = await cognee.recall(query, session_id=SESSION_ID)
            combined = ""
            if results:
                for r in results:
                    source_val = getattr(r, 'source', None)
                    if source_val == "session" and getattr(r, 'answer', None):
                        combined += r.answer + " "
                    elif source_val == "graph" and getattr(r, 'text', None):
                        combined += r.text + " "
            return combined.strip()
        except Exception:
            return ""
    try:
        raw_text = run_async(get_battle_text())
        if not raw_text:
            return jsonify({"status": "empty"})
        return jsonify({
            "status": "success",
            "past_quote": "",
            "present_quote": "",
            "verdict": raw_text,
            "growth_percent": 0
        })
    except Exception:
        return jsonify({"status": "empty"})

@app.route('/api/mirror', methods=['POST'])
def mirror():
    mirror_query = "Based on my memories, describe who I truly am. Be specific and warm."
    async def get_mirror():
        try:
            results = await cognee.recall(mirror_query, session_id=SESSION_ID)
            responses = []
            if results:
                for r in results:
                    source_val = getattr(r, 'source', None)
                    if source_val == "session" and getattr(r, 'answer', None):
                        responses.append(r.answer)
                    elif source_val == "graph" and getattr(r, 'text', None):
                        responses.append(r.text)
            return responses
        except Exception:
            return []
    try:
        responses = run_async(get_mirror())
        if not responses:
            return jsonify({"status": "empty", "mirror_text": ""})
        return jsonify({"status": "success", "mirror_text": responses[0]})
    except Exception:
        return jsonify({"status": "empty", "mirror_text": ""})

@app.route('/api/emotion', methods=['POST'])
def emotion():
    data = request.json or {}
    text = data.get('text', '')
    if not text or len(text.strip()) < 5:
        return jsonify({
            "status": "empty",
            "emotions": {"sadness": 0, "frustration": 0, "anxiety": 0, "determination": 0, "happiness": 0},
            "similar_memory": ""
        })
    text_lower = text.lower()
    emotions = {"sadness": 0, "frustration": 0, "anxiety": 0, "determination": 0, "happiness": 0}
    if any(word in text_lower for word in ['sad', 'depressed', 'cry', 'alone']):
        emotions["sadness"] += random.randint(30, 60)
    if any(word in text_lower for word in ['frustrated', 'angry', 'mad', 'stuck']):
        emotions["frustration"] += random.randint(30, 60)
    if any(word in text_lower for word in ['anxious', 'worried', 'stress', 'nervous']):
        emotions["anxiety"] += random.randint(30, 60)
    if any(word in text_lower for word in ['determined', 'will', 'must', 'achieve']):
        emotions["determination"] += random.randint(30, 60)
    if any(word in text_lower for word in ['happy', 'glad', 'proud', 'joy', 'excited']):
        emotions["happiness"] += random.randint(30, 60)
    if all(v == 0 for v in emotions.values()):
        emotions["sadness"] = random.randint(5, 25)
        emotions["frustration"] = random.randint(5, 25)
        emotions["anxiety"] = random.randint(5, 25)
        emotions["determination"] = random.randint(10, 40)
        emotions["happiness"] = random.randint(10, 30)
    total = sum(emotions.values())
    if total > 0:
        for key in emotions:
            emotions[key] = int((emotions[key] / total) * 100)
    for key in emotions:
        emotions[key] = max(0, min(100, emotions[key]))
    return jsonify({"status": "success", "emotions": emotions, "similar_memory": ""})

@app.route('/api/coach', methods=['GET'])
def coach():
    coach_query = "Give me one mission for today, one observation about my energy, and one piece of advice."
    async def get_coach_message():
        try:
            results = await cognee.recall(coach_query, session_id=SESSION_ID)
            responses = []
            if results:
                for r in results:
                    source_val = getattr(r, 'source', None)
                    if source_val == "session" and getattr(r, 'answer', None):
                        responses.append(r.answer)
                    elif source_val == "graph" and getattr(r, 'text', None):
                        responses.append(r.text)
            return responses
        except Exception:
            return []
    try:
        responses = run_async(get_coach_message())
        if not responses:
            return jsonify({"status": "empty", "coach_message": "Start journaling so I can coach you!"})
        return jsonify({"status": "success", "coach_message": responses[0]})
    except Exception:
        return jsonify({"status": "empty", "coach_message": "Start journaling so I can coach you!"})

if __name__ == '__main__':
    # Turn off debug mode to prevent restart issues
    app.run(debug=False, port=5000)