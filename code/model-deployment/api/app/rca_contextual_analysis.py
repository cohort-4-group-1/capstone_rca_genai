# rca_contextual_analysis.py

from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_community.llms import HuggingFacePipeline
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import json

RCA_PROMPT_TEMPLATE = """
You are a cloud infrastructure expert skilled in analyzing OpenStack logs and finding root causes of anomalies...
...Respond in this JSON format:
{
"anomaly_cause": "...",
"affected_component": "...",
"severity": "low | medium | high",
"suggested_action": "..."
}
"""

# Load model once
model_id = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id)
hf_pipeline = pipeline("text-generation", model=model, tokenizer=tokenizer)
llm = HuggingFacePipeline(pipeline=hf_pipeline)

template = PromptTemplate.from_template(RCA_PROMPT_TEMPLATE)
chain = LLMChain(prompt=template, llm=llm)

def contextual_analysis(anomaly_line: str, log_sequence: str, log_window_text: str) -> dict:
    response = chain.run(
        anomaly_line=anomaly_line,
        log_sequence=log_sequence,
        log_window_text=log_window_text
    )
    try:
        return json.loads(response)
    except Exception as e:
        return {"raw_output": response, "error": str(e)}
