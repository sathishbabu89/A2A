import os
import streamlit as st
import logging
import zipfile
import tempfile
import shutil
import traceback
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from crewai import Agent, Task
import litellm
from litellm import completion

# Configure LiteLLM for DeepSeek
litellm.drop_params = True
litellm.api_base = "https://api.deepseek.com/v1"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_MODEL = "deepseek/deepseek-coder"

class FileProcessor:
    """Handles all file operations including upload, extraction and content reading"""
    
    @staticmethod
    def save_uploaded_file(uploaded_file) -> Optional[str]:
        """Save uploaded zip file to temporary location"""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                return tmp_file.name
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            return None
    
    @staticmethod
    def extract_zip(zip_path: str, extract_to: str) -> bool:
        """Extract zip file to specified directory"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            return True
        except Exception as e:
            logger.error(f"Error extracting zip: {e}")
            return False
    
    @staticmethod
    def find_java_files(code_dir: str) -> List[str]:
        """Recursively find all Java files in directory"""
        return [
            os.path.join(root, file)
            for root, _, files in os.walk(code_dir)
            for file in files 
            if file.endswith('.java')
        ]
    
    @staticmethod
    def read_file_content(file_path: str) -> Optional[str]:
        """Read content of a file with proper error handling"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return None
    
    @staticmethod
    def combine_file_contents(files: List[str]) -> str:
        """Combine contents of multiple files for architecture analysis"""
        combined = []
        for file in files:
            if content := FileProcessor.read_file_content(file):
                combined.append(f"=== File: {file} ===\n{content}\n")
        return "\n".join(combined)

class DocumentationGenerator:
    """Core documentation generation functionality"""
    
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model
        self.agent = self._create_agent()
    
    def _create_agent(self) -> Agent:
        """Create and configure the documentation agent"""
        return Agent(
            role="Senior Java Documentation Specialist",
            goal="Generate excellent documentation for Java codebases",
            backstory=(
                "You are an expert Java developer with extensive experience "
                "creating clear, maintainable documentation for complex "
                "enterprise systems."
            ),
            verbose=True,
            llm=self._get_llm_config()
        )
    
    def _get_llm_config(self) -> Dict:
        """Get LLM configuration for DeepSeek"""
        return {
            "model": self.model,
            "api_key": self.api_key,
            "base_url": "https://api.deepseek.com/v1",
            "temperature": 0.2,
        }
    
    def _generate_docs(self, prompt: str) -> Optional[str]:
        """Execute LLM call with proper error handling"""
        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                api_key=self.api_key,
                base_url="https://api.deepseek.com/v1"
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Documentation generation failed: {traceback.format_exc()}")
            st.error(f"Error generating documentation: {str(e)}")
            return None
    
    def generate_basic_docs(self, code: str, file_path: str) -> Optional[str]:
        """Generate concise documentation"""
        prompt = f"""
        Provide concise documentation for this Java file:
        File: {file_path}
        Code:
        {code}
        
        Include:
        1. One-sentence file purpose
        2. Brief class overview
        3. List of public methods with one-line descriptions
        
        Format as bullet points.
        """
        return self._generate_docs(prompt)
    
    def generate_detailed_docs(self, code: str, file_path: str) -> Optional[str]:
        """Generate comprehensive documentation"""
        prompt = f"""
        Analyze and thoroughly document this Java file:
        File: {file_path}
        Code:
        {code}
        
        Include:
        1. File purpose and responsibilities
        2. Complete class documentation
        3. Detailed method documentation
        4. Important field documentation
        5. Usage examples
        
        Use Markdown with clear sections.
        """
        return self._generate_docs(prompt)
    
    def generate_architecture_docs(self, combined_code: str) -> Optional[str]:
        """Generate high-level architecture documentation"""
        prompt = f"""
        Analyze this Java codebase and generate comprehensive architecture documentation:
        
        {combined_code}
        
        Include:
        1. System Overview
           - Purpose and scope
           - High-level architecture diagram (in Mermaid syntax)
           - Major components and their interactions
        
        2. Module Structure
           - Module decomposition
           - Dependency graph
           - Architectural patterns used
        
        3. Cross-Cutting Concerns
           - Security approach
           - Error handling strategy
           - Logging methodology
        
        4. Integration Patterns
           - External system integrations
           - API design approach
           - Data flow diagrams
        
        5. Deployment Architecture
           - Runtime requirements
           - Infrastructure dependencies
        
        Provide the documentation in Markdown format suitable for technical architects.
        Include visual diagrams in Mermaid syntax where appropriate.
        """
        return self._generate_docs(prompt)

class AppState:
    """Manages application state and session variables"""
    
    @staticmethod
    def initialize():
        """Initialize all required session state variables"""
        defaults = {
            'documentation': {},
            'architecture_docs': None,
            'extracted_path': "",
            'processing': False,
            'progress': 0,
            'api_checked': False,
            'view_mode': 'files'  # 'files' or 'architecture'
        }
        for key, val in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = val
    
    @staticmethod
    def cleanup():
        """Clean up temporary files and reset state"""
        if st.session_state.extracted_path:
            try:
                shutil.rmtree(st.session_state.extracted_path)
            except Exception as e:
                logger.warning(f"Cleanup failed: {e}")
        st.session_state.processing = False
        st.session_state.progress = 0

class UI:
    """Handles all user interface components"""
    
    @staticmethod
    def setup_page():
        """Configure the Streamlit page"""
        st.set_page_config(
            page_title="Java Code Documentation Generator",
            layout="wide",
            page_icon="📝"
        )
        st.header("Java Code Documentation Generator")
    
    @staticmethod
    def setup_sidebar() -> str:
        """Configure and return API key from sidebar"""
        st.sidebar.header("Configuration")
        return st.sidebar.text_input(
            "DeepSeek API Key",
            type="password",
            help="Enter your DeepSeek API key"
        )
    
    @staticmethod
    def show_file_uploader() -> Optional[st.runtime.uploaded_file_manager.UploadedFile]:
        """Display file uploader and return uploaded file"""
        return st.file_uploader(
            "Upload your Java codebase (ZIP file)",
            type="zip"
        )
    
    @staticmethod
    def show_generation_options() -> Tuple[bool, bool, bool]:
        """Display documentation options and return button states"""
        col1, col2, col3 = st.columns(3)
        with col1:
            basic = st.button("📝 Basic Docs")
        with col2:
            detailed = st.button("🔍 Detailed Docs")
        with col3:
            architecture = st.button("🏛️ Architecture Docs")
        return basic, detailed, architecture
    
    @staticmethod
    def show_view_toggle():
        """Toggle between file docs and architecture docs view"""
        if st.session_state.architecture_docs:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("View File Documentation"):
                    st.session_state.view_mode = 'files'
            with col2:
                if st.button("View Architecture Documentation"):
                    st.session_state.view_mode = 'architecture'
    
    @staticmethod
    def show_progress(current: int, total: int):
        """Update progress display"""
        progress = current / total if total > 0 else 0
        st.session_state.progress = progress
        st.progress(progress)
        st.caption(f"Processing {current} of {total} items")
    
    @staticmethod
    def show_file_documentation():
        """Display file-level documentation"""
        if not st.session_state.documentation:
            st.info("No file documentation generated yet")
            return
        
        st.subheader("File Documentation")
        st.metric("Files Documented", len(st.session_state.documentation))
        
        tabs = st.tabs([Path(f).name for f in st.session_state.documentation])
        for tab, (path, docs) in zip(tabs, st.session_state.documentation.items()):
            with tab:
                st.markdown(f"### `{path}`")
                st.markdown(docs if docs else "*No documentation generated*")
    
    @staticmethod
    def show_architecture_documentation():
        """Display architecture documentation"""
        if not st.session_state.architecture_docs:
            st.info("No architecture documentation generated yet")
            return
        
        st.subheader("Architecture Documentation")
        st.markdown(st.session_state.architecture_docs)

def process_codebase(api_key: str, files: List[str], gen_func) -> Dict[str, str]:
    """Process all Java files using specified documentation function"""
    docs = {}
    generator = DocumentationGenerator(api_key)
    
    for i, file in enumerate(files, 1):
        UI.show_progress(i, len(files))
        if content := FileProcessor.read_file_content(file):
            docs[file] = gen_func(content, file)
    
    return docs

def generate_architecture_docs(api_key: str, files: List[str]) -> Optional[str]:
    """Generate architecture documentation for the entire codebase"""
    generator = DocumentationGenerator(api_key)
    combined_code = FileProcessor.combine_file_contents(files)
    return generator.generate_architecture_docs(combined_code)

def main():
    """Main application flow"""
    UI.setup_page()
    AppState.initialize()
    
    api_key = UI.setup_sidebar()
    uploaded_file = UI.show_file_uploader()
    basic_btn, detailed_btn, arch_btn = UI.show_generation_options()
    
    if uploaded_file and api_key and (basic_btn or detailed_btn or arch_btn):
        with st.spinner("Processing codebase..."):
            # Save and extract uploaded file
            zip_path = FileProcessor.save_uploaded_file(uploaded_file)
            extract_dir = tempfile.mkdtemp()
            
            if FileProcessor.extract_zip(zip_path, extract_dir):
                st.session_state.extracted_path = extract_dir
                java_files = FileProcessor.find_java_files(extract_dir)
                
                if java_files:
                    st.session_state.processing = True
                    
                    if basic_btn:
                        st.session_state.documentation = process_codebase(
                            api_key, java_files, 
                            DocumentationGenerator(api_key).generate_basic_docs
                        )
                    elif detailed_btn:
                        st.session_state.documentation = process_codebase(
                            api_key, java_files,
                            DocumentationGenerator(api_key).generate_detailed_docs
                        )
                    elif arch_btn:
                        st.session_state.architecture_docs = generate_architecture_docs(
                            api_key, java_files
                        )
                    
                    st.balloons()
                    st.success("Documentation generated successfully!")
                else:
                    st.error("No Java files found in uploaded codebase")
    
    UI.show_view_toggle()
    
    if st.session_state.view_mode == 'files':
        UI.show_file_documentation()
    else:
        UI.show_architecture_documentation()
    
    AppState.cleanup()

if __name__ == "__main__":
    main()