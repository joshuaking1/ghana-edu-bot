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
    """Generate pharmaceutical response using OpenRouter"""
    try:
        # Detect query type and language
        twi_mode = "twi:" in user_input.lower()
        query_type = "general"
        
        # Pharmaceutical query types
        for q_type in ["drug:", "moa:", "interaction:", "therapy:"]:
            if q_type in user_input.lower():
                query_type = q_type.replace(":", "")
                user_input = user_input.split(":")[1].strip()
                break
        
        # Base prompt for pharmaceutical responses
        prompt = f"""As a clinical pharmacy expert, provide detailed information about:
        {user_input}

        Include these sections when applicable:
        - Generic and brand names
        - Mechanism of action
        - Therapeutic indications
        - Dosage forms and regimens
        - Common side effects
        - Important drug interactions
        - Monitoring parameters
        - Special population considerations

        Use professional medical terminology but explain concepts clearly for pharmacy students."""

        # Add query type specific instructions
        if query_type == "moa":
            prompt += "\nFocus specifically on the pharmacological mechanism of action."
        elif query_type == "interaction":
            prompt += "\nFocus specifically on drug-drug and drug-food interactions."
        elif query_type == "therapy":
            prompt += "\nFocus on therapeutic uses and clinical applications."

        # Handle Twi translations
        if twi_mode:
            prompt = f"""Translate this pharmaceutical information to Twi while keeping:
            - Technical medical terms in English
            - Drug names in English
            - Measurements in English
            Original text: {user_input}"""

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
            json={
                "model": "mistralai/mistral-7b-instruct",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3  # More factual responses
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