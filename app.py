from flask import Flask, request, render_template, jsonify
import os
import requests
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# Initialize Twilio client
twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

def generate_response(user_input):
    """Generate educational response using OpenRouter"""
    try:
        # Detect subject and language
        twi_mode = "twi:" in user_input.lower()
        subject = "general"
        
        for sub in ["math", "science", "english"]:
            if f"{sub}:" in user_input.lower():
                subject = sub
                user_input = user_input.split(":")[1].strip()
                break
        
        prompt = f"Explain {user_input} for Ghanaian high school students. Subject: {subject}"
        if twi_mode:
            prompt = f"Translate to Twi (keep technical terms in English): {user_input}"

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
            json={
                "model": "mistralai/mistral-7b-instruct",
                "messages": [{"role": "user", "content": prompt}]
            }
        )
        return response.json()["choices"][0]["message"]["content"]
    
    except Exception as e:
        return f"Error: {str(e)}"

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
    user_input = request.form.get("Body", "").strip()
    from_number = request.form.get("From", "")
    
    response = generate_response(user_input)
    
    # Send reply via WhatsApp/SMS
    twilio_client.messages.create(
        body=response,
        from_=os.getenv("TWILIO_PHONE"),
        to=from_number
    )
    
    return "", 200

if __name__ == "__main__":
    app.run(port=5000)