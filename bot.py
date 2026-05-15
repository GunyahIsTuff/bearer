from flask import Flask, jsonify, request
import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# =========================
# SETTINGS
# =========================

class GameInfo:
    def __init__(self):
        self.TitleId = os.getenv("PLAYFAB_TITLE_ID", "1F89E1")
        self.SecretKey = os.getenv("PLAYFAB_SECRET_KEY")
        self.ApiKey = os.getenv("META_API_KEY")
        self.DiscordWebhookUrl = os.getenv("DISCORD_WEBHOOK")

    def get_auth_headers(self):
        return {
            "Content-Type": "application/json",
            "X-SecretKey": self.SecretKey
        }

settings = GameInfo()

# =========================
# NONCE CACHE
# =========================

USED_NONCES = {}
NONCE_EXPIRY = 300  # 5 mins

def cleanup_nonces():
    current = time.time()

    expired = [
        nonce for nonce, expiry in USED_NONCES.items()
        if expiry < current
    ]

    for nonce in expired:
        del USED_NONCES[nonce]

# =========================
# HELPERS
# =========================

def get_client_ip():
    forwarded = request.headers.get("X-Forwarded-For")

    if forwarded:
        return forwarded.split(",")[0].strip()

    return request.remote_addr

def GetOrgScopedId(oculus_id: str):
    url = (
        f"https://graph.oculus.com/{oculus_id}"
        f"?access_token={settings.ApiKey}"
        f"&fields=org_scoped_id"
    )

    res = requests.get(url)

    if res.status_code != 200:
        return None

    return res.json().get("org_scoped_id")

def GetMetaAlias(oculus_id: str):
    url = (
        f"https://graph.oculus.com/{oculus_id}"
        f"?access_token={settings.ApiKey}"
        f"&fields=alias"
    )

    res = requests.get(url)

    if res.status_code != 200:
        return None

    return res.json().get("alias")

def GetIsNonceValid(nonce: str, oculus_id: str):
    url = (
        "https://graph.oculus.com/user_nonce_validate"
        f"?nonce={nonce}"
        f"&user_id={oculus_id}"
        f"&access_token={settings.ApiKey}"
    )

    req = requests.post(
        url=url,
        headers={"Content-Type": "application/json"}
    )

    if req.status_code != 200:
        return False

    return req.json().get("is_valid", False)

def send_auth_webhook(
    success: bool,
    custom_id: str = None,
    playfab_id: str = None,
    oculus_id: str = None,
    meta_alias: str = None,
    error_message: str = None
):
    if not settings.DiscordWebhookUrl:
        return

    try:
        if success:
            embed = {
                "embeds": [{
                    "title": "Player Authenticated",
                    "color": 65280,
                    "fields": [
                        {
                            "name": "PlayFab ID",
                            "value": playfab_id or "N/A",
                            "inline": True
                        },
                        {
                            "name": "Custom ID",
                            "value": custom_id or "N/A",
                            "inline": True
                        },
                        {
                            "name": "Meta Alias",
                            "value": meta_alias or "N/A",
                            "inline": True
                        }
                    ]
                }]
            }
        else:
            embed = {
                "embeds": [{
                    "title": "Authentication Failed",
                    "color": 16711680,
                    "fields": [
                        {
                            "name": "Reason",
                            "value": error_message or "Unknown Error"
                        },
                        {
                            "name": "Oculus ID",
                            "value": oculus_id or "N/A"
                        }
                    ]
                }]
            }

        requests.post(
            settings.DiscordWebhookUrl,
            json=embed,
            timeout=5
        )

    except Exception as e:
        print(f"Webhook Error: {e}")

# =========================
# ROOT
# =========================

@app.route("/", methods=["GET"])
def main():
    return jsonify({
        "status": "online"
    })

# =========================
# PLAYFAB AUTH
# =========================

@app.route("/api/PlayFabAuthentication", methods=["POST"])
def playfab_authentication():

    cleanup_nonces()

    rjson = request.get_json()

    required_fields = [
        "Nonce",
        "AppId",
        "Platform",
        "OculusId"
    ]

    missing = [
        field for field in required_fields
        if not rjson.get(field)
    ]

    if missing:
        return jsonify({
            "Message": f"Missing parameter: {missing[0]}"
        }), 400

    if rjson.get("AppId") != settings.TitleId:
        return jsonify({
            "Message": "Invalid App ID"
        }), 403

    platform = rjson.get("Platform")

    # =========================
    # EDITOR LOGIN
    # =========================

    if platform == "Editor":

        login_request = requests.post(
            url=f"https://{settings.TitleId}.playfabapi.com/Server/LoginWithServerCustomId",
            json={
                "ServerCustomId": "EDITOR_AUTH",
                "CreateAccount": True
            },
            headers=settings.get_auth_headers()
        )

        if login_request.status_code != 200:
            return jsonify({
                "Message": "Editor auth failed"
            }), 500

        data = login_request.json()["data"]

        return jsonify({
            "PlayFabId": data["PlayFabId"],
            "SessionTicket": data["SessionTicket"],
            "EntityToken": data["EntityToken"]["EntityToken"],
            "EntityId": data["EntityToken"]["Entity"]["Id"],
            "EntityType": data["EntityToken"]["Entity"]["Type"]
        }), 200

    # =========================
    # QUEST AUTH
    # =========================

    nonce = rjson.get("Nonce")
    oculus_id = rjson.get("OculusId")

    # Prevent replay attacks
    if nonce in USED_NONCES:
        return jsonify({
            "Message": "Nonce already used"
        }), 403

    org_scoped_id = GetOrgScopedId(oculus_id)

    if not org_scoped_id:
        send_auth_webhook(
            False,
            oculus_id=oculus_id,
            error_message="Invalid Oculus ID"
        )

        return jsonify({
            "Message": "Invalid Oculus ID"
        }), 403

    if not GetIsNonceValid(nonce, oculus_id):

        send_auth_webhook(
            False,
            oculus_id=oculus_id,
            error_message="Invalid Nonce"
        )

        return jsonify({
            "Message": "Invalid nonce"
        }), 403

    USED_NONCES[nonce] = time.time() + NONCE_EXPIRY

    meta_alias = GetMetaAlias(oculus_id)

    login_request = requests.post(
        url=f"https://{settings.TitleId}.playfabapi.com/Server/LoginWithServerCustomId",
        json={
            "ServerCustomId": "OCULUS" + oculus_id,
            "CreateAccount": True
        },
        headers=settings.get_auth_headers()
    )

    if login_request.status_code != 200:

        try:
            error_json = login_request.json()
            error_message = error_json.get(
                "errorMessage",
                "PlayFab Error"
            )

        except:
            error_message = "PlayFab Error"

        send_auth_webhook(
            False,
            oculus_id=oculus_id,
            error_message=error_message
        )

        return jsonify({
            "Message": error_message
        }), login_request.status_code

    data = login_request.json()["data"]

    session_ticket = data["SessionTicket"]
    playfab_id = data["PlayFabId"]

    entity_token = data["EntityToken"]["EntityToken"]
    entity_id = data["EntityToken"]["Entity"]["Id"]
    entity_type = data["EntityToken"]["Entity"]["Type"]

    custom_id = rjson.get("CustomId")

    if custom_id:
        requests.post(
            url=f"https://{settings.TitleId}.playfabapi.com/Server/LinkServerCustomId",
            json={
                "ForceLink": True,
                "PlayFabId": playfab_id,
                "ServerCustomId": custom_id
            },
            headers=settings.get_auth_headers()
        )

    send_auth_webhook(
        True,
        custom_id=custom_id,
        playfab_id=playfab_id,
        oculus_id=oculus_id,
        meta_alias=meta_alias
    )

    return jsonify({
        "PlayFabId": playfab_id,
        "SessionTicket": session_ticket,
        "EntityToken": entity_token,
        "EntityId": entity_id,
        "EntityType": entity_type
    }), 200

# =========================
# PHOTON AUTH
# =========================

@app.route("/api/photon", methods=["POST"])
def photon_auth():

    rjson = request.get_json()

    ticket = rjson.get("Ticket")

    if not ticket:
        return jsonify({
            "resultCode": 2,
            "message": "Missing ticket"
        })

    try:
        user_id = ticket.split("-")[0]
    except:
        return jsonify({
            "resultCode": 2,
            "message": "Invalid ticket"
        })

    req = requests.post(
        url=f"https://{settings.TitleId}.playfabapi.com/Server/GetUserAccountInfo",
        json={
            "PlayFabId": user_id
        },
        headers=settings.get_auth_headers()
    )

    if req.status_code != 200:
        return jsonify({
            "resultCode": 0,
            "message": "PlayFab lookup failed"
        })

    nickname = (
        req.json()
        .get("UserInfo", {})
        .get("UserAccountInfo", {})
        .get("Username")
    )

    return jsonify({
        "resultCode": 1,
        "message": f"Authenticated {user_id}",
        "userId": user_id.upper(),
        "nickname": nickname
    })

# =========================
# CACHE ENDPOINT
# =========================

@app.route("/api/CachePlayFabId", methods=["POST"])
def cache_playfab_id():
    return jsonify({
        "Message": "Success"
    }), 200

# =========================
# START
# =========================

if __name__ == "__main__":

    if not settings.SecretKey:
        raise Exception("Missing PLAYFAB_SECRET_KEY")

    if not settings.ApiKey:
        raise Exception("Missing META_API_KEY")

    app.run(
        host="0.0.0.0",
        port=9080
    )
