from bson.objectid import ObjectId
from collections import Counter
import itertools


def populate_prompt(prompt, variables):
    populated_prompt = ""+prompt
    for k, v in variables.items():
        try:
            populated_prompt = populated_prompt.replace("["+k.upper()+"]", v)
        except:
            print(k, v)

    return populated_prompt

def filter_out_overlapping_suggestions(suggestions, preferred_type=None):
    suggestions = [sug for sug in suggestions if "action" not in sug]
    to_be_removed = []
    type_counts = Counter([sug["suggestion_type"] for sug in suggestions])

    for sug1, sug2 in itertools.combinations(suggestions, 2):
        if sug1["id"] in to_be_removed or sug2["id"] in to_be_removed:
            continue

        start1 = sug1["anchor_idx"]
        end1 = sug1["anchor_idx"] + len(sug1["original_text"])
        start2 = sug2["anchor_idx"]
        end2 = sug2["anchor_idx"] + len(sug2["original_text"])

        if not (end1 <= start2 or end2 <= start1):
            # Choose which one to remove: if there's a prefered type, choose based on that, otherwise: we keep the least common type_count
            removed_id = None
            if preferred_type is not None:
                if sug1["suggestion_type"] == preferred_type:
                    removed_id = sug2["id"]
                elif sug2["suggestion_type"] == preferred_type:
                    removed_id = sug1["id"]

            if removed_id is None:
                if type_counts[sug1["suggestion_type"]] < type_counts[sug2["suggestion_type"]]:
                    removed_id = sug2["id"]
                else:
                    removed_id = sug1["id"]
            to_be_removed.append(removed_id)

    return [sug for sug in suggestions if sug["id"] not in to_be_removed]


def verify_suggestions(document, suggestions, markers, skip_type_check=False, model_name=None):
    marker_map = {marker["name"].upper().replace(' ', '_'): marker for marker in markers}

    verified_suggestions = []
    for suggestion in suggestions:
        if all([k in suggestion for k in ["type", "source", "target"]]):
            # If it uses the simpler keys we use for the LLM, remap it to our internal key names
            new_info = suggestion.get("new_info", "no")
            explanation = suggestion.get("explanation", "")
            suggestion = {"suggestion_type": suggestion["type"], "original_text": suggestion["source"], "replace_text": suggestion["target"], "new_info": new_info, "explanation": explanation}

        if suggestion["suggestion_type"][0] == "[" and suggestion["suggestion_type"][-1] == "]":
            suggestion["suggestion_type"] = suggestion["suggestion_type"][1:-1]

        if suggestion["suggestion_type"] not in marker_map:
            # We try to salvage it by: (1) checking if we remove a potential trailing S, if it is in, or (2) if we add a trailing S, if it is in
            if suggestion["suggestion_type"][-1] == "S" and suggestion["suggestion_type"][:-1] in marker_map:
                suggestion["suggestion_type"] = suggestion["suggestion_type"][:-1] # Remove trailing S
            elif suggestion["suggestion_type"] not in marker_map and suggestion["suggestion_type"]+"S" in marker_map:
                suggestion["suggestion_type"] = suggestion["suggestion_type"]+"S" # Add trailing S

        if any([k not in suggestion for k in ["suggestion_type", "original_text", "replace_text"]]):
            print("Warning: Suggestion does not contain all required keys")
            print(suggestion)
            continue

        if suggestion["original_text"] not in document:
            print("Warning: Anchor text not found in document: %s" % suggestion["original_text"])
            continue

        if suggestion["replace_text"] == suggestion["original_text"]:
            continue # Skip suggestions that don't change anything

        if not skip_type_check and suggestion["suggestion_type"] not in marker_map:
            print("Warning: Suggestion type not found in markers (%s) not in %s" % (suggestion["suggestion_type"], marker_map.keys()))
            print(suggestion)
            continue

        if "new_info" not in suggestion:
            suggestion["new_info"] = "no"
        elif suggestion["new_info"] not in ["yes", "no"]:
            print("Warning: new_info value not valid: %s" % suggestion["new_info"])
            suggestion["new_info"] = "no"
            continue

        anchor_index = document.index(suggestion["original_text"])
        suggestion_obj = {"id": str(ObjectId()), "suggestion_type": suggestion["suggestion_type"], "anchor_idx": anchor_index, "original_text": suggestion["original_text"], "replace_text": suggestion["replace_text"], "new_info": suggestion["new_info"], "explanation": suggestion.get("explanation", "")}

        if not skip_type_check:
            marker = marker_map[suggestion["suggestion_type"]]
            suggestion_obj["marker_id"] = marker["id"]
            suggestion_obj["marker_name"] = marker["name"]

        if model_name is not None:
            suggestion_obj["model_name"] = model_name

        verified_suggestions.append(suggestion_obj)
    return verified_suggestions


def markers_to_text(markers):
    # We want to output something like this
    # [TYPO] Anything related to spelling, punctuation, grammar, or capitalization.
    # [REPHRASING] Any word or phrase you propose a replacement for. Ideally your edits should be atomic, and target at most 3-4 words at a time. You shouldn't propose to change a full sentence all at once.
    marker_text = ""
    marker_list = []
    for marker in markers:
        marker_name = marker["name"].upper().replace(' ', '_')
        if marker.get("description", "") == "":
            marker["description"] = "Suggest edits related to %s." % marker["name"]
        marker_text += f"[{marker_name}] {marker['description']}\n"
        marker_list.append(f"[{marker_name}]")

    marker_list = ", ".join(marker_list)
    return marker_text.strip(), marker_list
