# 🧠 SupportBrain — AI Customer Support Agent with Persistent Hindsight Memory

> **Hackathon Project:** An AI customer support agent that uses **Hindsight** as its persistent memory system to remember customer conversations, recurring problems, proven solutions, and preferences across sessions.

---

## 🌟 The Core Problem & Solution

Traditional AI customer support bots suffer from **amnesia**: every new conversation starts from zero. When a customer returns with a recurring issue, they are forced to re-explain their background, their company, and the previous troubleshooting steps.

**SupportBrain solves this using Hindsight:**
1. **Remembers Customers:** Tracks company, role, product tier, and user preferences.
2. **Remembers Solutions:** When a problem was resolved previously (e.g., clearing browser cookies for session invalidation), SupportBrain recalls the exact verified solution.
3. **Becomes Smarter Over Time:** Every new resolved problem is retained into Hindsight for future encounters.

---

## 🏗️ Tech Stack

- **Backend:** Python + FastAPI
- **Memory System:** [Hindsight](https://github.com/vectorize-io/hindsight) (`hindsight-client` Python SDK)
- **LLM:** [Groq API](https://console.groq.com) (`llama-3.3-70b-versatile`)
- **Frontend:** Pure HTML5, Modern CSS, Vanilla JavaScript (zero complex build steps)
- **Environment:** Configured via `.env`

---

## 📂 Project Structure

```
supportbrain/
├── backend/
│   ├── main.py          # FastAPI application & API endpoints (/api/chat, /api/memories)
│   ├── agent.py         # LLM logic isolated with Groq SDK & prompt engineering
│   ├── memory.py        # Hindsight memory integration isolated with official SDK
│   └── requirements.txt # Python dependencies
├── frontend/
│   ├── index.html       # Clean 3-panel dashboard (Profile, Chat, Memory Panel)
│   ├── app.js           # Client-side reactivity & API communication
│   └── style.css        # Modern, dark-mode hackathon dashboard styling
├── .env.example         # Template configuration
├── .env                 # Environment variables (API keys)
└── README.md            # Documentation & judge demo walkthrough
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10+ installed
- (Optional) Groq API key from [Groq Console](https://console.groq.com/keys) (If not set, SupportBrain runs with an intelligent built-in simulation mode so the memory workflow is fully testable immediately!)

### 2. Install Dependencies
```bash
cd supportbrain
pip install -r backend/requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Inside `.env`:
```ini
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# Hindsight Memory Configuration:
# - Default: http://127.0.0.1:8000 (Uses built-in standard Hindsight engine)
# - Docker:  http://127.0.0.1:8888 (docker run -p 8888:8888 ghcr.io/vectorize-io/hindsight:latest)
# - Cloud:   https://api.hindsight.vectorize.io
HINDSIGHT_BASE_URL=http://127.0.0.1:8000
HINDSIGHT_API_KEY=
HINDSIGHT_BANK_ID=supportbrain-bank
PORT=8000
```

### 4. Run the Application
```bash
python -m uvicorn backend.main:app --reload --port 8000
```
Open your browser to:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 🎯 Step-by-Step Hackathon Judge Demo

### Step 1: Initial State & Memory Inspection
1. Open [http://localhost:8000](http://localhost:8000).
2. Look at the right-hand **Hindsight Memory Panel**. Click **"Full Bank"** to see pre-seeded knowledge units:
   - **Customer:** Rahul Sharma
   - **Company:** Acme Technologies
   - **Product:** Enterprise Dashboard
   - **Previous Issue:** Invalid session / login failed after timeout
   - **Previous Solution:** Clear browser session and local storage cache
   - **Result:** Successfully resolved

### Step 2: Test Memory-Aware Recall (The "Aha!" Moment)
1. In the chat input, type or click the demo button:
   > *"I'm having the login problem again."*
2. Notice what happens:
   - **Memory Panel (Right):** Immediately displays the recalled Hindsight memory card with a **95% relevance match** and highlighted Previous Solution (`Clear browser session`).
   - **Agent Response (Center):**
     > *"Hello Rahul Sharma! I checked your history in Hindsight and remember you had a similar session issue previously on Enterprise Dashboard. Last time, **Clear browser session and local storage cache** resolved it completely. Would you like to try that again?"*
3. This clearly proves to the judge that the AI remembered past resolutions rather than giving generic advice.

### Step 3: Test Dynamic Knowledge Retention
1. Send a new piece of information:
   > *"My name is Sarah Connor. I work at Cyberdyne Systems and we use Cloud Analytics."*
2. The agent acknowledges the customer details.
3. Check the **Hindsight Memory Panel**: Hindsight has extracted and retained Sarah Connor's profile in the bank!
4. Ask:
   > *"What is my company and which product do we use?"*
5. SupportBrain queries Hindsight and answers correctly using memory context!

---

## 🧩 Architectural Highlights

### Isolated Hindsight Integration (`backend/memory.py`)
All interactions with Hindsight are encapsulated inside `backend/memory.py`:
- Uses the official `hindsight-client` Python SDK (`Hindsight(base_url=..., api_key=...)`).
- Stores memories using `client.aretain` with structured tags (`customer:...`, `company:...`, `product:...`) and metadata (`issue`, `solution`, `result`).
- Searches memories using `client.arecall` with semantic & keyword matching.
- Provides seamless fallback to local persistent JSON store if external servers are unreachable.

### Isolated LLM Agent (`backend/agent.py`)
All prompt construction and Groq LLM calls live in `backend/agent.py`:
- Injects recalled Hindsight memories directly into the system prompt.
- Explicitly guides the model to reference past solutions if relevant.
- Automatically parses customer replies to extract new problems and solutions to retain back into Hindsight.

---

## 🛡️ License
MIT License — Built for Hackathons with ❤️ and Hindsight.
