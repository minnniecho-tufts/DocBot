import os
import json
import requests
from flask import Flask, request, jsonify, Response
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
global session_dict
session_dict = load_sessions()

### --- ONBOARDING FUNCTION --- ###
def first_interaction(message, user):
    print("MY MES" + message)
    questions = {
        "condition": "🏪 What condition do you have? (Type II Diabetes, Crohn’s disease, or both)",
        "age": "👋 Hi, I'm DocBot — your health assistant!\n"
                "I'll help you track symptoms, remind you about meds 💊, and send you health tips 📰.\n\n"
                "Let’s start with a few quick questions.\n 🎂 How old are you?",
        "weight": "⚖️ What's your weight (in kg)?",
        "medications": "💊 What medications are you currently taking?",
        "emergency_contact": "📱 Who should we contact in case of emergency? [email]",
        "news_pref": "📰 What kind of weekly health updates would you like?\nOptions: Instagram Reel 📱, TikTok 🎵, or Research News 🧪"
    }

    stage = session_dict[user].get("onboarding_stage", "condition")

    if stage == "condition":
        session_dict[user]["condition"] = message
        session_dict[user]["onboarding_stage"] = "age"
        return {"text": questions["age"]}

    elif stage == "age":
        if not message.isdigit():
            return {"text": "❗ Please enter a valid age (a number)."}
        session_dict[user]["age"] = int(message)
        session_dict[user]["onboarding_stage"] = "weight"
        return {"text": questions["weight"]}

    elif stage == "weight":
        cleaned = message.lower().replace("kg", "").strip()

        if not cleaned.replace('.', '', 1).isdigit():
            return {"text": "❗ Please enter a valid weight (a number in kg)."}
        
        session_dict[user]["weight"] = cleaned
        session_dict[user]["onboarding_stage"] = "medications"
        return {"text": questions["medications"]}

    elif stage == "medications":
        session_dict[user]["medications"] = [med.strip() for med in message.split(",")]
        session_dict[user]["onboarding_stage"] = "emergency_contact"
        return {"text": questions["emergency_contact"]}

    elif stage == "emergency_contact":
        session_dict[user]["emergency_contact"] = message
        session_dict[user]["onboarding_stage"] = "news_pref"

        buttons = [
            {
                "type": "button",
                "text": "🎥 YouTube",
                "msg": "YouTube",
                "msg_in_chat_window": True,
                "msg_processing_type": "sendMessage",
                "button_id": "youtube_button"
            },
            {
                "type": "button",
                "text": "📸 IG Reel",
                "msg": "Instagram Reel",
                "msg_in_chat_window": True,
                "msg_processing_type": "sendMessage",
                "button_id": "insta_button"
            },
            {
                "type": "button",
                "text": "🎵 TikTok",
                "msg": "TikTok",
                "msg_in_chat_window": True,
                "msg_processing_type": "sendMessage",
                "button_id": "tiktok_button"
            },
            {
                "type": "button",
                "text": "🧪 Research",
                "msg": "Research News",
                "msg_in_chat_window": True,
                "msg_processing_type": "sendMessage",
                "button_id": "research_button"
            }
        ]

        return {
            "text": "📰 What kind of weekly health updates would you like?",
            "attachments": [
                {
                    "collapsed": False,
                    "color": "#e3e3e3",
                    "actions": buttons
                }
            ]
        }

    elif stage == "news_pref":
        valid_options = ["YouTube", "Instagram Reel", "TikTok", "Research News"]

        if message not in valid_options:
            return {"text": "Please click one of the buttons above to continue."}

        session_dict[user]["news_pref"] = [message]
        session_dict[user]["onboarding_stage"] = "condition1"


        buttons = [
            {
                "type": "button",
                "text": "Crohn's",
                "msg": "Crohn's",
                "msg_in_chat_window": True,
                "msg_processing_type": "sendMessage",
                "button_id": "choose_condition_crohns"
            },
            {
                "type": "button",
                "text": "Type II Diabetes",
                "msg": "Type II Diabetes",
                "msg_in_chat_window": True,
                "msg_processing_type": "sendMessage",
                "button_id": "choose_condition_diabetes"
            }
        ]
        return {
            "text": "🏪 What condition do you have?",
            "attachments": [
                {
                    "collapsed": False,
                    "color": "#e3e3e3",
                    "actions": buttons
                }
            ]
        }
    
    elif stage == "condition1":
        print(message)
        valid_conditions = ["Crohn's", "Type II Diabetes"]

        if message not in valid_conditions:
                    return {"text": "Please click one of the buttons above to continue."}

        session_dict[user]["condition"] = message
        session_dict[user]["onboarding_stage"] = "done"

        return llm_daily(message, user, session_dict)



### --- DAILY CHECK-IN DEBUG --- ###
def llm_daily(message, user, session_dict):
    for key, value in session_dict[user].items():
        print(f"{key}: {value}")
    return {"text": "📆 IN LLM DAILY"}

### --- FLASK ROUTE TO HANDLE USER REQUESTS --- ###
@app.route('/query', methods=['POST'])
def main():
    global session_dict
    data = request.get_json()
    message = data.get("text", "").strip()
    user = data.get("user_name", "Unknown")

    # Reload sessions from file
    session_dict = load_sessions()

    print("Current session dict:", session_dict)
    print("Current user:", user)

    # Restart handling
    if "restart" in message.lower():
        print("Restarting user:", user)
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
        save_sessions(session_dict)
        return jsonify({"text": "🔄 Restarted onboarding. " + first_interaction("", user)["text"]})

    # Initialize user session if not present
    if user not in session_dict:
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
        save_sessions(session_dict)

    if session_dict[user]["onboarding_stage"] != "done":
        response = first_interaction(message, user)
    else:
        response = llm_daily(message, user, session_dict)

    save_sessions(session_dict)
    return jsonify(response)

### --- RUN FLASK APP --- ###
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)

# import os
# import json
# import requests
# from flask import Flask, request, jsonify, Response
# from llmproxy import generate
# import re

# app = Flask(__name__)

# # JSON file to store user sessions
# SESSION_FILE = "session_store.json"

# ### --- SESSION MANAGEMENT FUNCTIONS --- ###
# def load_sessions():
#     """Load stored sessions from a JSON file."""
#     if os.path.exists(SESSION_FILE):
#         with open(SESSION_FILE, "r") as file:
#             try:
#                 return json.load(file)
#             except json.JSONDecodeError:
#                 return {}
#     return {}

# def save_sessions(session_dict):
#     """Save sessions to a JSON file."""
#     with open(SESSION_FILE, "w") as file:
#         json.dump(session_dict, file, indent=4)

# # Load sessions when the app starts
# session_dict = load_sessions()

# ### --- ONBOARDING FUNCTION --- ###
# def first_interaction(message, user):
#     questions = {
#         "condition": "🩺 What condition do you have? (Type II Diabetes, Crohn’s disease, or both)",
#         "age": "🎂 How old are you?",
#         "weight": "⚖️ What's your weight (in kg)?",
#         "medications": "💊 What medications are you currently taking?",
#         "emergency_contact": "📞 Who should we contact in case of emergency? (Name + Phone)",
#         "news_pref": "📰 What kind of weekly health updates would you like?\nOptions: Instagram Reel 📱, TikTok 🎵, or Research News 🧪"
#     }

#     stage = session_dict[user].get("onboarding_stage", "condition")

#     if stage == "condition":
#         session_dict[user]["condition"] = message
#         session_dict[user]["onboarding_stage"] = "age"
#         return {"text": questions["age"]}

#     elif stage == "age":
#         session_dict[user]["age"] = message
#         session_dict[user]["onboarding_stage"] = "weight"
#         return {"text": questions["weight"]}

#     elif stage == "weight":
#         session_dict[user]["weight"] = message
#         session_dict[user]["onboarding_stage"] = "medications"
#         return {"text": questions["medications"]}

#     elif stage == "medications":
#         session_dict[user]["medications"] = [med.strip() for med in message.split(",")]
#         session_dict[user]["onboarding_stage"] = "emergency_contact"
#         return {"text": questions["emergency_contact"]}

#     elif stage == "emergency_contact":
#         session_dict[user]["emergency_contact"] = message
#         session_dict[user]["onboarding_stage"] = "news_pref"
#         return {"text": questions["news_pref"]}

#     elif stage == "news_pref":
#         session_dict[user]["news_pref"] = [pref.strip() for pref in message.split(",")]
#         session_dict[user]["onboarding_stage"] = "done"
#         return {"text": "✅ Onboarding complete! You're all set. You can now do daily check-ins or request help anytime."}

#     else:
#         return llm_daily(message, user, session_dict)  # ✅ make sure to return this!

# ### --- DAILY CHECK-IN DEBUG --- ###
# def llm_daily(message, user, session_dict):
#     print("🔍 DEBUG: Current user data:")
#     for key, value in session_dict[user].items():
#         print(f"{key}: {value}")
#     return {"text": "📆 IN LLM DAILY"}

# ### --- FLASK ROUTE TO HANDLE USER REQUESTS --- ###
# @app.route('/query', methods=['POST'])
# def main():
#     data = request.get_json()
#     message = data.get("text", "").strip()
#     user = data.get("user_name", "Unknown")

    
#     print("Current session dict:", session_dict)
#     print("Current user:", user)

#     # Create a new session if user is new or restarted
#     if user not in session_dict or "restart" in message.lower():
#         print("new user", user)
#         session_dict[user] = {
#             "session_id": f"{user}-session",
#             "onboarding_stage": "condition",
#             "condition": "",
#             "age": 0,
#             "weight": 0,
#             "medications": [],
#             "emergency_contact": "",
#             "news_pref": ""
#         }
#         save_sessions(session_dict)

#     # Call appropriate flow
#     if session_dict[user]["onboarding_stage"] != "done":
#         response = first_interaction(message, user)
#     else:
#         response = llm_daily(message, user, session_dict)

#     save_sessions(session_dict)
#     return jsonify(response)

# ### --- RUN FLASK APP --- ###
# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5001)
