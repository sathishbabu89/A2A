
# 📘 **Agent-to-Agent Code Generator System (A2A Architecture)**

### Automating Java Documentation, Boilerplate Code & JUnit Test Generation using Multi-Agent Collaboration

---

## 🧠 **Overview**

This project demonstrates a practical implementation of **Agent-to-Agent (A2A)** communication using open agent frameworks like **CrewAI** and LLMs from **DeepSeek**, backed by a microservice architecture and REST-based interaction.

The system is built as two cooperating applications:

* **App A** – *Java Code Documentation Generator*
* **App B** – *Boilerplate Code & Test Case Generator*

They **communicate via REST (A2A protocol-style)** to pass information and collaborate on tasks. App A serves as the *producer*, and App B acts as the *consumer and generator*.

---

## 🧩 **App A – Java Code Documentation Generator**

### 🔧 Functionality

* Accepts a **ZIP file** containing Java source code.
* Extracts and reads each `.java` file.
* Uses a **Documentation Agent** (LLM via CrewAI) to generate detailed, structured Markdown documentation for each file.
* Displays the documentation in the UI.
* Allows exporting:

  * As downloadable JSON (`java_documentation.json`)
  * Or sending to **App B** for code generation via REST (A2A).

### 🧠 Agent: `DocumentationAgent`

* **Role**: `Senior Java Documentation Specialist`
* **Goal**: Understand Java code and generate well-structured Markdown documentation.
* **LLM**: DeepSeek Coder (via LiteLLM)

### 📡 Integration with App B

* Sends the following payload to App B:

  ```json
  {
    "api_key": "<DeepSeek key>",
    "json_data": { <Java documentation JSON> },
    "generate_tests": true/false
  }
  ```

---

## 🧩 **App B – Spring Boot Code + JUnit Test Generator**

### 🔧 Functionality

* Accepts JSON documentation from App A via file upload or REST API (`/generate`).
* Based on user input, it can:

  * Generate **Spring Boot boilerplate code**
  * Optionally generate **JUnit 5 test cases**

### 🧠 Agent 1: `BoilerplateAgent`

* **Role**: `Spring Boot Code Generator`
* **Goal**: Generate Java Controller, Service, DTO classes from structured JSON.
* **LLM**: DeepSeek Coder

### 🧠 Agent 2: `TestCaseAgent`

* **Role**: `JUnit Test Case Generator`
* **Goal**: Generate JUnit 5 test classes (Controller + Service) using Mockito, covering success and failure flows.
* **LLM**: DeepSeek Coder

### 🔀 Multi-Agent Collaboration Flow

1. **BoilerplateAgent** reads the documentation and creates controller/service code.
2. If `generate_tests` is `True`, **TestCaseAgent** is triggered using the same input.
3. All generated code is organized and returned to App A or made available for ZIP download.

### 🛠 API Endpoint (`a2a_server.py`)

```http
POST /generate
Content-Type: application/json

{
  "api_key": "your-deepseek-key",
  "json_data": { ... },
  "generate_tests": true
}
```

---

## 🔁 **Agent-to-Agent (A2A) Protocol Architecture**

| Step | Action                                                                    |
| ---- | ------------------------------------------------------------------------- |
| 1.   | User uploads Java code to App A                                           |
| 2.   | App A extracts, processes, and generates JSON documentation               |
| 3.   | User optionally chooses to send data to App B                             |
| 4.   | App A POSTs data to App B (`/generate`)                                   |
| 5.   | App B processes using multi-agent logic (BoilerplateAgent, TestCaseAgent) |
| 6.   | Response is returned to App A and displayed or downloaded                 |

### 🔄 A2A Interaction Pattern

* Communication is achieved through a **standard JSON contract**.
* Flexible control over execution (test case generation toggle).
* Future-proof and modular (can scale to include more agents).

---

## 💡 Highlights & Innovations

✅ Real-world implementation of Agent2Agent microservice
✅ Multi-agent orchestration using CrewAI
✅ REST-based modular architecture
✅ Toggle-based functionality from UI
✅ Clean integration of LLM-based generation and automated testing

---

## 📁 Technologies Used

| Component       | Tech Stack                                                                          |
| --------------- | ----------------------------------------------------------------------------------- |
| UI              | Streamlit                                                                           |
| Backend         | Python, Flask                                                                       |
| Agent Framework | [CrewAI](https://github.com/joaomdmoura/crewai)                                     |
| LLM Provider    | [DeepSeek](https://deepseek.com/) via [LiteLLM](https://github.com/BerriAI/litellm) |
| Communication   | REST (custom A2A-style endpoint)                                                    |

---

## 🧪 Future Enhancements

* Agent memory or context sharing
* GitHub integration for input/output
* Swagger/OpenAPI export
* More agents: Security Review, Optimization, Logging Enhancer, etc.
* Use official [A2A Protocol](https://a2a-protocol.org/) standard message format

---

Let me know if you want this turned into:

* A downloadable **PDF/Markdown**
* A 3-slide **PowerPoint deck**
* A GitHub README template

Or want to present it to your leadership — I can help with a **demo script or talking points** too.
