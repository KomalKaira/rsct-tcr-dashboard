import json
import base64

# ✅ Point to your service account key file
with open("data/service_account_key.json", "r") as f:
    creds = json.load(f)

# ✅ Convert JSON to base64 string
encoded = base64.b64encode(json.dumps(creds).encode("utf-8")).decode("utf-8")

# ✅ Print the long one-line secret
print(encoded)
