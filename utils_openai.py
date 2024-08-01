from datetime import datetime
from openai import OpenAI
import os, time, json

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

ERROR_LOG_FILE = "logs/error_log.jsonl"
QUERY_LOG_FILE = "logs/query_log.jsonl"
STATS_LOG_FILE = "logs/llm_stats_log.jsonl"


def parse_json(json_str):
    problematic_starts = ["```json", "```", "`"]
    problematic_ends = ["```", "`"]

    for start in problematic_starts:
        if json_str.startswith(start):
            json_str = json_str[len(start):]

    for end in problematic_ends:
        if json_str.endswith(end):
            json_str = json_str[:-len(end)]

    json_str = json_str.strip()
    return json.loads(json_str)


def run_openai_query(messages, model="gpt-3.5-turbo-1106", timeout=30, max_retries=3, is_json=False):
    T = time.time()
    kwargs = {}
    if is_json:
        kwargs["response_format"] = { "type": "json_object" }
    N = 0
    while True:
        try:
            response = client.chat.completions.create(model=model, messages=messages, timeout=timeout, **kwargs)
            break
        except:
            N += 1
            if N >= max_retries:
                raise Exception("Failed to get response from OpenAI")
            else:
                time.sleep(4)

    response_text = response.choices[0].message.content
    usage = response.usage

    total_tokens = usage.total_tokens

    prompt_tokens = usage.prompt_tokens
    completion_tokens = usage.completion_tokens
    total_usd = 0.0

    inp_token_cost, out_token_cost = 0.0, 0.0

    if model == "gpt-3.5-turbo":
        inp_token_cost, out_token_cost = 0.0015, 0.002
    elif model == "gpt-3.5-turbo-1106":
        inp_token_cost, out_token_cost = 0.001, 0.002
    elif model == "gpt-3.5-turbo-0125":
        inp_token_cost, out_token_cost = 0.0005, 0.0015
    elif model == "gpt-4-1106-preview":
        inp_token_cost, out_token_cost = 0.01, 0.03
    elif model == "gpt-4":
        inp_token_cost, out_token_cost = 0.03, 0.06
    total_usd = (prompt_tokens / 1000) * inp_token_cost + (completion_tokens / 1000) * out_token_cost

    completion_time = time.time() - T
    return {"message": response_text, "total_tokens": total_tokens, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "completion_time": completion_time, "total_usd": total_usd}


def get_openai_json(messages, model, location=None, document_id=None):
    total_response = run_openai_query(messages, model=model, is_json=True)
    cgpt_response = total_response["message"]

    print(">>>>", cgpt_response)

    stats = {k: v for k, v in total_response.items() if k != "message"}
    if location is not None:
        stats["location"] = location
    if document_id is not None:
        stats["document_id"] = document_id
    stats["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(STATS_LOG_FILE, "a") as f:
        f.write(json.dumps(stats) + "\n")

    response_json = None
    log_obj = {"input_prompt": json.dumps(messages), "response_str": cgpt_response, "model_card": model, "location": location, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    log_file = QUERY_LOG_FILE
    try:
        response_json = parse_json(cgpt_response)
    except:
        print("Warning: Could not parse JSON response")
        log_file = ERROR_LOG_FILE
        print(">>>>>>>>", cgpt_response)

    with open(log_file, "a") as f:
        f.write(json.dumps(log_obj) + "\n")
    return response_json


if __name__ == "__main__":
    messages = [
        {"role": "system", "content": "You are a stand-up comedian getting content ready for your Netflix special."},
        {"role": "user", "content": "Tell me a long and funny joke about UC Berkeley."},
    ]

    response = run_openai_query(messages)
    print(response)
