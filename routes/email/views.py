# routes/login/views.py
import base64
from flask_login import login_required, current_user
from flask import jsonify, request
from google import genai
from utils import *
from . import email_bp
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

email_cache = {}  # key: email_id, value: full message
schema = {
    "type": "object",
    "properties": {
        "loading_places_amount": {"type": "number"},
        "unloading_places_amount": {"type": "number"},
        "loading_location": {"type": "string"},
        "loading_date_from": {"type": "string"},
        "loading_date_to": {"type": "string"},
        "loading_time_from": {"type": "string"},
        "loading_time_to": {"type": "string"},
        "unloading_location": {"type": "string"},
        "unloading_date_from": {"type": "string"},
        "unloading_date_to": {"type": "string"},
        "unloading_time_from": {"type": "string"},
        "unloading_time_to": {"type": "string"},
        "shipment_size": {"type": "string"},
        "shipment_weight": {"type": "string"},
        "palette_exchange": {"type": "boolean"},
        "vehicle_type": {"type": "string"},
        "vehicle_body": {"type": "string"},
        "vehicle_certificates": {"type": "string"},
    },
    "required": ["loading_date_from","loading_date_to","loading_location",
                 "unloading_date_from","unloading_date_to","unloading_location",
                 "shipment_size","shipment_weight","vehicle_type","vehicle_body"]
}

client = genai.Client(api_key='AIzaSyByu3AatMxSafp8eKCBeON4DYTjm8ZfiYw')

@email_bp.route('/api/gmail-emails')
@login_required
@no_cache
def get_emails():
    if current_user.user_id not in user_tokens:
        return jsonify({"error": "No Gmail account connected"}), 400

    creds_dict = user_tokens[current_user.user_id]
    creds = Credentials(
        creds_dict['token'],
        refresh_token=creds_dict['refresh_token'],
        token_uri=creds_dict['token_uri'],
        client_id=creds_dict['client_id'],
        client_secret=creds_dict['client_secret'],
        scopes=creds_dict['scopes']
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # frissítsd a dict-et is:
        user_tokens[current_user.user_id]['token'] = creds.token

    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(userId='me', maxResults=20).execute()
    messages = results.get('messages', [])

    emails = []
    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id'], format='metadata', metadataHeaders=['From', 'Subject']).execute()
        headers = {h['name']: h.get('value', '') for h in msg_data['payload']['headers']}
        emails.append({
            "id": msg['id'],
            "from": headers.get('From', ''),
            "subject": headers.get('Subject', '')
        })

    return jsonify(emails)


@email_bp.route('/api/gmail-email/<email_id>')
@login_required
@no_cache
def get_email(email_id):
    """Lazy load: teljes üzenet, HTML/Plain text formázással"""
    if current_user.user_id not in user_tokens:
        return jsonify({"error": "No Gmail account connected"}), 400

    if email_id in email_cache:
        return jsonify(email_cache[email_id])

    creds_dict = user_tokens[current_user.user_id]
    creds = Credentials(
        creds_dict['token'],
        refresh_token=creds_dict['refresh_token'],
        token_uri=creds_dict['token_uri'],
        client_id=creds_dict['client_id'],
        client_secret=creds_dict['client_secret'],
        scopes=creds_dict['scopes']
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # frissítsd a dict-et is:
        user_tokens[current_user.user_id]['token'] = creds.token

    service = build('gmail', 'v1', credentials=creds)
    msg_data = service.users().messages().get(userId='me', id=email_id, format='full').execute()

    body = ""
    if 'parts' in msg_data['payload']:
        for part in msg_data['payload']['parts']:
            if part['mimeType'] == 'text/html':
                import base64
                body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                break
            elif part['mimeType'] == 'text/plain' and not body:
                import base64
                body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
    else:
        import base64
        body = base64.urlsafe_b64decode(msg_data['payload']['body']['data']).decode('utf-8')

    email_cache[email_id] = {"id": email_id, "body": body}
    return jsonify(email_cache[email_id])


@email_bp.route('/api/gmail-email-ai/<email_id>', methods=['GET'])
@login_required
@no_cache
def email_to_cargo(email_id):
    if current_user.user_id not in user_tokens:
        return jsonify({"error": "No Gmail account connected"}), 400

    creds_dict = user_tokens[current_user.user_id]
    creds = Credentials(
        creds_dict['token'],
        refresh_token=creds_dict['refresh_token'],
        token_uri=creds_dict['token_uri'],
        client_id=creds_dict['client_id'],
        client_secret=creds_dict['client_secret'],
        scopes=creds_dict['scopes']
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # frissítsd a dict-et is:
        user_tokens[current_user.user_id]['token'] = creds.token

    # Gmail üzenet lekérése
    service = build('gmail', 'v1', credentials=creds)
    msg_data = service.users().messages().get(userId='me', id=email_id, format='full').execute()

    # Email plain text vagy HTML kinyerése
    parts = msg_data['payload'].get('parts', [])
    email_text = ""
    for part in parts:
        if part['mimeType'] == 'text/plain':
            raw_data = part['body'].get('data', '')
            email_text = base64.urlsafe_b64decode(raw_data).decode('utf-8', errors='ignore')
            break
    if not email_text:
        email_text = msg_data['snippet']

    print(email_text)

    # JSON schema a Gemini AI kéréshez
    schema = {
        "type": "object",
        "properties": {
            # Honnan
            "from_country": {"type": "string"},
            "from_postcode": {"type": "string"},
            "from_city": {"type": "string"},
            "is_hidden_from": {"type": "boolean"},

            # Hová
            "to_country": {"type": "string"},
            "to_postcode": {"type": "string"},
            "to_city": {"type": "string"},
            "is_hidden_to": {"type": "boolean"},

            # Felvétel
            "departure_from": {"type": "string"},
            "departure_from_time_start": {"type": "string"},
            "departure_from_time_end": {"type": "string"},
            "departure_end_date": {"type": "string"},
            "departure_end_time_start": {"type": "string"},
            "departure_end_time_end": {"type": "string"},

            # Rakodás
            "arrival_start_date": {"type": "string"},
            "arrival_start_time_start": {"type": "string"},
            "arrival_start_time_end": {"type": "string"},
            "arrival_end_date": {"type": "string"},
            "arrival_end_time_start": {"type": "string"},
            "arrival_end_time_end": {"type": "string"},

            # Áru
            "length": {"type": "number"},
            "weight": {"type": "number"},
            "description": {"type": "string"},

            # Jármű
            "vehicle_type": {"type": "string"},
            "superstructure": {"type": "string"},
            "equipment": {"type": "array", "items": {"type": "string"}},
            "certificates": {"type": "string"},
            "cargo_securement": {"type": "string"}
        }
    }

    # AI kérés (Gemini)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"Extract info from this email to fill a freight form. If no postcode or country given, fill it knowing the city in the e-mail. Return JSON only, no explanation."
                 f"Use the following form field names exactly: from_country, from_postcode, from_city, is_hidden_from, "
                 f"to_country, to_postcode, to_city, is_hidden_to, departure_from, departure_from_time_start, "
                 f"departure_from_time_end, departure_end_date, departure_end_time_start, departure_end_time_end, "
                 f"arrival_start_date, arrival_start_time_start, arrival_start_time_end, arrival_end_date, "
                 f"arrival_end_time_start, arrival_end_time_end, length, weight, description, vehicle_type, "
                 f"superstructure, equipment, certificates, cargo_securement.\n\nEmail text:\n{email_text}",
        config={"response_mime_type": "application/json", "response_schema": schema}
    )

    return jsonify(response.parsed)


@email_bp.route('/parse-email', methods=['POST'])
@login_required
@no_cache
def parse_email():
    email_text = request.json.get("email_text", "")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"Extract info as JSON from this email. Everything in English. Text:\n{email_text}",
        config={
            "response_mime_type": "application/json",
            "response_schema": schema
        }
    )
    return jsonify(response.parsed)
