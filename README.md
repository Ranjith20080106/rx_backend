# CVGenius AI Backend

A production-ready asynchronous Python backend for **CVGenius AI Resume Analyzer** powered by **FastAPI** and **Google Gemini AI**.

---

## Features Implemented
1. **Resume File Upload & Extraction:** Asynchronous endpoints supporting PDF (`pypdf`) and Word `.docx` (`python-docx`) text parsing, validation of extensions, and file size limits (10MB).
2. **Localized ATS Engine:** Structured Python algorithm scoring format layout, match/missing technical keywords, action verb impact ratios, and cliché buzzword penalties.
3. **Google Gemini Integration:** Queries `gemini-1.5-flash` with optimized instructions to return JSON-structured career suggestions, additional skill gaps, and custom optimized professional introductions.
4. **AI Career Advisor Chatbot:** Fully conversational chatbot history context tracker tailored around the candidate's resume keywords.

---

## Tech Stack
* Python 3.9+
* FastAPI (Web Framework)
* Uvicorn (ASGI Web Server)
* Google Generative AI (Gemini SDK)
* PyPDF (PDF Reader)
* python-docx (Word Parser)

---

## Installation & Setup

### 1. Set Up Environment File
Navigate to the `backend` folder, duplicate `.env.example`, name it `.env`, and populate your Gemini API Key:
```bash
cp .env.example .env
```
Inside `.env`:
```env
GEMINI_API_KEY=AIzaSyYourKeyHere...
HOST=127.0.0.1
PORT=8000
```
*(Get a free key from [Google AI Studio](https://aistudio.go
* **Endpoint:** `POST /chat`
* **Payload (JSON):**
  ```json
  {
    "message": "How can I explain my employment gap?",
    "history": [
      { "sender": "user", "text": "Hello!" },
      { "sender": "assistant", "text": "Hi! I am your AI career advisor." }
    ],
    "resume_text": "Resume text string context (optional)..."
  }
  ```
* **Response:**
  ```json
  {
    "response": "Address employment gaps by framing them as dedicated upskilling periods. For example, explain that you took structured time off to master TypeScript and system architectures..."
  }
  ```

---

## Frontend Integration Code Examples

### 1. Uploading a Resume File
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

fetch('http://127.0.0.1:8000/analyze-resume', {
  method: 'POST',
  body: formData
})
.then(res => res.json())
.then(data => {
  console.log("Overall Score:", data.score);
  console.log("Optimized Summary:", data.summary_optimization);
  // Update UI Elements with response data
})
.catch(err => console.error("Error analyzing:", err));
```

### 2. Querying the Chatbot
```javascript
fetch('http://127.0.0.1:8000/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: "How can I improve my action verbs?",
    history: [
      { sender: "user", text: "Hi" },
      { sender: "assistant", text: "Hello! How can I help you today?" }
    ],
    resume_text: "Raw resume text for context..."
  })
})
.then(res => res.json())
.then(data => {
  console.log("Advisor Response:", data.response);
})
.catch(err => console.error("Error chatting:", err));
```
