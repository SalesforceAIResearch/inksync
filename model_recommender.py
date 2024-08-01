from utils_openai import get_openai_json, run_openai_query
import json, utils_prompts


class RecommendationEngine:
    def __init__(self, marker_prompt_fn="prompts/markers.txt", chat_prompt_fn="prompts/chat.txt", chat_initial_prompt_fn="prompts/chat_initial.txt",
                 brainstorm_prompt_fn="prompts/brainstorm.txt", comment_prompt_fn="prompts/comment.txt",
                 verify_prompt_fn="prompts/verify.txt", shortcut_prompt_fn="prompts/shortcut.txt",
                 model_card="gpt-3.5-turbo"):
        self.marker_prompt_fn = marker_prompt_fn
        self.chat_prompt_fn = chat_prompt_fn
        self.chat_initial_prompt_fn = chat_initial_prompt_fn
        self.brainstorm_prompt_fn = brainstorm_prompt_fn
        self.comment_prompt_fn = comment_prompt_fn
        self.verify_prompt_fn = verify_prompt_fn
        self.shortcut_prompt_fn = shortcut_prompt_fn

        self.model_card = model_card

    def get_marker_suggestions(self, text, markers, document_id):
        with open(self.marker_prompt_fn, "r") as f:
            prompt = f.read()
        text = text.rstrip()
        markers_text, markers_list = utils_prompts.markers_to_text(markers)
        populated_prompt = utils_prompts.populate_prompt(prompt, {"markers": markers_text, "markers_list": markers_list}) # , "previous_suggestions": previous_suggestions, "document": text

        prompt_document = "Document:\n%s" % text

        messages = [
            {"role": "system", "content": "You are the helpful assistant."},
            {"role": "user", "content": prompt_document},
            {"role": "user", "content": populated_prompt},
        ]

        initial_suggestions = get_openai_json(messages, model=self.model_card, location="suggestions", document_id=document_id)
        if initial_suggestions is None:
            initial_suggestions = []
        initial_suggestions = initial_suggestions["edits"] # in the new format, it's nested under this key for better results

        new_suggestions = utils_prompts.verify_suggestions(text, initial_suggestions, markers, model_name=self.model_card)
        new_suggestions = utils_prompts.filter_out_overlapping_suggestions(new_suggestions)
        return new_suggestions

    def generate_chat_response(self, text, conversation, document_id):
        with open(self.chat_prompt_fn, "r") as f:
            prompt = f.read()

        text = text.strip()
        if len(text) < 50:
            return self.generate_chat_initial_response(text, conversation, document_id=document_id)

        prompt_doc, prompt_examples, prompt_format = [msg.strip() for msg in prompt.split("=============================================================")]
        prompt_doc = utils_prompts.populate_prompt(prompt_doc, {"document": text})

        messages = []
        # Start with the document
        messages.append({"role": "system", "content": prompt_doc})
        # Then add the examples
        messages.append({"role": "system", "content": prompt_examples})

        conversation = [msg for msg in conversation if msg.get("clear", 0) != 1 and msg.get("retry", 0) != 1 and msg["sender"] in ["user", "assistant"]]

        for msg in conversation[-3:]: # for now, only use the last 3 messages
            messages.append({"role": msg["sender"], "content": msg["message"]})

        # Finally, add the format
        messages.append({"role": "system", "content": prompt_format})

        model_response = get_openai_json(messages, model=self.model_card, location="chat", document_id=document_id)
        model_reply = "I'm sorry, an error occurred, can you try again?"
        model_suggestions = []

        if model_response is not None:
            model_reply = model_response["reply"]
            model_suggestions = model_response["edits"]
            for sugg in model_suggestions:
                sugg["type"] = "CHAT"

            model_suggestions = utils_prompts.verify_suggestions(text, model_suggestions, [], skip_type_check=True, model_name=self.model_card)
            for sug in model_suggestions:
                sug["suggestion_type"] = "CHAT"

        return {"reply": model_reply, "suggestions": model_suggestions}

    def generate_chat_initial_response(self, text, conversation, document_id):
        with open(self.chat_initial_prompt_fn, "r") as f:
            prompt = f.read()

        text = text.strip()

        conversation_str = ""
        for msg in conversation[-3:]:
            conversation_str += "%s: %s\n" % (msg["sender"], msg["message"])

        prompt_populated = utils_prompts.populate_prompt(prompt, {"instruction": conversation_str})
        messages = [{"role": "system", "content": prompt_populated}]

        model_response = get_openai_json(messages, model=self.model_card, location="chat_initial", document_id=document_id)
        model_reply = "I'm sorry, an error occurred, can you try again?"
        model_suggestions = []
        if model_response is not None:
            model_reply = model_response["reply"]
            initial_draft = model_response["initial_draft"]
            model_suggestions = [{"original_text": text, "replace_text": initial_draft, "anchor_idx": 0, "suggestion_type": "CHAT_INITIAL", "new_info": "yes"}]

        model_suggestions = utils_prompts.verify_suggestions(text, model_suggestions, [], skip_type_check=True, model_name=self.model_card)
        return {"reply": model_reply, "suggestions": model_suggestions}


    def generate_brainstorm(self, old_text, new_text, cursor_line_index, cursor_pointer, selection_text, document_id):
        with open(self.brainstorm_prompt_fn, "r") as f:
            prompts = f.read().strip()

        prompt_doc, prompt_examples, prompt_format = [p.strip() for p in prompts.split("=============================================================")]
        doc_lines = new_text.split("\n")

        selected_lines = [line for line in doc_lines if selection_text in line]
        if len(selected_lines) == 0:
            print("Brainstorm selection text not found in document.")
            return {"suggestions": []}

        highlighted_doc = new_text.replace(selection_text, "**%s**" % selection_text)
        prompt_doc = utils_prompts.populate_prompt(prompt_doc, {"document": highlighted_doc})

        prompt_format = utils_prompts.populate_prompt(prompt_format, {"selected_text": selection_text})
        
        messages = [
            {"role": "system", "content": prompt_doc},
            {"role": "system", "content": prompt_examples},
            {"role": "user", "content": prompt_format},
        ]

        model_suggestions = get_openai_json(messages, model=self.model_card, location="brainstorm", document_id=document_id)
        if model_suggestions is None:
            model_suggestions = []
        else:
            model_suggestions = model_suggestions["alternatives"]

        for sugg in model_suggestions:
            sugg["type"] = "BRAINSTORM"
            if sugg["source"] not in new_text and "**" in sugg["source"]:
                cleaned_source = sugg["source"].replace("**", "")
                if cleaned_source in new_text:
                    sugg["source"] = cleaned_source

        model_suggestions = utils_prompts.verify_suggestions(new_text, model_suggestions, [], skip_type_check=True, model_name=self.model_card)
        for sugg in model_suggestions:
            if len(sugg["original_text"]) == len(selection_text) - 2 and sugg["original_text"] == selection_text[1:-1] and selection_text[0] == "[" and selection_text[-1] == "]":
                sugg["original_text"] = selection_text
                sugg["anchor_idx"] -= 1
            # If the replace_text contains the `[` `]`, then we remove it
            if sugg["replace_text"].startswith("[") and sugg["replace_text"].endswith("]"):
                sugg["replace_text"] = sugg["replace_text"][1:-1]

        return {"suggestions": model_suggestions}

    def generate_comment_response(self, old_text, new_text, conversation, selection_text, anchor_idx, document_id):
        with open(self.comment_prompt_fn, "r") as f:
            prompt = f.read()

        new_text = new_text.strip()
        selection_text = selection_text.strip()
        # Get all the indices of the selection_text in the new_text
        selection_indices = [i for i in range(len(new_text)) if new_text.startswith(selection_text, i)]
        # get the closest index to the anchor_idx
        model_reply = "I'm sorry, an error occurred, can you try again?"
        model_suggestions = []

        closest_indeces = sorted(selection_indices, key=lambda x: abs(x - anchor_idx))
        if len(closest_indeces) > 0:
            closest_index = closest_indeces[0]
            highlighted_text = new_text[:closest_index] + "**%s**" % selection_text + new_text[closest_index + len(selection_text):]

            # system_messages = [msg.strip() for msg in prompt.split("=============================================================")]
            # system_messages = [utils_prompts.populate_prompt(msg, {"document": highlighted_text}) for msg in system_messages]

            # messages = [{"role": "system", "content": msg} for msg in system_messages]

            prompt_doc, prompt_examples, prompt_format = [msg.strip() for msg in prompt.split("=============================================================")]
            # system_messages = [utils_prompts.populate_prompt(msg, {"document": text}) for msg in system_messages]
            prompt_doc = utils_prompts.populate_prompt(prompt_doc, {"document": highlighted_text})

            messages = []
            # Start with the document
            messages.append({"role": "system", "content": prompt_doc})
            # Then add the examples
            messages.append({"role": "system", "content": prompt_examples})

            for msg in conversation:
                messages.append({"role": msg["sender"], "content": msg["message"]})
            
            # Finally, add the format
            messages.append({"role": "system", "content": prompt_format})

            model_response = get_openai_json(messages, model=self.model_card, location="comment", document_id=document_id)
            if model_response is not None:
                model_reply = model_response["reply"]
                model_suggestions = model_response["edits"]
                for sugg in model_suggestions:
                    # It is possible that the model has returned its "source" with the ** which should be removed
                    if sugg["source"] not in new_text and "**" in sugg["source"]:
                        cleaned_source = sugg["source"].replace("**", "")
                        if cleaned_source in new_text: # Clean up
                            sugg["source"] = cleaned_source
                    sugg["type"] = "COMMENT_SUGGESTION"

                model_suggestions = utils_prompts.verify_suggestions(new_text, model_suggestions, [], skip_type_check=True, model_name=self.model_card)
                model_suggestions = utils_prompts.filter_out_overlapping_suggestions(model_suggestions)
        return {"reply": model_reply, "suggestions": model_suggestions}

    def generate_verify_response(self, document_text, suggestion, document_id):
        with open(self.verify_prompt_fn, "r") as f:
            prompts = f.read().strip()

        prompt_doc, prompt_examples, prompt_sample = [p.strip() for p in prompts.split("=============================================================")]

        assert "original_text" in suggestion and "replace_text" in suggestion
        simple_suggestion = json.dumps({"original_text": suggestion["original_text"], "replace_text": suggestion["replace_text"]})

        # populated_prompt = utils_prompts.populate_prompt(prompt, {"suggestion": simple_suggestion, "document": document_text})
        prompt_doc = utils_prompts.populate_prompt(prompt_doc, {"document": document_text})
        propmt_sample = utils_prompts.populate_prompt(prompt_sample, {"suggestion": simple_suggestion})

        messages = [
            {"role": "system", "content": prompt_doc},
            {"role": "system", "content": prompt_examples},
            {"role": "user", "content": propmt_sample},
        ]
        verification_queries = get_openai_json(messages, model=self.model_card, location="verify", document_id=document_id)
        
        if verification_queries is None:
            verification_queries = []

        verification_queries = verification_queries["queries"] # The new prompt requires the queries to be nested
        return verification_queries

    def generate_shortcut_interpretation(self, document, query, document_id):
        with open("prompts/shortcut_v1.txt", "r") as f:
            prompt_shortcut = f.read().strip()

        doc_lines = document.split("\n")

        selected_lines = [line for line in doc_lines if query in line]
        if len(selected_lines) == 0:
            print("Shortcut query not found in document.")
            return "BRAINSTORM"

        selected_line = selected_lines[0]
        # selected_line = sorted([(i, line) for i, line in enumerate(selected_lines)], key=lambda x: abs(x[0] - cursor_line_index))[0][1]
        highlighted_line = selected_line.replace(query, "**%s**" % query)
        populated_prompt = utils_prompts.populate_prompt(prompt_shortcut, {"user_query": highlighted_line})

        # print(">>>>", populated_prompt)

        messages = [
                {"role": "system", "content": "You are the helpful assistant."},
                {"role": "user", "content": populated_prompt},
            ]
        response = run_openai_query(messages, model="gpt-3.5-turbo")
        response_str = response["message"].strip().lower()
        print("Shortcut interpreter for query '%s' returned '%s'" % (query, response_str))

        return "BRAINSTORM" if response_str == "paraphrase" else "COMMENT"


if __name__ == "__main__":
    default_markers = [
        {"id": "marker1", "name": "Typos", "strike_color": "#E31E3E", "strike_style": "dashed", "description": "Suggest any edits related to spelling, punctuation, grammar, or capitalization."},
        {"id": "marker2", "name": "Lexical Simplification", "strike_color": "#12A683", "strike_style": "solid", "description": ""}
    ]

    document = """A microscope (from Ancient Greek μικρός (mikrós) 'small', and σκοπέω (skopéō) 'to look (at); examine, inspect') is a laboratory instrumnt used to examine objects that are too small to be seen by the naked eye. Microscopy is the science of investigating small objects and structures using a microscope. Microscopic means being invisible to the eye unless aided by a microscope."""

    suggestion_recommender = GPT_Suggestion_Recommender("prompts/memoryless_prompt_v3.txt")
    suggestions = suggestion_recommender.generate_suggestions("", document, [], default_markers)

    for suggestion in suggestions:
        print("---")
        print(suggestion)
