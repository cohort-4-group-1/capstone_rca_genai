from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
from langchain_community.llms import HuggingFacePipeline
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence

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
