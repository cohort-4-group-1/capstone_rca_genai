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
  "affected_component": "...",
  "severity": "low | medium | high",
  "suggested_action": "..."
}}

---
"""

# Load model
model_id = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
print("Starting to create tokenizer")
tokenizer = AutoTokenizer.from_pretrained(model_id)
print("Starting to create model")
model = AutoModelForCausalLM.from_pretrained(model_id)
print("Starting to create hf_pipeline")
hf_pipeline = pipeline(
    "text-generation",
    model=model,
    tokenizer=tokenizer,
    max_new_tokens=512,  # limit output length
)
print("Starting to create llm")
llm = HuggingFacePipeline(pipeline=hf_pipeline)
print("Starting to create prompt")
prompt = PromptTemplate.from_template(RCA_PROMPT_TEMPLATE)
print("Starting to create chain")
chain = prompt | llm

MAX_TOKENS = 2048


def truncate_input_to_token_limit(prompt_obj, anomaly_line, log_sequence, log_window_text, tokenizer, max_tokens=2048):
    while True:
        formatted_prompt = prompt_obj.format_prompt(
            anomaly_line=anomaly_line,
            log_sequence=log_sequence,
            log_window_text=log_window_text
        ).to_string()
        token_count = len(tokenizer.tokenize(formatted_prompt))
        if token_count <= max_tokens:
            return anomaly_line, log_sequence, log_window_text
        # Truncate log_window_text iteratively
        log_window_text = log_window_text[len(log_window_text) // 10:]
        if len(log_window_text) < 100:
            break
    return anomaly_line, log_sequence, log_window_text


def contextual_analysis(anomaly_line: str, log_sequence: str, log_window_text: str) -> dict:
    print("**************** Before truncate *************************")
    print(f"anomaly_line: {anomaly_line}")
    print(f"log_sequence: {log_sequence}")
    print(f"log_window_text: {log_window_text}")
    anomaly_line, log_sequence, log_window_text = truncate_input_to_token_limit(
        prompt,
        anomaly_line,
        log_sequence,
        log_window_text,
        tokenizer,
        max_tokens=2048
    )
    input_vars = {
        "anomaly_line": anomaly_line,
        "log_sequence": log_sequence,
        "log_window_text": log_window_text
    }
    print("**************** After truncate *************************")
    print(f"anomaly_line: {anomaly_line}")
    print(f"log_sequence: {log_sequence}")
    print(f"log_window_text: {log_window_text}")
    response = chain.invoke(input_vars)
    print("Json will be loaded")
    try:
        return json.loads(response)    
    except Exception as e:
        print(f"Exception occured: {str(e)}")
        return {"raw_output": response, "error": str(e)}
