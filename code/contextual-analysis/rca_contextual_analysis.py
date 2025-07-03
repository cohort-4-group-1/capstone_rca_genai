from fastapi import FastAPI
from pydantic import BaseModel
from langchain import PromptTemplate, LLMChain
from langchain.llms import HuggingFacePipeline
from langchain.output_parsers import JsonOutputParser
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline


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

    {
    "anomaly_cause": "...",
    "affected_component": "...",
    "severity": "low | medium | high",
    "suggested_action": "..."
    }
"""
# Load model
model_id = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id)
hf_pipeline = pipeline("text-generation", model=model, tokenizer=tokenizer)

llm = HuggingFacePipeline(pipeline=hf_pipeline)

# Prompt template
template = PromptTemplate.from_template(RCA_PROMPT_TEMPLATE)

parser = JsonOutputParser()

chain = LLMChain(prompt=template, llm=llm)

# FastAPI app
app = FastAPI()

class RCARequest(BaseModel):
    anomaly_line: str
    log_sequence: str
    log_window_text: str

@app.post("/analyze")
def analyze(req: RCARequest):
    response = chain.run(
        anomaly_line=req.anomaly_line,
        log_sequence=req.log_sequence,
        log_window_text=req.log_window_text
    )
    try:
        return parser.parse(response)
    except Exception as e:
        return {"raw_output": response, "error": str(e)}
