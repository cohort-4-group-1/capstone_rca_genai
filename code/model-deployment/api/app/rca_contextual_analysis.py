# rca_contextual_analysis.py

from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_community.llms import HuggingFacePipeline
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import json

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


# Load model once
model_id = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id)
hf_pipeline = pipeline("text-generation", model=model, tokenizer=tokenizer)

llm = HuggingFacePipeline(pipeline=hf_pipeline)
prompt = PromptTemplate.from_template(RCA_PROMPT_TEMPLATE)
chain = prompt | llm

def contextual_analysis(anomaly_line: str, log_sequence: str, log_window_text: str) -> dict:
    MAX_LOG_WINDOW_CHARS = 2000
    if len(log_window_text) > MAX_LOG_WINDOW_CHARS:
        log_window_text = log_window_text[-MAX_LOG_WINDOW_CHARS:]
    input_vars = {
        "anomaly_line": anomaly_line,
        "log_sequence": log_sequence,
        "log_window_text": log_window_text
    }
    response = chain.invoke(input_vars)
    try:
        return json.loads(response)
    except Exception as e:
        return {"raw_output": response, "error": str(e)}
