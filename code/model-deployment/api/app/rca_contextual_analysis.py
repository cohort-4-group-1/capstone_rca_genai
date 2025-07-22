import json
import traceback
from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_community.llms import HuggingFacePipeline
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

# Import OTEL shared instances
from main_isolation_forest import logger, tracer, meter, OTEL_ENABLED

# Prompt template for RCA
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

# Metrics
if OTEL_ENABLED and meter:
    rca_context_invocations_total = meter.create_counter(
        name="rca_context_invocations_total",
        description="Total number of contextual analysis calls"
    )
    rca_context_duration = meter.create_histogram(
        name="rca_context_duration_seconds",
        description="Contextual analysis execution duration"
    )
else:
    rca_context_invocations_total = None
    rca_context_duration = None

def contextual_analysis(anomaly_line: str, log_sequence: str, log_window_text: str) -> dict:
    MAX_LOG_WINDOW_CHARS = 2000
    if len(log_window_text) > MAX_LOG_WINDOW_CHARS:
        log_window_text = log_window_text[-MAX_LOG_WINDOW_CHARS:]

    input_vars = {
        "anomaly_line": anomaly_line,
        "log_sequence": log_sequence,
        "log_window_text": log_window_text
    }

    if OTEL_ENABLED and tracer:
        with tracer.start_as_current_span("rca_contextual_analysis") as span:
            span.set_attribute("anomaly_line", anomaly_line)
            logger.info(f"Invoking RCA contextual analysis for anomaly: {anomaly_line}")
            try:
                if rca_context_invocations_total:
                    rca_context_invocations_total.add(1, {"status": "invoked"})

                import time
                start_time = time.time()
                response = chain.invoke(input_vars)
                duration = time.time() - start_time

                if rca_context_duration:
                    rca_context_duration.record(duration, {"status": "success"})

                try:
                    parsed = json.loads(response)
                    logger.info("RCA contextual analysis completed successfully")
                    return parsed
                except Exception as e:
                    logger.warning(f"RCA response not JSON formatted: {response}")
                    return {"raw_output": response, "error": str(e)}
            except Exception as e:
                logger.error(f"RCA contextual analysis failed: {str(e)}")
                if rca_context_duration:
                    rca_context_duration.record(0.0, {"status": "error"})
                return {"error": str(e), "trace": traceback.format_exc()}
    else:
        logger.warning("OTEL not enabled - running RCA without tracing")
        try:
            response = chain.invoke(input_vars)
            return json.loads(response)
        except Exception as e:
            return {"raw_output": response, "error": str(e)}
