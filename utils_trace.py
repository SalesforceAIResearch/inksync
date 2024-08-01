from difflib import SequenceMatcher

def suggestion2track(suggestion):
    track = {"suggestion_id": suggestion["id"]}
    anchor_idx = suggestion["anchor_idx"]

    original_text = suggestion["original_text"]
    replace_text = suggestion["replace_text"]

    s = SequenceMatcher(None, original_text, replace_text)
    opcodes = s.get_opcodes()
    first_opcode = opcodes[0]
    last_opcode = opcodes[-1]

    if first_opcode[0] == "equal":
        anchor_idx += first_opcode[2] - first_opcode[1]
        replace_text = replace_text[(first_opcode[2] - first_opcode[1]):]

    if last_opcode[0] == "equal":
        replace_text = replace_text[:-(last_opcode[2] - last_opcode[1])]

    track["anchor_idx"] = anchor_idx
    track["replace_text"] = replace_text
    return track


def find_all_contiguous_chunks(new_indices):
    all_chunks = []
    current_chunk = []
    for elem in new_indices:
        if elem == -1:
            if len(current_chunk) > 0:
                all_chunks.append(current_chunk)
                current_chunk = []
        else:
            if len(current_chunk) > 0 and current_chunk[-1] + 1 != elem:
                all_chunks.append(current_chunk)
                current_chunk = []
            current_chunk.append(elem)

    if len(current_chunk) > 0:
        all_chunks.append(current_chunk)
        current_chunk = []

    return [[chunk[0], chunk[-1]] for chunk in all_chunks]


def merge_tracks(tracks):
    tracks = sorted(tracks, key=lambda x: x["anchor_idx"])
    i = 0
    while i < len(tracks):
        if i == len(tracks)-1:
            i += 1 # There's nothing to merge with
        else:
            track = tracks[i]
            track2 = tracks[i+1]
            # Try to merge i & j
            if track["anchor_idx"] + len(track["replace_text"]) == track2["anchor_idx"]:
                track["replace_text"] += track2["replace_text"] # They are contiguous, merge them
                tracks = tracks[:i+1] + tracks[i+2:] # Remove track2 from the list
            else:
                i += 1 # No merge, move on
    return tracks


def merge_all_tracks(tracks):
    all_merged_tracks = []
    sug_ids = set([t["suggestion_id"] for t in tracks])

    for sug_id in sug_ids:
        all_merged_tracks += merge_tracks([t for t in tracks if t["suggestion_id"] == sug_id])
    return all_merged_tracks


def shift_tracks(old_text, new_text, old_tracks):
    s = SequenceMatcher(None, old_text, new_text)
    opcodes = s.get_opcodes()
    idx_map = {}
    for code, i1, i2, j1, j2 in opcodes:
        if code == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                idx_map[i] = j

    new_tracks = []
    for old_track in old_tracks:
        start_idx = old_track["anchor_idx"]
        end_idx = start_idx + len(old_track["replace_text"])

        # Keep track of all indices and find largest contiguous range
        new_indices = [idx_map.get(i, -1) for i in range(start_idx, end_idx)]
        contiguous_chunks = find_all_contiguous_chunks(new_indices)

        for chunk_start, chunk_end in contiguous_chunks:
            new_track = {"suggestion_id": old_track["suggestion_id"], "anchor_idx": chunk_start}
            new_track["replace_text"] = new_text[chunk_start:(chunk_end+1)]
            if len(new_track["replace_text"]) > 0:
                new_tracks.append(new_track)

    new_tracks = merge_all_tracks(new_tracks)
    return new_tracks


def find_all_indices(text, sub):
    indices = []
    idx = text.find(sub)
    while idx != -1:
        indices.append(idx)
        idx = text.find(sub, idx+1)
    return indices


def run_suggestion_tracing(document_history, suggestions, printing=False, final_cleanup=True):
    current_text, active_tracks = "", []
    for v_idx, version in enumerate(document_history):
        new_text = version["text"].strip()
        active_tracks = shift_tracks(current_text, new_text, active_tracks)

        version_suggestions = [sug for sug in suggestions if sug["id"] in version.get("accepted_suggestion_ids", [])]

        for sug in version_suggestions:
            if len(sug["replace_text"]) == 0:
                # It's a pure deletion, we can skip the tracking
                continue
            # Verify that the suggestion is correctly positioned
            inside_text = current_text[sug["anchor_idx"]:(sug["anchor_idx"] + len(sug["original_text"]))]
            if inside_text != sug["original_text"] and printing:
                print("!! WARNING: Suggestion insertion mismatch (type 1)")

            inside_new_text = new_text[sug["anchor_idx"]:(sug["anchor_idx"] + len(sug["replace_text"]))]

            track = suggestion2track(sug)
            if inside_new_text != sug["replace_text"]:
                if printing:
                    print("!! WARNING: Suggestion insertion mismatch (type 2)")
                if new_text.count(sug["replace_text"]) == 0:
                    # No matches, hopeless, skip that suggestion
                    continue
                else:
                    # 1. get all the indices, and find the closest one to the original anchor_idx
                    indices = find_all_indices(new_text, sug["replace_text"])
                    closest_idx = min(indices, key=lambda x: abs(x - sug["anchor_idx"]))
                    track["anchor_idx"] = closest_idx
            active_tracks.append(track)

        current_text = new_text
        if printing:
            N_tracks = len(active_tracks)
            N_suggs = len(set([t["suggestion_id"] for t in active_tracks]))
            print("========= VERSION %d; %d TRACKS; %d SUGGESTIONS =========" % (v_idx, N_tracks, N_suggs))
            print(highlight_text_console(current_text, active_tracks).strip())

    if final_cleanup:
        active_tracks = cleanup_tracks_presentation(active_tracks)

    return active_tracks


def highlight_text_console(text, tracks):
    tracks = sorted(tracks, key=lambda x: x["anchor_idx"], reverse=True)
    already_ranges = []
    current_text = ""+text
    for track in tracks:
        # check if there's any overlap
        if any(not (track["anchor_idx"] + len(track["replace_text"]) <= already_range["start"] or already_range["end"] <= track["anchor_idx"]) for already_range in already_ranges):

            continue
        current_text = current_text[:track["anchor_idx"]] + "\033[93m" + track["replace_text"] + "\033[0m" + current_text[(track["anchor_idx"] + len(track["replace_text"])):] # Use colorama to color in orange
        already_ranges.append({"start": track["anchor_idx"], "end": track["anchor_idx"] + len(track["replace_text"])})
    return current_text


def cleanup_track(track):
    punctuation = [".", ","]
    track["replace_text"] = track["replace_text"].rstrip()

    N_char = len(track["replace_text"])
    if len(track["replace_text"].lstrip()) != N_char:
        new_N_char = len(track["replace_text"].lstrip())
        track["anchor_idx"] += N_char - new_N_char
        track["replace_text"] = track["replace_text"].lstrip()

    if len(track["replace_text"]) == 0 or track["replace_text"] in punctuation:
        return None
    return track


def cleanup_tracks_presentation(tracks):
    clean_tracks = []
    for track in tracks:
        clean_track = cleanup_track(track)
        if clean_track is not None:
            clean_tracks.append(clean_track)
    return clean_tracks


if __name__ == "__main__":
    import json, sys, os

    if len(sys.argv) >= 2:
        fn = "documents/%s.json" % (sys.argv[1])
        if not os.path.isfile(fn):
            print("Document ID not found: %s" % (sys.argv[1]))
            exit()

        with open(fn, "r") as f:
            document = json.load(f)

        document_history = document["document_history"]
        suggestions = document["suggestions"]
        print(len(suggestions))
        tracks = run_suggestion_tracing(document_history, suggestions, printing=True)
        print(tracks)
