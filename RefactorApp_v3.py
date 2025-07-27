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

# Configure LiteLLM for DeepSeek with more robust settings
litellm.drop_params = True
litellm.api_base = "https://api.deepseek.com/v1"
litellm.set_verbose = False  # Reduce verbose logging

# Configure logging to suppress unnecessary LiteLLM logs
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger("litellm").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Constants
DEFAULT_MODEL = "deepseek/deepseek-coder"

class FileProcessor:
    """Handles all file operations with improved error handling"""
    
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
        """Extract zip file with better cleanup handling"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            return True
        except Exception as e:
            logger.error(f"Error extracting zip: {e}")
            return False
        finally:
            try:
                os.unlink(zip_path)
            except:
                pass
    
    @staticmethod
    def find_java_files(code_dir: str) -> List[str]:
        """Recursively find Java files with existence check"""
        if not os.path.exists(code_dir):
            return []
        return [
            os.path.join(root, file)
            for root, _, files in os.walk(code_dir)
            for file in files 
            if file.endswith('.java')
        ]
    
    @staticmethod
    def read_file_content(file_path: str) -> Optional[str]:
        """Read file content with encoding fallback"""
        try:
            for encoding in ['utf-8', 'latin-1', 'iso-8859-1']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            return None
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return None
    
    @staticmethod
    def combine_file_contents(files: List[str]) -> str:
        """Combine file contents with size limit"""
        combined = []
        max_size = 500000  # ~500KB to avoid hitting API limits
        current_size = 0
        
        for file in files:
            if content := FileProcessor.read_file_content(file):
                file_content = f"=== File: {file} ===\n{content}\n"
                if current_size + len(file_content) > max_size:
                    break
                combined.append(file_content)
                current_size += len(file_content)
        
        return "\n".join(combined)

class DocumentationGenerator:
    """Documentation generator with improved error handling"""
    
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model
        self.agent = self._create_agent()
    
    def _create_agent(self) -> Agent:
        """Create agent with timeout settings"""
        return Agent(
            role="Senior Java Documentation Specialist",
            goal="Generate excellent documentation",
            backstory="Expert in Java documentation",
            verbose=False,  # Reduce verbosity
            llm=self._get_llm_config(),
            max_iter=5,  # Limit iterations
            max_execution_time=120  # 2 minute timeout
        )
    
    def _get_llm_config(self) -> Dict:
        """Get LLM config with timeout settings"""
        return {
            "model": self.model,
            "api_key": self.api_key,
            "base_url": "https://api.deepseek.com/v1",
            "temperature": 0.2,
            "request_timeout": 60,  # 60 second timeout
        }
    
    def _generate_docs(self, prompt: str) -> Optional[str]:
        """Generate docs with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = completion(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    api_key=self.api_key,
                    base_url="https://api.deepseek.com/v1",
                    timeout=60
                )
                return response.choices[0].message.content
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Final attempt failed: {traceback.format_exc()}")
                    st.error(f"Documentation generation failed after {max_retries} attempts")
                else:
                    logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                    time.sleep(2)  # Wait before retry
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
    """State management with better cleanup"""
    
    @staticmethod
    def initialize():
        defaults = {
            'documentation': {},
            'architecture_docs': None,
            'extracted_path': "",
            'processing': False,
            'progress': 0,
            'view_mode': 'files'
        }
        for key, val in defaults.items():
            st.session_state.setdefault(key, val)
    
    @staticmethod
    def cleanup():
        """More robust cleanup method"""
        if 'extracted_path' in st.session_state and st.session_state.extracted_path:
            try:
                if os.path.exists(st.session_state.extracted_path):
                    shutil.rmtree(st.session_state.extracted_path, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Cleanup warning: {e}")
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
    import time
    time.sleep(1)  # Small delay to help with streamlit initialization
    main()