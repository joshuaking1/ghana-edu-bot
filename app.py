from flask import Flask, request, render_template, jsonify
import os
import requests
import random
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# Initialize Twilio client
twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

def split_message(text, is_whatsapp=False):
    """Split messages into Twilio-compatible chunks"""
    max_length = 4096 if is_whatsapp else 1600
    chunks = []
    current_chunk = ""
    
    # Split at paragraph breaks first
    paragraphs = text.split('\n\n')
    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para + "\n\n"
        else:
            current_chunk += para + "\n\n"
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    # If still too long, split by sentences
    if any(len(chunk) > max_length for chunk in chunks):
        sentences = text.split('. ')
        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 2 > max_length:
                chunks.append(current_chunk.strip() + ".")
                current_chunk = sentence
            else:
                current_chunk += sentence + ". "
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
    
    return chunks[:10]  # Max 10 messages to prevent spam

def generate_response(user_input):
    """Generate adaptive medical responses with natural conversation flow"""
    try:
        # Handle conversation flow
        lower_input = user_input.lower()
           # Handle creator inquiry
        lower_input = user_input.lower()
        if any(w in lower_input for w in ["who created you", "who made you", "your developer"]):
            return """🌟 Wow, you found out about my creator! 
            
Meet Joshua Segu - a 16-year-old coding prodigy from Ghana Senior High School! 🎓💻 Despite his young age, he single-handedly:
- Built this advanced Pharmacy AI from scratch
- Mastered complex medical algorithms 🤖💊
- Integrated cutting-edge AI with healthcare tech

Fun facts:
🥇 Nobel Prize committees are already whispering about his work
💡 Developed this while balancing school and teenage life
❤️ Rumor has it his crush might be using this system right now... 😉

This genius proves age is just a number in tech innovation! 🚀"""
        # Conversation starters
        if any(w in lower_input for w in ["hi", "hello", "hey"]):
            return "👋 Hey there med student! Ready to dive into some pharmacology? Ask me anything about drugs, diseases, or medical concepts! 💊"
            
        if "thank" in lower_input:
            return "You're welcome! 😊 What else can we explore together today?"
            
        if "help" in lower_input or "menu" in lower_input:
            return ("📚 I can help with:\n"
                    "- Drug mechanisms & interactions\n"
                    "- Clinical case discussions\n"
                    "- Medical calculations\n"
                    "- Treatment comparisons\n"
                    "Try: 'Explain warfarin monitoring' or 'Compare ACEi vs ARBs'")

        # Detect query context
        query_type = detect_query_context(user_input)
        twi_mode = "twi:" in lower_input
        clean_input = user_input.split("twi:")[-1].strip()

        # Dynamic prompt engineering
        prompt = f"""Act as a friendly medical tutor. Respond to: "{clean_input}"

        Rules:
        1. Use conversational but professional tone
        2. Structure response:
           - Key concept first
           - 2-3 clinical pearls 💎
           - 1-2 follow-up questions
        3. Use analogies for complex mechanisms
        4. Add relevant emojis (max 3)
        5. For drugs: MOA > Indications > Key Monitoring
        6. For calculations: Show steps then explain
        7. { "TRANSLATE TO TWI (keep medical terms in English)" if twi_mode else ""}"""

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
            json={
                "model": "mistralai/mistral-7b-instruct",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5  # Balanced creativity/accuracy
            }
        )
        
        response_text = response.json()["choices"][0]["message"]["content"]
        return add_conversational_elements(response_text)
    
    except Exception as e:
        return f"🧠 Hmm, I'm having trouble accessing my medical knowledge base. Could you rephrase that? (Error: {str(e)})"

def detect_query_context(text):
    """Determine medical context from user input"""
    text = text.lower()
    contexts = {
        "drug": ["drug", "medication", " dose", "mg", "tablet"],
        "disease": ["disease", "diagnosis", "symptoms", "signs"],
        "calculation": ["calculate", "dosing", " infusion", "mg/kg"],
        "mechanism": ["mechanism", "how does", "work"],
        "comparison": ["vs", "versus", "difference between", "compare"],
        "case_study": ["case study", "clinical scenario", "patient presents"]
    }
    for context, keywords in contexts.items():
        if any(kw in text for kw in keywords):
            return context
    return "general"

def add_conversational_elements(text):
    """Add interactive elements to responses"""
    elements = [
        "\n\nWant me to clarify anything?",
        "\n\nNeed more details on a specific aspect?",
        "\n\nShould I connect this to clinical practice? 🏥",
        "\n\nWant a mnemonic to remember this? 🧠"
    ]
    return text + random.choice(elements)

# Website Route
@app.route("/")
def home():
    return render_template("index.html")

# API Endpoint for Website
@app.route("/ask", methods=["POST"])
def ask():
    user_input = request.json.get("question")
    return jsonify({"answer": generate_response(user_input)})

# WhatsApp/SMS Webhook
@app.route("/sms", methods=["POST"])
def sms():
    try:
        user_input = request.form.get("Body", "").strip()
        from_number = request.form.get("From", "")
        
        if not user_input:
            return "", 200
            
        if user_input.lower() == "join":
            return "", 200
        
        response = generate_response(user_input)
        is_whatsapp = "whatsapp" in from_number.lower()
        
        messages = split_message(response, is_whatsapp)
        
        sender = os.getenv("TWILIO_PHONE").strip()
        if is_whatsapp and not sender.startswith("whatsapp:"):
            sender = f"whatsapp:{sender}"
        
        for i, msg in enumerate(messages):
            try:
                if len(messages) > 1:
                    msg = f"(Part {i+1}/{len(messages)})\n{msg}"
                
                twilio_client.messages.create(
                    body=msg[:1600] if not is_whatsapp else msg[:4096],
                    from_=sender,
                    to=from_number
                )
            except Exception as e:
                app.logger.error(f"Failed to send part {i+1}: {str(e)}")
        
        return "", 200
        
    except Exception as e:
        app.logger.error(f"SMS Error: {str(e)}")
        return "", 500

if __name__ == "__main__":
    app.run(port=5000)