# Steps to run:
# 1. Install dependencies: pip install flask qrcode[pil]
# 2. Run the server: .\.venv\Scripts\python.exe .\EcoRewardQR-CODE.py
import qrcode
import json
import os
import random
import sys
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

app = Flask(__name__)

DATA_FILE = "EcoRewardQR.json"
QR_DIR    = "qr_codes"
BASE_URL  = os.environ.get("APP_BASE_URL", "http://localhost:5000").rstrip("/")
os.makedirs(QR_DIR, exist_ok=True)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"users": {}, "codes": {}}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# Products catalogue
PRODUCTS = [
    {"id": "P01", "name": "50% Off at Good Taste Restaurant", "points": 500,  "emoji": "🍜"},
    {"id": "P02", "name": "Free Coffee at Café by the Ruins", "points": 300, "emoji": "☕"},
    {"id": "P03", "name": "₱100 Off at Mount Cloud Bookshop",  "points": 250, "emoji": "📚"},
    {"id": "P04", "name": "Free Pony Ride - Wright Park",  "points": 400, "emoji": "🐴"},
    {"id": "P05", "name": "10% Off - BenCab Museum", "points": 200, "emoji": "🎨"},
    {"id": "P06", "name": "₱50 SM Baguio Gift Card", "points": 600, "emoji": "🛍️"},
    {"id": "P07", "name": "Free Strawberry Picking - La Trinidad", "points": 800, "emoji": "🍓"},
    {"id": "P08", "name": "Transcom Bus Discount ₱30", "points": 800, "emoji": "🚌"},
]

# QR Code generator
def generate_qr(points: int = 10, campaign: str = "default") -> str:
    """
    Creates a QR code PNG that encodes a URL pointing to this server.
    Returns the filename of the saved PNG.
    """
    code_id  = str(uuid.uuid4())[:8].upper()
    url      = f"{BASE_URL}/scan/{code_id}"

    # Store the code metadata
    data = load_data()
    data["codes"][code_id] = {
        "points":    points,
        "campaign":  campaign,
        "created":   datetime.now().isoformat(),
        "redeemed":  False,
        "redeemed_by": None,
    }
    save_data(data)

    # Build the QR image
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img      = qr.make_image(fill_color="#1a1a2e", back_color="white")
    filename = f"{QR_DIR}/qr_{code_id}.png"
    img.save(filename)

    print(f"\n✅  QR Code generated!")
    print(f"    Code ID  : {code_id}")
    print(f"    Points   : {points}")
    print(f"    Campaign : {campaign}")
    print(f"    Scan URL : {url}")
    print(f"    File     : {filename}\n")
    return filename, code_id

# Flask routes

# Serve the QR PNG files
@app.route("/qr_codes/<path:filename>")
def serve_qr(filename):
    return send_from_directory(QR_DIR, filename)


@app.route("/scan/<code_id>")
def scan(code_id):
    """Called when a user scans the QR code."""
    data = load_data()

    if code_id not in data["codes"]:
        return render_page(
            "❌ Invalid Code",
            "This QR code does not exist.",
            0, "#e74c3c", []
        )

    code = data["codes"][code_id]

    if code["redeemed"]:
        return render_page(
            "⚠️ Already Used",
            f"This code was already redeemed by user <b>{code['redeemed_by']}</b>.",
            0, "#e67e22", []
        )

    # Assign a simple anonymous user id via query param or auto-generate
    user_id = request.args.get("user", f"guest_{str(uuid.uuid4())[:6].upper()}")

    # Credit points
    if user_id not in data["users"]:
        data["users"][user_id] = {"points": 0, "history": []}

    earned = code["points"]
    data["users"][user_id]["points"] += earned
    data["users"][user_id]["history"].append({
        "code":   code_id,
        "earned": earned,
        "date":   datetime.now().isoformat(),
    })

    # Mark code as redeemed
    code["redeemed"]    = True
    code["redeemed_by"] = user_id
    save_data(data)

    total = data["users"][user_id]["points"]

    # Which products can this user afford?
    affordable = [p for p in PRODUCTS if p["points"] <= total]

    return render_page(
        "🎉 Congratulations!",
        f"You earned <b>{earned} points</b>!",
        total,
        "#27ae60",
        affordable,
        user_id=user_id,
    )


@app.route("/redeem", methods=["POST"])
def redeem():
    """Redeem points for a product."""
    body       = request.get_json()
    user_id    = body.get("user_id")
    product_id = body.get("product_id")

    data    = load_data()
    user    = data["users"].get(user_id)
    product = next((p for p in PRODUCTS if p["id"] == product_id), None)

    if not user or not product:
        return jsonify({"success": False, "message": "Invalid user or product."})

    if user["points"] < product["points"]:
        return jsonify({"success": False, "message": "Not enough points."})

    user["points"] -= product["points"]
    user["history"].append({
        "redeemed": product["name"],
        "cost":     product["points"],
        "date":     datetime.now().isoformat(),
    })
    save_data(data)

    return jsonify({
        "success":      True,
        "message":      f"✅ Redeemed: {product['emoji']} {product['name']}!",
        "points_left":  user["points"],
    })


@app.route("/balance/<user_id>")
def balance(user_id):
    """Check a user's point balance (JSON)."""
    data = load_data()
    user = data["users"].get(user_id, {"points": 0, "history": []})
    return jsonify({"user_id": user_id, "points": user["points"], "history": user["history"]})


@app.route("/")
def home():
    """Simple health page for web hosts."""
    return jsonify({
        "app": "EcoReward",
        "status": "running",
        "base_url": BASE_URL,
        "generate_url": f"{BASE_URL}/generate",
    })


@app.route("/generate")
def generate_from_browser():
    """Generate a QR code from the browser."""
    points = request.args.get("points", "random")
    campaign = request.args.get("campaign", "default")

    if points.lower() == "random":
        points = random.choice([10, 20, 30, 50, 75, 100])
    else:
        try:
            points = int(points)
        except ValueError:
            return jsonify({"success": False, "message": "points must be a number or random"}), 400

    filename, code_id = generate_qr(points=points, campaign=campaign)
    qr_filename = os.path.basename(filename)
    scan_url = f"{BASE_URL}/scan/{code_id}"
    qr_url = f"{BASE_URL}/qr_codes/{qr_filename}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>EcoReward QR Generated</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #f2f7f4;
      color: #173b2f;
      padding: 24px;
    }}
    main {{
      width: 100%;
      max-width: 420px;
      text-align: center;
      background: white;
      border: 1px solid #d7e6dd;
      border-radius: 8px;
      padding: 24px;
      box-shadow: 0 12px 30px rgba(20, 70, 45, 0.12);
    }}
    img {{
      width: 240px;
      height: 240px;
      margin: 12px auto;
      display: block;
    }}
    a {{
      color: #0f7a4d;
      overflow-wrap: anywhere;
      font-weight: 700;
    }}
    .meta {{
      margin: 12px 0;
      color: #47645a;
    }}
  </style>
</head>
<body>
  <main>
    <h1>QR Code Created</h1>
    <img src="{qr_url}" alt="Generated QR code"/>
    <p class="meta">Code ID: <strong>{code_id}</strong></p>
    <p class="meta">Points: <strong>{points}</strong></p>
    <p><a href="{scan_url}">{scan_url}</a></p>
  </main>
</body>
</html>"""


# HTML helpers

def render_page(title, message, points, color, products, user_id=""):
    product_cards = ""
    if products:
        for p in products:
            product_cards += f"""
            <div class="card">
              <span class="emoji">{p['emoji']}</span>
              <div class="card-info">
                <strong>{p['name']}</strong>
                <span>{p['points']} pts</span>
              </div>
              <button onclick="redeem('{user_id}', '{p['id']}', this)">Redeem</button>
            </div>"""
    else:
        product_cards = "<p class='no-items'>Keep scanning to earn more points!</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>EcoReward</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Segoe UI', sans-serif;
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}
    .container {{
      background: rgba(255,255,255,0.05);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(255,255,255,0.15);
      border-radius: 24px;
      padding: 36px 28px;
      max-width: 420px;
      width: 100%;
      text-align: center;
      color: #fff;
    }}
    h1 {{ font-size: 2rem; margin-bottom: 8px; }}
    .msg {{ color: #cdd; font-size: 1.05rem; margin-bottom: 20px; }}
    .points-badge {{
      display: inline-block;
      background: {color};
      border-radius: 50px;
      padding: 10px 28px;
      font-size: 1.4rem;
      font-weight: 700;
      margin-bottom: 28px;
      box-shadow: 0 4px 20px {color}66;
    }}
    .section-title {{
      font-size: 0.85rem;
      letter-spacing: 2px;
      text-transform: uppercase;
      color: #aab;
      margin-bottom: 14px;
    }}
    .card {{
      display: flex;
      align-items: center;
      gap: 12px;
      background: rgba(255,255,255,0.08);
      border-radius: 14px;
      padding: 14px 16px;
      margin-bottom: 10px;
      text-align: left;
    }}
    .emoji {{ font-size: 1.8rem; }}
    .card-info {{ flex: 1; }}
    .card-info strong {{ display: block; font-size: 0.95rem; }}
    .card-info span {{ font-size: 0.8rem; color: #aab; }}
    button {{
      background: {color};
      color: #fff;
      border: none;
      border-radius: 8px;
      padding: 8px 14px;
      font-size: 0.85rem;
      cursor: pointer;
      font-weight: 600;
      transition: opacity .2s;
    }}
    button:hover {{ opacity: 0.85; }}
    button:disabled {{ opacity: 0.4; cursor: not-allowed; }}
    .no-items {{ color: #aab; font-size: 0.9rem; margin: 16px 0; }}
    #toast {{
      position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
      background: #27ae60; color: #fff; padding: 12px 24px;
      border-radius: 50px; font-size: 0.95rem; display: none;
      box-shadow: 0 4px 20px #0008;
    }}
  </style>
</head>
<body>
<div class="container">
  <h1>{title}</h1>
  <p class="msg">{message}</p>
  {"<div class='points-badge'>🏆 " + str(points) + " Total Points</div>" if points > 0 else ""}
  {"<p class='section-title'>Available Rewards</p>" if products else ""}
  <div id="products">{product_cards}</div>
</div>
<div id="toast"></div>
<script>
async function redeem(userId, productId, btn) {{
  btn.disabled = true;
  btn.textContent = '...';
  const res = await fetch('/redeem', {{
    method: 'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{user_id: userId, product_id: productId}})
  }});
  const data = await res.json();
  showToast(data.message);
  if (data.success) {{
    btn.closest('.card').style.opacity = '0.4';
  }} else {{
    btn.disabled = false;
    btn.textContent = 'Redeem';
  }}
}}
function showToast(msg) {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3500);
}}
</script>
</body>
</html>"""

# Entry point
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "generate":
        # Quick CLI mode: just generate a QR code
        pts      = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        campaign = sys.argv[3]      if len(sys.argv) > 3 else "default"
        generate_qr(points=pts, campaign=campaign)
    else:
        # Generate a sample QR then start the server
        print("=" * 50)
        print("  QR Loyalty System")
        print("=" * 50)
        generate_qr(points=10, campaign="welcome")
        generate_qr(points=50, campaign="promo")
        port = int(os.environ.get("PORT", 5000))
        print(f"Starting server → http://localhost:{port}")
        print("Scan any QR code to earn points!\n")
        app.run(debug=True, host="0.0.0.0", port=port)
