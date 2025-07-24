from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
import json
import traceback
from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_community.llms import HuggingFacePipeline
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

# Import OTEL shared instances
from otel import logger, tracer, meter, OTEL_ENABLED

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


# Updated multi-anomaly prompt template
RCA_MULTI_PROMPT_TEMPLATE = """
You are a cloud infrastructure expert skilled in analyzing OpenStack logs and identifying root causes of anomalies.

You are given a list of anomalies. Each anomaly contains:
- An anomalous log line flagged by a machine learning model.
- The raw log context (actual log lines before and after the anomaly).

Analyze each anomaly contextually and return a JSON array of RCA results. Each object in the array should contain:
{
  "anomaly_line": string,
  "anomaly_cause": string,
  "affected_component": string,
  "severity": "low" | "medium" | "high",
  "suggested_action": string
}

Respond only with a JSON array.

Anomalies:
{anomaly_list}
"""

def create_llm():
    model_id = "tiiuae/falcon-7b-instruct"
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(model_id)
    hf_pipeline = pipeline(
        task="text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=512,
        do_sample=True,
        temperature=0.7,
        top_k=50,
        top_p=0.95,
        repetition_penalty=1.2
    )
    return HuggingFacePipeline(pipeline=hf_pipeline)

llm = create_llm()

# Prompt template using only anomaly_list
template = PromptTemplate(
    input_variables=["anomaly_list"],
    template=RCA_MULTI_PROMPT_TEMPLATE
)

# Load model once
model_id = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id)
hf_pipeline = pipeline("text-generation", model=model, tokenizer=tokenizer)


# RunnableSequence is the new style for chaining in LangChain
chain = template | llm


def contextual_analysis_batch(anomaly_inputs):
    # Format the anomaly inputs as a string
    formatted_input = "\n\n".join([
        f"Anomaly Line: {a['anomaly_line']}\nLog Context:\n{a['log_window_text']}"
        for a in anomaly_inputs
    ])
    response = chain.invoke({"anomaly_list": formatted_input})
    return response


def contextual_analysis(anomaly_line: str, log_sequence: str, log_window_text: str) -> dict:
    MAX_LOG_WINDOW_CHARS = 2000
    MAX_LOG_WINDOW_CHARS = 1000
    MAX_SEQUENCE_CHARS = 1000

    if len(log_window_text) > MAX_LOG_WINDOW_CHARS:
        log_window_text = log_window_text[-MAX_LOG_WINDOW_CHARS:]
    
    if len(log_sequence) > MAX_SEQUENCE_CHARS:
        log_sequence = log_sequence[-MAX_SEQUENCE_CHARS:]

    input_vars = {
        "anomaly_line": anomaly_line,
        "log_sequence": log_sequence,
        "log_window_text": log_window_text
    }
    
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
