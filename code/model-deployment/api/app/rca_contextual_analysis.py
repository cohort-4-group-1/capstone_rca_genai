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

Suspicious Log Line:
"{anomaly_line}"

Log Sequence (Template Pattern):
"{log_sequence}"

Raw Log Context:
{log_window_text}

---

Please explain the likely root cause or contributing factors, even if speculative.
Respond in this JSON format:

{{
  "anomaly_line": "...",
  "anomaly_cause": "...",
  "suggested_action": "..."
}}

---
"""

# Load model once
model_id = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id)
hf_pipeline = pipeline("text-generation", model=model, tokenizer=tokenizer,max_new_tokens=512)

llm = HuggingFacePipeline(pipeline=hf_pipeline)
prompt = PromptTemplate.from_template(RCA_PROMPT_TEMPLATE)
chain = prompt | llm

MAX_TOKENS = 2048

def contextual_analysis(anomaly_line: str, log_sequence: str, log_window_text: str) -> dict:
    max_total_chars = 6000  # 2048 tokens * ~3 chars per token
    print (f"Before truncate -  Length of anomaly_line: {len(anomaly_line)}")
    print (f"Before truncate -  Length of log_sequence  : {len(log_sequence)}")
    print (f"Before truncate -  ength of log_window_text : {len(log_window_text)}")
     # Allocate budget (you can tweak this ratio)
    max_log_sequence_chars = int(max_total_chars * 0.4)
    max_log_window_chars = max_total_chars - len(anomaly_line) - max_log_sequence_chars

    if len(log_sequence) > max_log_sequence_chars:
        log_sequence = log_sequence[-max_log_sequence_chars:]
    if len(log_window_text) > max_log_window_chars:
        log_window_text = log_window_text[-max_log_window_chars:]

    print (f"After truncate -  Length of anomaly_line: {len(anomaly_line)}")
    print (f"After truncate -  Length of log_sequence  : {len(log_sequence)}")
    print (f"After truncate -  ength of log_window_text : {len(log_window_text)}")
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
