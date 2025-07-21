# rca_contextual_analysis.py

from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_groq import ChatGroq
import json
import os

RCA_PROMPT_TEMPLATE = """
You are a cloud infrastructure expert skilled in analyzing OpenStack logs and finding root causes of anomalies. You are given:

1. An anomalous log line that was flagged by a machine learning model.
2. A log sequence — a list of log templates leading up to the anomaly.
3. A raw log window — actual log lines before and after the anomaly.

Your job is to:
- Identify possible causes of the anomaly.
- Suggest where the issue might have originated.
- Keep it concise, technical, and actionable.

---

🔴 Suspicious Log Line:
"{anomaly_line}"

🧩 Log Sequence (Template Pattern):
"{log_sequence}"

📜 Raw Log Context:
{log_window_text}

---

Please explain the likely root cause or contributing factors, even if speculative.
Respond in this JSON format:

{{
  "anomaly_cause": "...",
  "affected_component": "...",
  "severity": "low | medium | high",
  "suggested_action": "..."
}}
"""

CHAT_PROMPT_TEMPLATE = """
You are a cloud infrastructure expert who has just analyzed an OpenStack log anomaly. Here's the context of your previous analysis:

ORIGINAL ANALYSIS:
🔴 Suspicious Log Line: "{anomaly_line}"
🧩 Log Sequence: "{log_sequence}"
📜 Raw Log Context: {log_window_text}

PREVIOUS ANALYSIS RESULT:
{previous_analysis}

CONVERSATION HISTORY:
{chat_history}

USER QUESTION: {user_question}

Please provide a helpful, technical response based on your expertise and the context above. Keep responses concise and actionable.
"""


class RCAAnalyzer:
    def __init__(self, model_name="llama3-8b-8192", api_key=None):
        """
        Initialize RCA Analyzer with ChatGroq
        
        Args:
            model_name (str): Groq model name (default: "llama3-8b-8192")
                Available models: "llama3-8b-8192", "llama3-70b-8192", "mixtral-8x7b-32768", "gemma-7b-it"
            api_key (str): Groq API key. If None, will look for GROQ_API_KEY environment variable
        """
        # Set up API key
        
        if api_key:
            os.environ["GROQ_API_KEY"] = api_key
        elif not os.getenv("GROQ_API_KEY"):
            raise ValueError(
                "Groq API key is required. Either pass it as 'api_key' parameter or set GROQ_API_KEY environment variable.\n"
                "You can get an API key from: https://console.groq.com/keys"
            )
        
        # Initialize ChatGroq
        print(f"Initializing ChatGroq with model: {model_name}")
        self.llm = ChatGroq(
            model=model_name,
            temperature=0.3,  # Lower temperature for more consistent analysis
            max_tokens=1024,
            timeout=60,
            max_retries=2
        )
        
        # Create chains
        self.rca_prompt = PromptTemplate.from_template(RCA_PROMPT_TEMPLATE)
        self.chat_prompt = PromptTemplate.from_template(CHAT_PROMPT_TEMPLATE)
        
        self.rca_chain = self.rca_prompt | self.llm
        self.chat_chain = self.chat_prompt | self.llm
        
        # Store analysis context
        self.analysis_context = {}
        self.chat_history = []
        
    def contextual_analysis(self, anomaly_line: str, log_sequence: str, log_window_text: str) -> dict:
        """Perform initial RCA analysis"""
        MAX_LOG_WINDOW_CHARS = 3000  # Increased limit for Groq models
        if len(log_window_text) > MAX_LOG_WINDOW_CHARS:
            log_window_text = log_window_text[-MAX_LOG_WINDOW_CHARS:]
            
        input_vars = {
            "anomaly_line": anomaly_line,
            "log_sequence": log_sequence,
            "log_window_text": log_window_text
        }
        
        # Store context for chat
        self.analysis_context = input_vars.copy()
        
        print("Analyzing logs with ChatGroq...")
        try:
            response = self.rca_chain.invoke(input_vars)
            
            # Extract content from the response
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Try to parse JSON response
            # Look for JSON content within the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_content = response_text[json_start:json_end]
                analysis_result = json.loads(json_content)
                self.analysis_context["previous_analysis"] = json.dumps(analysis_result, indent=2)
                return analysis_result
            else:
                # If no JSON found, return the raw response
                self.analysis_context["previous_analysis"] = response_text
                return {"raw_output": response_text, "note": "Could not parse JSON format"}
                
        except json.JSONDecodeError as e:
            # If JSON parsing fails, store raw response
            self.analysis_context["previous_analysis"] = response_text
            return {"raw_output": response_text, "json_error": str(e)}
        except Exception as e:
            return {"error": f"Analysis failed: {str(e)}"}
    
    def chat(self, user_question: str) -> str:
        """Continue conversation about the analysis"""
        if not self.analysis_context:
            return "Please run contextual_analysis first to establish context for the chat."
        
        # Add user question to history
        self.chat_history.append(f"User: {user_question}")
        
        # Prepare chat history string (keep last 10 exchanges to manage token limits)
        chat_history_str = "\n".join(self.chat_history[-10:])
        
        input_vars = {
            **self.analysis_context,
            "chat_history": chat_history_str,
            "user_question": user_question
        }
        
        try:
            response = self.chat_chain.invoke(input_vars)
            
            # Extract content from the response
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Clean up response (remove any prompt repetition)
            response_text = response_text.strip()
            if "USER QUESTION:" in response_text:
                response_text = response_text.split("USER QUESTION:")[-1].strip()
            
            # Add assistant response to history
            self.chat_history.append(f"Assistant: {response_text}")
            
            return response_text
            
        except Exception as e:
            return f"Error during chat: {str(e)}"
    
    def start_interactive_session(self):
        """Start interactive chat session"""
        if not self.analysis_context:
            print("No analysis context available. Please run contextual_analysis first.")
            return
        
        print("\n" + "="*60)
        print("🤖 INTERACTIVE RCA CHAT SESSION STARTED")
        print("="*60)
        print("Ask me anything about the log analysis!")
        print("Type 'quit', 'exit', or 'bye' to end the session.")
        print("="*60 + "\n")
        
        while True:
            try:
                user_input = input("\n💬 Your question: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye', 'q']:
                    print("\n👋 Chat session ended. Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                print("\n🤖 Assistant:", end=" ")
                response = self.chat(user_input)
                print(response)
                
            except KeyboardInterrupt:
                print("\n\n👋 Chat session interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")


def interactive_contextual_analysis(anomaly_line: str,  log_sequence: str, log_window_text: str, api_key=None) -> dict:
    """Legacy function for backward compatibility"""
   
    try:
        # Initialize analyzer with different model options:
        # "llama3-8b-8192" (fast, good balance)
        # "llama3-70b-8192" (more capable but slower)
        # "mixtral-8x7b-32768" (large context window)
        # "gemma-7b-it" (Google's Gemma model)
        
        analyzer = RCAAnalyzer(model_name="llama3-8b-8192")  # or pass api_key=api_key
        
        # Example log data
        anomaly_line = "ERROR nova.compute.manager Connection to libvirt lost: [Errno 104] Connection reset by peer"
        log_sequence = "compute.manager -> libvirt.driver -> connection.close"
        log_window_text = """
        2024-01-15 10:23:45 INFO nova.compute.manager Starting compute service
        2024-01-15 10:23:46 DEBUG libvirt.driver Connecting to hypervisor
        2024-01-15 10:23:47 ERROR nova.compute.manager Connection to libvirt lost: [Errno 104] Connection reset by peer
        2024-01-15 10:23:48 WARNING nova.compute.manager Attempting reconnection
        2024-01-15 10:23:49 ERROR nova.compute.manager Failed to reconnect to libvirt
        2024-01-15 10:23:50 CRITICAL nova.compute.manager Compute service degraded
        """
        
        # Perform initial analysis
        print("🔍 Performing RCA Analysis...")
        result = analyzer.contextual_analysis(anomaly_line, log_sequence, log_window_text)
        
        print("\n📋 ANALYSIS RESULT:")
        print("="*50)
        if "error" in result:
            print(f"Error: {result['error']}")
        elif "raw_output" in result:
            print(f"Raw Output: {result['raw_output']}")
            if "json_error" in result:
                print(f"JSON Parse Error: {result['json_error']}")
        else:
            for key, value in result.items():
                print(f"{key.replace('_', ' ').title()}: {value}")
        
        # Start interactive session
        analyzer.start_interactive_session()
        
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print("\nTo get started:")
        print("1. Sign up at https://console.groq.com/")
        print("2. Get your API key from https://console.groq.com/keys")
        print("3. Set environment variable: export GROQ_API_KEY='your_key_here'")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
    



# Example usage
if __name__ == "__main__":
    # You need to set your Groq API key
    # Option 1: Set environment variable
    # export GROQ_API_KEY="your_api_key_here"
    
    # Option 2: Pass directly (not recommended for production)
    # api_key = "your_api_key_here"
    
    try:
        # Initialize analyzer with different model options:
        # "llama3-8b-8192" (fast, good balance)
        # "llama3-70b-8192" (more capable but slower)
        # "mixtral-8x7b-32768" (large context window)
        # "gemma-7b-it" (Google's Gemma model)
        
        analyzer = RCAAnalyzer(model_name="llama3-8b-8192")  # or pass api_key=api_key
        
        # Example log data
        sample_anomaly = "ERROR nova.compute.manager Connection to libvirt lost: [Errno 104] Connection reset by peer"
        sample_sequence = "compute.manager -> libvirt.driver -> connection.close"
        sample_context = """
        2024-01-15 10:23:45 INFO nova.compute.manager Starting compute service
        2024-01-15 10:23:46 DEBUG libvirt.driver Connecting to hypervisor
        2024-01-15 10:23:47 ERROR nova.compute.manager Connection to libvirt lost: [Errno 104] Connection reset by peer
        2024-01-15 10:23:48 WARNING nova.compute.manager Attempting reconnection
        2024-01-15 10:23:49 ERROR nova.compute.manager Failed to reconnect to libvirt
        2024-01-15 10:23:50 CRITICAL nova.compute.manager Compute service degraded
        """
        
        # Perform initial analysis
        print("🔍 Performing RCA Analysis...")
        result = analyzer.contextual_analysis(sample_anomaly, sample_sequence, sample_context)
        
        print("\n📋 ANALYSIS RESULT:")
        print("="*50)
        if "error" in result:
            print(f"Error: {result['error']}")
        elif "raw_output" in result:
            print(f"Raw Output: {result['raw_output']}")
            if "json_error" in result:
                print(f"JSON Parse Error: {result['json_error']}")
        else:
            for key, value in result.items():
                print(f"{key.replace('_', ' ').title()}: {value}")
        
        # Start interactive session
        analyzer.start_interactive_session()
        
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print("\nTo get started:")
        print("1. Sign up at https://console.groq.com/")
        print("2. Get your API key from https://console.groq.com/keys")
        print("3. Set environment variable: export GROQ_API_KEY='your_key_here'")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")