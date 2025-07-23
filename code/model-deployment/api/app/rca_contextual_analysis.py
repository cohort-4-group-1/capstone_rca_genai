# rca_contextual_analysis.py

from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_community.llms import HuggingFacePipeline
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import json

RCA_MULTI_PROMPT_TEMPLATE = """
You are a cloud infrastructure expert skilled in analyzing OpenStack logs and identifying root causes of anomalies.

You are given a list of anomalies, where each anomaly has:
- An anomalous log line flagged by a machine learning model.
- A log sequence (template pattern) preceding the anomaly.
- A raw log context (actual log lines before and after the anomaly).

For each anomaly, analyze the context and respond with a JSON object in this format:
{{
  "anomaly_line": "...",
  "anomaly_cause": "...",
  "affected_component": "...",
  "severity": "low | medium | high",
  "suggested_action": "..."
}}

Return a JSON array of such objects — one per anomaly. Keep the response concise, technical, and actionable.

---

🔍 Anomalies to analyze:
{anomaly_list}
"""




# Load model once
model_id = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id)
hf_pipeline = pipeline("text-generation", model=model, tokenizer=tokenizer,  max_length=2048,       
    max_new_tokens=300,      
    truncation=True,         
    do_sample=True,
    temperature=0.7)

llm = HuggingFacePipeline(pipeline=hf_pipeline)
prompt = PromptTemplate.from_template(RCA_MULTI_PROMPT_TEMPLATE)
chain = prompt | llm

def contextual_analysis_batch(anomaly_inputs: list) -> list:
    # Format input
    blocks = []
    for idx, anomaly in enumerate(anomaly_inputs):
        block = f"""---
        Anomaly #{idx+1}
        🔴 Log Line: {anomaly['anomaly_line']}
        🧩 Log Sequence: {anomaly['log_sequence']}
        📜 Raw Context:
        {anomaly['log_window_text']}
        """
        blocks.append(block)

    anomaly_list = "\n".join(blocks)
    response = chain.invoke({"anomaly_list": anomaly_list})

    try:
        return json.loads(response)
    except Exception as e:
        return [{"error": str(e), "raw_output": response}]
