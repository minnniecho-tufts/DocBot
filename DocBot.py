import os
import json
import requests
from flask import Flask, request, jsonify , Response
from llmproxy import generate
import re


app = Flask(__name__)

# JSON file to store user sessions
SESSION_FILE = "session_store.json"

### --- SESSION MANAGEMENT FUNCTIONS --- ###
def load_sessions():
    """Load stored sessions from a JSON file."""
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return {}  
    return {}

def save_sessions(session_dict):
    """Save sessions to a JSON file."""
    with open(SESSION_FILE, "w") as file:
        json.dump(session_dict, file, indent=4)


# Load sessions when the app starts
session_dict = load_sessions()
def first_interaction(message, user):
    questions = {
        "condition": "🩺 What condition do you have? (Type II Diabetes, Crohn’s disease, or both)",
        "age": "🎂 How old are you?",
        "gender": "⚧️ What's your gender?",
        "weight": "⚖️ What's your weight (in kg)?",
        "medications": "💊 What medications are you currently taking?",
        "emergency_contact": "📞 Who should we contact in case of emergency? (Name + Phone)",
        "news_pref": "📰 What kind of weekly health updates would you like?\nOptions: Instagram Reel 📱, TikTok 🎵, or Research News 🧪"
    }

    stage = session_dict[user].get("onboarding_stage", "condition")

    if stage == "condition":
        session_dict[user]["condition"] = message
        session_dict[user]["onboarding_stage"] = "age"
        return {"text": questions["age"]}

    elif stage == "age":
        session_dict[user]["age"] = message
        session_dict[user]["onboarding_stage"] = "gender"
        return {"text": questions["weight"]}

    elif stage == "weight":
        session_dict[user]["weight"] = message
        session_dict[user]["onboarding_stage"] = "medications"
        return {"text": questions["medications"]}
    
    elif stage == "medications":
        # Split input by comma and strip whitespace
        session_dict[user]["medications"] = [med.strip() for med in message.split(",")]
        session_dict[user]["onboarding_stage"] = "emergency_contact"
        return {"text": questions["emergency_contact"]}


    elif stage == "emergency_contact":
        session_dict[user]["emergency_contact"] = message
        session_dict[user]["onboarding_stage"] = "news_pref"
        return {"text": questions["news_pref"]}

    elif stage == "news_pref":
        session_dict[user]["news_pref"] = [pref.strip() for pref in message.split(",")]
        session_dict[user]["onboarding_stage"] = "done"
        return {"text": "✅ Onboarding complete! You're all set. You can now do daily check-ins or request help anytime."}

    else:
        llm_daily(message, user, session_dict)


def llm_daily(message, user, session_dict):
    
    for key, value in session_dict[user].items():
        print(f"{key}: {value}")
    
    return {"text": "IN LLM DAILY"}

### --- FLASK ROUTE TO HANDLE USER REQUESTS --- ###
# """Handles user messages and manages session storage."""
@app.route('/query', methods=['POST'])
def main():
    data = request.get_json()
    message = data.get("text", "").strip()
    user = data.get("user_name", "Unknown")

    # Load sessions at the beginning of each request
    session_dict = load_sessions()
    
    print("Current session dict:", session_dict)
    print("Current user:", user)

    # Initialize user session if it doesn't exist
    if user not in session_dict or "restart" in message.lower():
        print("new user", user)
        session_dict[user] = {
            "session_id": f"{user}-session",
            "onboarding_stage": "condition",
            "condition": "",
            "age": 0,
            "weight": 0,
            "medications": [],
            "emergency_contact": "",
            "news_pref": ""
        }
        save_sessions(session_dict)  # Save immediately after creating new session
        #return jsonify({"text": questions["condition"]})

    if session_dict[user]["onboarding_stage"] != "done":
        response = first_interaction(message, user)
    else:
        response = llm_daily(message, user, session_dict)
    
    # Save session data at the end of the request
    save_sessions(session_dict)
    return jsonify(response)


### --- RUN THE FLASK APP --- ###
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)