from agno.embedder.openai import OpenAIEmbedder
from agno.agent import Agent, RunResponse
from agno.knowledge.pdf import PDFKnowledgeBase
from agno.vectordb.chroma import ChromaDb
from agno.document.chunking.document import DocumentChunking
from agno.storage.sqlite import SqliteStorage
from agno.models.anthropic import Claude
from agno.memory.v2 import Memory
from agno.memory.v2.db.sqlite import SqliteMemoryDb
from flask import Flask, request, jsonify
import traceback
import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

agent_storage = SqliteStorage(
    table_name="agent_sessions",
    db_file="database_files/agent_storage.db",
    auto_upgrade_schema=True,
)

memory_db = SqliteMemoryDb(
    table_name="memories",
    db_file="database_files/memory.db",
)

openai_embedder = OpenAIEmbedder(id="text-embedding-3-large", api_key=OPENAI_API_KEY)

knowledge_base = PDFKnowledgeBase(
    path="data",
    vector_db=ChromaDb(
        collection="insurance_customers_details",
        path="database_files/insurance_data",
        persistent_client=True,
        embedder=openai_embedder,
    ),
    chunking_strategy=DocumentChunking(),
)

with open("agent_instructions.txt", "r", encoding="utf-8") as f:
    agent_instructions = f.read()

agent = Agent(
    model=Claude(id="claude-sonnet-4-5", api_key=ANTHROPIC_API_KEY),
    memory=Memory(db=memory_db),
    storage=agent_storage,
    knowledge=knowledge_base,
    search_knowledge=True,
    show_tool_calls=True,
    add_history_to_messages=True,
    num_history_runs=3,
    num_history_responses=3,
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
        response: RunResponse = agent.run(user_input, user_id=user_id)

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


if __name__ == "__main__":
    # Comment out after the first run once knowledge base is loaded
    knowledge_base.load(recreate=False, skip_existing=True)
    app.run(debug=True, port=8000)
