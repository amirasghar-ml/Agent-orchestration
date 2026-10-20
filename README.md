# Multi-Agent AI Assistant

This project is a small multi-agent system built in Python. It routes a user request to the most relevant specialist agent and then combines their results into a single answer.

## Features

- Research agent for web-based lookups
- Data agent for arithmetic and numerical analysis
- Coding agent for Python syntax checking
- Documents agent for text/statistical analysis
- Master router to decide which agents to use
- Browser-based frontend for chat interaction

## Requirements

- Python 3.9+
- API access to an OpenAI-compatible model (default is Ollama)
- Environment variables for model configuration

## Setup

1. Open a terminal in the project folder.
2. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install python-dotenv pydantic langchain-openai langchain-community langgraph duckduckgo-search flask
   ```

4. Create a `.env` file in the project root with values like:

   ```env
   OLLAMA_MODEL=gpt-oss:20b
   OLLAMA_API_KEY=your_api_key
   OLLAMA_BASE_URL=https://ollama.com/v1
   ```

5. If you are using Ollama locally instead, set:

   ```env
   OLLAMA_BASE_URL=http://localhost:11434/v1
   OLLAMA_API_KEY=unused
   ```

## Run the CLI version

```bash
python app.py
```

Then type a prompt in the terminal, such as:

```text
Search for the latest developments in agentic AI?
```

Type `exit` or `quit` to stop.

## Run the web frontend

```bash
python web_app.py
```

Then open:

```text
http://localhost:5000
```

Use the browser chat UI to interact with the same agent system.

## Project files

- `app.py` — terminal-based multi-agent orchestration
- `web_app.py` — Flask frontend server
- `templates/index.html` — browser chat UI
- `static/style.css` — styling
- `static/script.js` — frontend behavior
- `.env` — environment configuration

## Troubleshooting

- If the app fails to route to agents, make sure the model endpoint is reachable.
- If the browser UI does not load, confirm Flask is installed.
- If you get import errors, install dependencies again in the active environment.
