from flask import Flask, render_template, request, jsonify
import json
import os
import google.generativeai as genai
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

# ==== CONFIGURATION ====
TWILIO_ACCOUNT_SID = 'AC###'  #place your twilio account sid
TWILIO_AUTH_TOKEN = '######' #place your twilio authentication token
TWILIO_WHATSAPP_NUMBER = 'whatsapp:+14155238886'

GEMINI_API_KEY = '#######'  # place Your Gemini API key here
GEMINI_MODEL = 'models/text-bison-001'  # Gemini 1.5 Text Generation model

genai.configure(api_key=GEMINI_API_KEY)

DATA_FILE = "cart_data.json"

app = Flask(__name__)
client_twilio = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# ==== Helper Functions ====

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        content = f.read().strip()
        if not content:
            return {}
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            print("[ERROR] JSON decode failed. Resetting data file.")
            return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def normalize_phone(phone):
    phone = phone.strip()
    if phone.startswith("whatsapp:"):
        phone = phone[len("whatsapp:"):]
    if not phone.startswith("+"):
        phone = "+" + phone
    return phone

def send_whatsapp_message(to_number, message):
    try:
        client_twilio.messages.create(
            body=message,
            from_=TWILIO_WHATSAPP_NUMBER,
            to=f"whatsapp:{to_number}"
        )
    except Exception as e:
        print(f"[ERROR] WhatsApp send failed: {e}")

def generate_cart_summary(cart):
    if all(isinstance(item, str) for item in cart):
        return "Customer's cart contains:\n" + "\n".join(f"- {item}" for item in cart)
    else:
        return "Customer's cart contains:\n" + "\n".join(f"- {item['name']}" for item in cart)

def get_gemini_reply(messages):
    try:
        # Build the prompt text for Gemini 1.5 Flash
        prompt = ""
        for msg in messages:
            author = msg["author"]
            content = msg["content"]
            prompt += f"{author.capitalize()}: {content}\n"
        prompt += "Bot:"

        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        # print(response)
        # print(response)
        return response.candidates[0].content.parts[0].text
    except Exception as e:
        print(f"[Gemini Error]: {e}")
        return "Sorry, I'm having trouble connecting right now. Please try again later."

# ==== Routes ====

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/abandon_cart", methods=["POST"])
def abandon_cart():
    data = request.json
    user = data.get("user")
    cart = data.get("cart")

    if not user or not cart:
        return jsonify({"error": "User and cart info required"}), 400

    phone = normalize_phone(user.get("phone", ""))
    if not phone:
        return jsonify({"error": "Valid phone number required"}), 400

    all_data = load_data()
    all_data[phone] = {
        "user": user,
        "cart": cart,
        "consent": None,
        "conversation": []
    }
    save_data(all_data)

    cart_summary = generate_cart_summary(cart)
    initial_message = (
        "👋 Hi there! We noticed you left items in your cart:\n"
        f"{cart_summary}\n\n"
        "Would you like help completing your purchase? Reply YES or NO."
    )
    send_whatsapp_message(phone, initial_message)

    return jsonify({"message": "Cart abandonment flow initiated"})

@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    from_number = normalize_phone(request.values.get("From", ""))
    body = request.values.get("Body", "").strip()

    print(f"📩 Incoming from {from_number}: {body}")

    all_data = load_data()
    if from_number not in all_data:
        resp = MessagingResponse()
        resp.message("Sorry, no active cart session found. Please start by adding items to your cart.")
        return str(resp)

    user_data = all_data[from_number]
    response = MessagingResponse()

    if user_data["consent"] is None:
        if body.lower() == "yes":
            user_data["consent"] = True
            reply = (
                "Great! I can help with:\n"
                "1️⃣ Answer questions about products\n"
                "2️⃣ Apply discount codes\n"
                "3️⃣ Complete your purchase\n"
                "What would you like to do?"
            )
        elif body.lower() == "no":
            reply = "No problem! Come back anytime. Type 'HELP' if you change your mind."
            del all_data[from_number]
            save_data(all_data)
            response.message(reply)
            return str(response)
        else:
            reply = "Please reply with YES or NO."
    else:
        cart_context = generate_cart_summary(user_data["cart"])
        system_prompt = (
            "You are a helpful e-commerce assistant. The customer abandoned this cart:\n"
            f"{cart_context}\n\n"
            "Be concise, friendly, and help them complete the purchase or answer any product questions."
        )

        # Prepare messages in Gemini format
        messages = [{"author": "system", "content": system_prompt}]
        for msg in user_data["conversation"]:
            if "user" in msg:
                messages.append({"author": "user", "content": msg["user"]})
            if "assistant" in msg:
                messages.append({"author": "bot", "content": msg["assistant"]})
        messages.append({"author": "user", "content": body})

        reply = get_gemini_reply(messages)
        print("reply: ",reply)

    user_data["conversation"].append({"user": body})
    if user_data.get("consent") is True:
        user_data["conversation"].append({"assistant": reply})

    save_data(all_data)
    response.message(reply)
    return str(response)

if __name__ == "__main__":
    app.run(debug=True, port=5001)
