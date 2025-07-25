# rca_contextual_analysis.py

from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_community.llms import HuggingFacePipeline
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import json

RCA_PROMPT_TEMPLATE = """
You are a cloud infrastructure expert skilled in analyzing OpenStack logs and finding root causes of anomalies.

You are given a list of anomalies, where each anomaly includes:
- A suspicious log line.
- A log sequence of templates before the anomaly.
- Raw log context around the anomaly.

Your job is to:
- Identify possible causes for each anomaly.
- Suggest where the issue might have originated.
- Keep the answers concise, technical, and actionable.

---

{anomaly_list}

---

For each anomaly, respond in this JSON list format:

[
  {{
    "anomaly_line": "...",
    "anomaly_cause": "...",
    "affected_component": "...",
    "severity": "low | medium | high",
    "suggested_action": "..."
  }},
  ...
]
"""



# Load model once
model_id = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id)
hf_pipeline = pipeline("text-generation", model=model, tokenizer=tokenizer)

llm = HuggingFacePipeline(pipeline=hf_pipeline)
prompt = PromptTemplate.from_template(RCA_PROMPT_TEMPLATE)
chain = prompt | llm

def contextual_analysis_batch(anomaly_inputs):
    # Construct a formatted block of anomalies
    formatted_input = "\n\n".join([
        f"🔴 Anomaly Line:\n{a['anomaly_line']}\n"
        f"🧩 Log Sequence:\n{a.get('log_sequence', '')}\n"
        f"📜 Log Window:\n{a['log_window_text']}"
        for a in anomaly_inputs
    ])

    response = chain.invoke({"anomaly_list": formatted_input})

    try:
        return json.loads(response)
    except Exception as e:
        return {"raw_output": response, "error": str(e)}


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
