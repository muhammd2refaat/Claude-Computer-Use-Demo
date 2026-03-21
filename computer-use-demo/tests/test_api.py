import os
import json
import urllib.request
from urllib.error import URLError, HTTPError

def load_env():
    """Simple parser to load variables from .env if python-dotenv is not installed"""
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "=" in line:
                    key, value = line.strip().split("=", 1)
                    # Strip any surrounding quotes that users might mistakenly leave
                    value = value.strip('\'"')
                    os.environ[key] = value

def test_connection():
    load_env()
    
    # We'll use the environment variable GEMINI_API_KEY if they set it
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY") # fallback strictly for testing if they replaced it

    # Default to Gemini 2.5 Pro as requested
    model = "gemini-2.5-flash"
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    print("=== Configuration ===")
    print(f"Provider: Google Gemini Native")
    print(f"API Key:  {'[SET]' if api_key else '[MISSING]'}")
    if api_key:
        print(f"Key Prefix: {api_key[:12]}...")

    if not api_key:
        print("\n❌ Error: No API key found. Set GEMINI_API_KEY in .env")
        return

    print(f"\n[1] Testing Google Gemini API Authentication for {model}...")
    
    payload = json.dumps({
        "contents": [{
            "parts": [{"text": "Say 'hello from gemini' and nothing else."}]
        }]
    }).encode("utf-8")
    
    headers = {
        "Content-Type": "application/json"
    }
    
    req = urllib.request.Request(endpoint, data=payload, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = json.loads(response.read().decode())
            print("    ✅ Successfully authenticated and communicated with Gemini!")
            try:
                text = res_body['candidates'][0]['content']['parts'][0]['text']
                print(f"    AI Response: {text.strip()}")
            except KeyError:
                print(f"    AI Response Structure: {res_body}")
            print("\n🎉 Your Gemini API connection is fully working!")
    
    except HTTPError as e:
        body = e.read().decode()
        print("\n    ❌ Request Failed!")
        print(f"    HTTP Code: {e.code}")
        print(f"    Response: {body}")
        
    except URLError as e:
        print(f"\n    ❌ Connection Error! Details: {e.reason}")

if __name__ == "__main__":
    test_connection()
