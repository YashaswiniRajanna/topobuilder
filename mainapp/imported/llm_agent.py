# llm_agent.py

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from rapidfuzz import process, fuzz
import re
import subprocess
from .config import api_key, detailed_prompt

# --- LLM setup ---
llm = ChatOpenAI(
    model="gpt-4.1",
    base_url="https://cxai-playground.cisco.com",
    openai_api_key=api_key,
    temperature=0.7,
    streaming=False
)

tools = []

# --- Create LangGraph ReAct Agent ---
agent_executor = create_react_agent(
    model=llm,
    tools=tools,
    prompt=detailed_prompt
)

def clean_version_in_input(user_input):
    known_versions = ["7.11.21", "25.4", "24.4", "24.2"]
    possible_versions = re.findall(r'[\d][\d\.\-_l]{0,5}', user_input.lower())
    user_input_cleaned = user_input
    for candidate in possible_versions:
        match, score, _ = process.extractOne(candidate, known_versions, scorer=fuzz.ratio)
        if score > 75:
            user_input_cleaned = re.sub(re.escape(candidate), match, user_input_cleaned, count=1)
    return user_input_cleaned

def get_yaml(messages):
    result = agent_executor.invoke({"messages": messages})
    return result["messages"][-1].content

def deploy_and_graph():
    deploy_cmd = ["containerlab", "deploy", "-t", "current_lab.yml"]
    try:
        print("[DEBUG] Deploying the lab...")
        deploy_result = subprocess.run(deploy_cmd, capture_output=True, text=True, check=True)
        print(deploy_result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error during deploy: {e.stderr}")
        return
    # No graph command or debug message here!

def destroy_lab():
    destroy_cmd = ["containerlab", "destroy", "-t", "current_lab.yml", "--cleanup"]
    try:
        print("[DEBUG] Destroying the lab and cleaning up resources...")
        result = subprocess.run(destroy_cmd, capture_output=True, text=True, check=True)
        print(result.stdout)
        print("Lab destroyed and cleaned up successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error during destroy: {e.stderr}")

def is_delete_lab_intent(user_input):
    return user_input.strip().lower() == "delete the lab"