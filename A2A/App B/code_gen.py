import os
import json
import streamlit as st
import tempfile
import zipfile
from pathlib import Path
from crewai import Agent, Task
from litellm import completion
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure DeepSeek
LITELLM_API_BASE = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek/deepseek-coder"

# Streamlit UI setup
st.set_page_config(page_title="Spring Boot Boilerplate Generator", layout="wide", page_icon="🧩")
st.title("🧩 Java Boilerplate Code Generator (App B)")

# Sidebar input
api_key = st.sidebar.text_input("🔐 Enter your DeepSeek API Key", type="password")
uploaded_json = st.file_uploader("📥 Upload JSON from App A (java_documentation.json)", type="json")

# Create the Boilerplate Agent
def create_boilerplate_agent(api_key: str):
    return Agent(
        role="Spring Boot Code Generator",
        goal="Generate Java boilerplate code (Controller, Service, DTOs) from JSON input",
        backstory="""
        You're an expert in Spring Boot and help developers by creating clean, consistent code 
        from structured specifications. You always follow modern Java best practices.
        """,
        verbose=True,
        llm={
            "model": DEFAULT_MODEL,
            "api_key": api_key,
            "base_url": LITELLM_API_BASE,
            "temperature": 0.2
        }
    )

# Code generation function
def generate_code_from_json(api_key: str, file_json: dict):
    generated_files = {}
    
    agent = create_boilerplate_agent(api_key)

    for file_path, content in file_json.items():
        class_name = Path(file_path).stem

        task = Task(
            description=f"""
            You're given the following documentation extracted from a Java file:

            File: {file_path}

            Documentation:
            {content}

            Based on this, generate:
            1. A Spring Boot Controller class
            2. A Service Interface and Implementation
            3. Optional DTO classes if required

            Requirements:
            - Use standard Java naming conventions
            - Include method stubs and class annotations
            - Follow typical Spring structure
            - Keep each class in a separate file
            - Respond only with code in ```java blocks per file

            """,
            expected_output="Java code files with correct structure and annotations",
            agent=agent
        )

        try:
            response = completion(
                model=DEFAULT_MODEL,
                messages=[{"role": "user", "content": task.description}],
                api_key=api_key,
                base_url=LITELLM_API_BASE
            )

            generated_files[class_name] = response.choices[0].message.content

        except Exception as e:
            logger.error(f"Generation failed for {file_path}: {str(e)}")
            generated_files[class_name] = f"Error: {str(e)}"

    return generated_files

# Save generated files as a zip
def save_to_zip(file_dict):
    tmp_zip_path = tempfile.NamedTemporaryFile(delete=False, suffix=".zip").name
    with zipfile.ZipFile(tmp_zip_path, 'w') as zipf:
        for filename, content in file_dict.items():
            cleaned_name = filename.replace(".java", "").replace(" ", "_")
            java_files = extract_java_files(content)
            for i, (name, code) in enumerate(java_files):
                zipf.writestr(f"{cleaned_name}_{name}.java", code)
    return tmp_zip_path

# Extract ```java blocks
def extract_java_files(text):
    import re
    blocks = re.findall(r"```java(.*?)```", text, re.DOTALL)
    files = []
    for block in blocks:
        first_line = block.strip().splitlines()[0]
        class_name = first_line.split()[-1] if "class" in first_line else f"File_{len(files)}"
        files.append((class_name, block.strip()))
    return files

# Main logic
if uploaded_json and api_key:
    st.success("✅ JSON uploaded and API key provided.")
    json_data = json.load(uploaded_json)

    if st.button("🚀 Generate Boilerplate Code"):
        with st.spinner("Generating boilerplate using DeepSeek..."):
            result = generate_code_from_json(api_key, json_data)
            zip_path = save_to_zip(result)

            # Show generated files
            st.subheader("📄 Generated Code Files")
            for filename, content in result.items():
                st.markdown(f"### `{filename}`")
                st.code(content, language="java")

            # Download link
            with open(zip_path, "rb") as f:
                st.download_button("💾 Download All Code as ZIP", data=f, file_name="spring_boot_code.zip")

else:
    st.info("Please upload the JSON from App A and provide your DeepSeek API key.")

# Footer
st.markdown("---")
st.caption("🔧 This tool uses DeepSeek LLM to generate Spring Boot boilerplate from JSON class definitions.")
