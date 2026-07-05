from flask import Flask, render_template, request, jsonify
import cognee
import asyncio
import sys
from datetime import datetime
import re
import random
import os
import requests
import tempfile

# ============================================
# FIX: Set writable database paths for Render
# ============================================
if os.environ.get('RENDER'):
    # Use /tmp which is writable on Render
    db_dir = '/tmp/cognee_data'
    os.makedirs(db_dir, exist_ok=True)
    os.environ['COGNEE_SYSTEM_ROOT'] = db_dir
    os.environ['DATA_ROOT'] = db_dir
    print(f"✅ Using writable database: {db_dir}")
else:
    print("✅ Cognee using local SQLite database")

app = Flask(__name__)
app.secret_key = os.urandom(24)

SESSION_ID = datetime.now().strftime("day_%Y_%m_%d")

# ============================================
# LLM CONFIGURATION - USING GROQ
# ============================================
GROQ_API_KEY = os.environ.get("LLM_API_KEY")
if not GROQ_API_KEY:
    print("⚠️ WARNING: LLM_API_KEY environment variable not set!")

GROQ_ENDPOINT = "https://api.groq.com/openai/v1"
GROQ_DIRECT_MODEL = "llama-3.3-70b-versatile"

os.environ["OPENAI_API_KEY"] = GROQ_API_KEY or ""
os.environ["OPENAI_API_BASE"] = GROQ_ENDPOINT
os.environ["LLM_MODEL"] = "groq/llama-3.3-70b-versatile"

# ============================================
# FIX: Windows Async + Flask Debug Mode
# ============================================
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

def run_async(coro):
    """Run async coroutine with proper event loop handling."""
    return asyncio.run(coro)

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
    """Detect if user is asking about their OWN name ONLY."""
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
                                if ' ' not in name:
                                    return name
                                return name.split()[0]
            except Exception as e:
                print(f"[get_name] Error: {e}")
            return None

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
# OTHER API ROUTES
# ============================================

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

@app.route('/api/emotion', methods=['POST'])
def emotion():
    return jsonify({
        "status": "success",
        "emotions": {"sadness": 10, "frustration": 10, "anxiety": 10, "determination": 40, "happiness": 30},
        "similar_memory": ""
    })

@app.route('/api/insights', methods=['GET'])
def api_insights():
    return jsonify({
        "score": 65,
        "resilience": 70,
        "growth": 60,
        "consistency": 55,
        "positivity": 75,
        "dna": {"resilience": 70, "creativity": 65, "patience": 60, "determination": 80, "empathy": 55},
        "predictions": [{"text": "You're on a growth path", "confidence": 70}]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)