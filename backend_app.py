from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.agent import Agent
from agno.run.agent import RunOutput
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.vectordb.chroma import ChromaDb
from agno.knowledge.chunking.document import DocumentChunking
from agno.db.sqlite.sqlite import SqliteDb
from agno.models.anthropic import Claude
from flask import Flask, request, jsonify
import anthropic
import base64
import json
import re
import traceback
import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

os.makedirs("database_files", exist_ok=True)

agent_db = SqliteDb(
    db_file="database_files/agent_storage.db",
    session_table="agent_sessions",
    memory_table="memories",
)

openai_embedder = OpenAIEmbedder(id="text-embedding-3-large", api_key=OPENAI_API_KEY)

knowledge_base = Knowledge(
    vector_db=ChromaDb(
        collection="insurance_customers_details",
        path="database_files/insurance_data",
        persistent_client=True,
        embedder=openai_embedder,
    ),
    readers={"pdf": PDFReader(chunking_strategy=DocumentChunking())},
)

with open("agent_instructions.txt", "r", encoding="utf-8") as f:
    agent_instructions = f.read()

agent = Agent(
    model=Claude(id="claude-sonnet-4-5", api_key=ANTHROPIC_API_KEY),
    db=agent_db,
    knowledge=knowledge_base,
    search_knowledge=True,
    add_history_to_context=True,
    num_history_runs=3,
    enable_user_memories=True,
    enable_session_summaries=True,
    read_chat_history=True,
    read_tool_call_history=True,
    enable_agentic_memory=True,
    debug_mode=True,
    instructions=agent_instructions,
)

app = Flask(__name__)


@app.route("/query", methods=["POST"])
def handle_query():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    user_input = data.get("user_input")
    user_id = data.get("user_id", "default_user")

    if not user_input:
        return jsonify({"error": "Missing user_input"}), 400

    print(f"Received user input from user '{user_id}': '{user_input}'")

    try:
        response: RunOutput = agent.run(user_input, user_id=user_id)

        if response and hasattr(response, "content"):
            agent_response_text = response.content
        else:
            agent_response_text = "No response content found."
            print(f"Warning: No 'content' attribute in RunResponse: {response}")

        return jsonify({"response": agent_response_text})

    except Exception as e:
        error_message = traceback.format_exc()
        print(f"Error in handle_query: {error_message}")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500


DAMAGE_ANALYSIS_PROMPT = """You are an expert automotive damage assessor with 20+ years of experience in vehicle repair and insurance claims.

Analyze this vehicle damage photo and return a JSON object with this exact structure:
{
  "vehicle_description": "brief description of vehicle and overall condition",
  "overall_severity": "low|medium|high|critical",
  "confidence": 0.0-1.0,
  "damaged_parts": [
    {
      "part": "part name in English",
      "severity": "low|medium|high|critical",
      "description": "what exactly is damaged",
      "repair_type": "repair|replace|paint|align",
      "cost_min": integer USD,
      "cost_max": integer USD
    }
  ],
  "total_cost_min": integer USD,
  "total_cost_max": integer USD,
  "repair_time_days": "X-Y days",
  "can_drive": true or false,
  "safety_concerns": ["list any safety issues"],
  "recommendations": ["actionable next steps"]
}

Rules:
- List every visibly damaged part separately
- Cost estimates must be realistic USD market rates (US/Europe)
- severity: low=minor scratches, medium=dents/moderate damage, high=structural/major, critical=totaled
- can_drive=false if airbags deployed, frame bent, or wheels/steering damaged
- Return ONLY the JSON, no other text"""


@app.route("/analyze-damage", methods=["POST"])
def analyze_damage():
    data = request.get_json()
    if not data or "image_b64" not in data:
        return jsonify({"error": "Missing image_b64"}), 400

    image_b64 = data["image_b64"]
    media_type = data.get("media_type", "image/jpeg")

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": DAMAGE_ANALYSIS_PROMPT},
                    ],
                }
            ],
        )

        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        result = json.loads(raw)
        return jsonify(result)

    except json.JSONDecodeError as e:
        return jsonify({"error": "Model returned invalid JSON", "details": str(e)}), 500
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": "Analysis failed", "details": str(e)}), 500


if __name__ == "__main__":
    # Load PDFs from data/ folder into knowledge base (skip existing on subsequent runs)
    if os.path.isdir("data") and any(f.endswith(".pdf") for f in os.listdir("data")):
        knowledge_base.insert(path="data", skip_if_exists=True)
    app.run(debug=True, port=8000)
