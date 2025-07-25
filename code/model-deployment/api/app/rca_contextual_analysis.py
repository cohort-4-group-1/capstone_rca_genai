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
For each anomaly, analyze the context and respond with a JSON object in this format:
{
  "anomaly_line": "...",
  "anomaly_cause": "...",
  "affected_component": "...",
  "severity": "low | medium | high",
  "suggested_action": "..."
}

---

"""

# Load model once
model_id = "mistralai/Mistral-7B-Instruct-v0.1"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id, device_map="auto")
hf_pipeline = pipeline("text-generation", model=model, tokenizer=tokenizer)

llm = HuggingFacePipeline(pipeline=hf_pipeline)
prompt = PromptTemplate.from_template(RCA_PROMPT_TEMPLATE)
chain = prompt | llm

MAX_TOKENS = 2048


def truncate_input_to_token_limit(prompt_template: str, anomaly_line: str, log_sequence: str, log_window_text: str, tokenizer, max_tokens: int = 2048):
    formatted_prompt = prompt_template.format(
        anomaly_line=anomaly_line,
        log_sequence=log_sequence,
        log_window_text=log_window_text
    )
    tokens = tokenizer.tokenize(formatted_prompt)
    if len(tokens) <= max_tokens:
        return anomaly_line, log_sequence, log_window_text

    trimmed_log_window = log_window_text
    while len(tokenizer.tokenize(prompt_template.format(
        anomaly_line=anomaly_line,
        log_sequence=log_sequence,
        log_window_text=trimmed_log_window
    ))) > max_tokens:
        trimmed_log_window = trimmed_log_window[len(trimmed_log_window)//10:]  # trim ~10% each loop
        if len(trimmed_log_window) < 100:
            break

    return anomaly_line, log_sequence, trimmed_log_window


def contextual_analysis(anomaly_line: str, log_sequence: str, log_window_text: str) -> dict:
    anomaly_line, log_sequence, log_window_text = truncate_input_to_token_limit(
        RCA_PROMPT_TEMPLATE,
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
    response = chain.invoke(input_vars)
    try:
        return json.loads(response)
    except Exception as e:
        return {"raw_output": response, "error": str(e)}
