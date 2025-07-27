import os
import streamlit as st
import logging
import zipfile
import tempfile
import shutil
import traceback
import json
from pathlib import Path
from typing import Optional
from crewai import Agent, Task
import litellm
from litellm import completion

# Configure LiteLLM specifically for DeepSeek
litellm.drop_params = True  # Ignore unsupported params
litellm.api_base = "https://api.deepseek.com/v1"  # Set DeepSeek API base URL

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set page configuration
st.set_page_config(
    page_title="Java Code Documentation Generator",
    layout="wide",
    page_icon="📝"
)

class FileProcessor:
    """Handles file uploads and processing"""
    
    @staticmethod
    def save_uploaded_file(uploaded_file):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                return tmp_file.name
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            return None
    
    @staticmethod
    def extract_zip(zip_path, extract_to):
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            return True
        except Exception as e:
            logger.error(f"Error extracting zip: {e}")
            return False
    
    @staticmethod
    def find_java_files(code_dir):
        """Find all Java files in the codebase"""
        java_files = []
        for root, _, files in os.walk(code_dir):
            for file in files:
                if file.endswith('.java'):
                    java_files.append(os.path.join(root, file))
        return java_files
    
    @staticmethod
    def read_file_content(file_path):
        """Read the content of a file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return None

class DocumentationGenerator:
    """Handles documentation generation using CrewAI"""
    
    def __init__(self, api_key: str, model: str = "deepseek/deepseek-coder"):
        self.api_key = api_key
        self.model = model
        self.documentation_agent = self._create_documentation_agent()
    
    def _create_documentation_agent(self):
        """Create the documentation agent"""
        return Agent(
            role="Senior Java Documentation Specialist",
            goal="Generate comprehensive documentation for Java codebases",
            backstory="""You are an expert Java developer with 10+ years of experience in creating 
            excellent documentation for enterprise Java applications. You specialize in understanding
            complex codebases and producing clear, concise documentation that helps developers
            understand and maintain the code.""",
            verbose=True,
            llm=self._create_deepseek_llm()
        )
    
    def _create_deepseek_llm(self):
        """Create a custom LLM configuration for DeepSeek"""
        return {
            "model": self.model,
            "api_key": self.api_key,
            "base_url": "https://api.deepseek.com/v1",
            "temperature": 0.2,
        }
    
    def generate_documentation(self, code_content: str, file_path: str) -> Optional[str]:
        """Generate documentation for a single Java file"""
        try:
            task = Task(
                description=f"""
                Analyze and document this Java file:
                File path: {file_path}
                Code content:
                {code_content}
                
                Generate comprehensive documentation including:
                1. File purpose and overall responsibility
                2. Class documentation with:
                   - Class responsibilities
                   - Important design decisions
                   - Thread safety considerations
                3. Method documentation for all public methods:
                   - Method purpose
                   - Parameters
                   - Return values
                   - Exceptions thrown
                   - Side effects
                4. Important field documentation
                5. Usage examples where appropriate
                
                Format the documentation in Markdown with clear sections.
                Include the original file path as a header.
                """,
                expected_output="Well-structured Markdown documentation for the Java file",
                agent=self.documentation_agent
            )
            
            # Explicitly use DeepSeek API
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": task.description}],
                api_key=self.api_key,
                base_url="https://api.deepseek.com/v1"
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Documentation generation failed for {file_path}: {traceback.format_exc()}")
            st.error(f"Error generating documentation: {str(e)}")
            return None

class SessionStateManager:
    """Manages session state variables"""
    
    @staticmethod
    def initialize():
        if 'documentation' not in st.session_state:
            st.session_state.documentation = {}
        if 'extracted_code_path' not in st.session_state:
            st.session_state.extracted_code_path = ""
        if 'processing_complete' not in st.session_state:
            st.session_state.processing_complete = False
        if 'progress' not in st.session_state:
            st.session_state.progress = 0

class UIComponents:
    """Handles the user interface components"""
    
    @staticmethod
    def setup_sidebar():
        """Configure the sidebar elements"""
        st.sidebar.header("Configuration")
        
        api_key = st.sidebar.text_input(
            "DeepSeek API Key",
            type="password",
            help="Enter your DeepSeek API key"
        )
        
        return api_key
    
    @staticmethod
    def show_progress(current: int, total: int):
        """Show progress bar"""
        progress = current / total if total > 0 else 0
        st.session_state.progress = progress
        st.progress(progress)
        st.caption(f"Processing {current} of {total} files...")
    
    @staticmethod
    def show_results():
        """Display the generated documentation"""
        if not st.session_state.documentation:
            st.info("Upload and process a Java codebase to view documentation.")
            return
        
        st.subheader("Generated Documentation")
        
        # Show summary stats
        col1, col2 = st.columns(2)
        col1.metric("Files Documented", len(st.session_state.documentation))
        
        # Create tabs for each file's documentation
        tabs = st.tabs([Path(f).name for f in st.session_state.documentation.keys()])
        
        for tab, (file_path, docs) in zip(tabs, st.session_state.documentation.items()):
            with tab:
                if docs:
                    st.markdown(f"### {file_path}")
                    st.markdown(docs)
                else:
                    st.warning("No documentation generated for this file.")

# Initialize session state
SessionStateManager.initialize()

# Setup sidebar
api_key = UIComponents.setup_sidebar()

# Main file uploader
st.header("Upload Java Codebase")
uploaded_file = st.file_uploader(
    "Choose a ZIP file containing your Java codebase",
    type="zip"
)

# Process uploaded file
if uploaded_file is not None and not st.session_state.processing_complete:
    with st.spinner("Processing uploaded file..."):
        # Save the uploaded file
        zip_path = FileProcessor.save_uploaded_file(uploaded_file)
        
        # Create temp directory for extraction
        extract_dir = tempfile.mkdtemp()
        st.session_state.extracted_code_path = extract_dir
        
        # Extract the zip file
        if FileProcessor.extract_zip(zip_path, extract_dir):
            st.success("File uploaded and extracted successfully!")
            
            # Find all Java files
            java_files = FileProcessor.find_java_files(extract_dir)
            
            if java_files:
                st.success(f"Found {len(java_files)} Java files in the codebase.")
                
                if api_key:
                    if st.button("Generate Documentation"):
                        generator = DocumentationGenerator(api_key)
                        total_files = len(java_files)
                        
                        for i, java_file in enumerate(java_files):
                            UIComponents.show_progress(i+1, total_files)
                            
                            # Read file content
                            content = FileProcessor.read_file_content(java_file)
                            if content:
                                # Generate documentation
                                docs = generator.generate_documentation(content, java_file)
                                st.session_state.documentation[java_file] = docs
                            
                        st.session_state.processing_complete = True
                        st.balloons()
                        st.success("Documentation generation complete!")
                else:
                    st.error("Please enter a DeepSeek API key to generate documentation")
            else:
                st.error("No Java files found in the uploaded codebase")

# Display results if processing is complete
if st.session_state.processing_complete:
    UIComponents.show_results()
    st.markdown("### 💾 Export Documentation for Chatbot")
    st.download_button(
    label="Download JSON for Chatbot (App B)",
    data=json.dumps(st.session_state.documentation, indent=2),
    file_name="java_documentation.json",
    mime="application/json"
)

# Cleanup temp files on app rerun
if 'extracted_code_path' in st.session_state and st.session_state.extracted_code_path:
    try:
        shutil.rmtree(st.session_state.extracted_code_path)
    except Exception as e:
        logger.warning(f"Could not cleanup temp dir: {e}")

# Footer
st.markdown("---")
st.markdown("""
**Note**: This tool uses AI to generate documentation for Java codebases.
Always review generated documentation for accuracy and completeness.
""")