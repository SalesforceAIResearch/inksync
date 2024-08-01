# InkSync

Authors: Philippe Laban, Jesse Vig, Marti A. Hearst, Caiming Xiong, Chien-Sheng Wu

Paper Link: [Beyond the Chat: Executable and Verifiable Text-Editing with LLMs
](https://arxiv.org/abs/2309.15337)

Contact: plaban@salesforce.com



## How to install/setup InkSync:

1. Install the requirements.txt
```
pip install -r requirements.txt
```

2. (Optional) Modify the app's parameters, defined in the `app_params.py`. This can be used to enable/disable certain components of the app, and set which LLM to use to serve edit recommendations from.

3. Set an environment variable for `OPENAI_API_KEY` which will be used to bill for the LLM API usage. You can get an API key from [OpenAI](https://openai.com/). It should be set in the environment before launching the app.

4. Launch the app!
For development purposes, you can simply launch the app this way:

```
python wsgiis.py
```

This is not stable for a "production environment" (or a long-term usability study), but can help during development.

For a more stable deployment, you can use NGINX & Gunicorn, and start the app with the following command:

```
gunicorn --timeout 60 --bind unix:/path/to/inksync/app.sock -m 777 -w 5 wsgiis:app --reload
```

This requires more advanced setup and configuration on a server, but is more stable and secure.

5. Head to the app's URL in the browser:

By default, typically: [http://127.0.0.1:5000/](http://127.0.0.1:5000/)


## Where are things located in this project:

- `app_*` files contain the files to the backend (Flask) of the app.
    - `app_inksync.py` is the main file which defines all the backend routes.
    - `app_params.py` has all basic parameters to enable/disable components without having to get deep in the code.
- `prompts/` folder contains all the prompts used by LLM-based components of the app.
- `model_recommender.py` has all the LLM-related code, dealing with receiving inputs, and generating/validating edit suggestions by the LLM.
- The front end is distributed in:
    - `static/` folder contains all the static files (CSS, JS, images, etc.)
    - `templates/` folder contains all the HTML files.
- `documents/` folder contains the full trace of documents edited by users. Each document corresponds to a JSON file in there in the format: `user_<USERID>_<UNIQUE_DOC_ID>.json`
- `logs/` folder contains several important log files useful for analysis:
    - `api_log.jsonl` contains all the API calls made to the app.
    - `llm_stats_log.jsonl` contains high-level information about LLM-queries made: which component, the number of tokens, the cost (USD), and the latency.
    - `query_log.jsonl` contains the exact queries that were sent to the LLM, for debugging purposes.

## How to learn more about InkSync

Read the paper, listed above for details on the system and implementation.