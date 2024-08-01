# To launch: `gunicorn --timeout 60 --bind unix:/export/home/inksync/app.sock -m 777 -w 5 wsgiis:app --reload`
from app_params import model_card, NO_LEFT_MENU, ENABLE_CHAT, ENABLE_MARKERS, ENABLE_LOCAL, ENABLE_WARN_VERIFY_AUDIT
from flask import Flask, request, render_template, send_from_directory, redirect
from utils_inksync import create_starter_document, get_user_documents
from model_recommender import RecommendationEngine
from utils_trace import run_suggestion_tracing
import utils_misc, json, os, time, pytz
from bson.objectid import ObjectId
from collections import Counter
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__)
app.debug = True
app.config["TEMPLATES_AUTO_RELOAD"] = True
CORS(app)

utils_misc.DoublePrint("logs/app.log")
API_LOG_FILE = "logs/api_log.jsonl"

engine = RecommendationEngine(model_card=model_card)


@app.before_request
def set_user_id():
    user_id = request.cookies.get('inksync_uid')
    if user_id is not None and not user_id.startswith("UU"):
        user_id = None
    request.start_ts = time.time()
    request.skip_log = False
    request.doc_id = -1

    if user_id is None:
        # Generate a unique ID using UUID4
        new_user_id = "UU%s" % str(ObjectId())
        with open("data/users.jsonl", "a") as f:
            f.write(json.dumps({"id": new_user_id, "creation_timestamp": datetime.now().isoformat()}) + "\n")
        request.user_id = new_user_id
    else:
        # If the user_id cookie is already set, store it in request.user_id
        request.user_id = user_id


# Set the cookie in the after_request hook
@app.after_request
def set_cookie(response):
    # Add entry to API log
    if not request.skip_log:
        response.set_cookie('inksync_uid', request.user_id, max_age=60 * 60 * 24 * 90)
        entry = {"timestamp": datetime.now().isoformat(), "user_id": request.user_id, "endpoint": request.path, "duration": time.time() - request.start_ts, "doc_id": request.doc_id}
        print("[%s] [User %s] %s" % (datetime.now(tz=pytz.timezone('America/New_York')).strftime("%Y-%m-%d %H:%M:%S"), request.user_id, request.path))
        with open(API_LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    return response


@app.route('/js/<path:path>')
def send_JS_static(path):
    request.skip_log = True
    return send_from_directory('static/js/', path)

@app.route('/css/<path:path>')
def send_css_static(path):
    request.skip_log = True
    return send_from_directory('static/css/', path)


@app.route("/new_doc")
def app_new_doc():
    new_doc = create_starter_document(request.user_id, initial_text="")
    doc_id = new_doc["id"]
    request.doc_id = doc_id
    doc_id = new_doc["id"]
    with open("documents/%s.json" % doc_id, "w") as f:
        json.dump(new_doc, f, indent=4)
    return redirect("/doc/%s" % doc_id)


@app.route("/")
def app_inksync_homepage():
    documents = get_user_documents(request.user_id)
    no_menu_class = "no_menu" if (request.args.get("no_menu", "false") != "false" or NO_LEFT_MENU) else ""
    return render_template("main.html", documents=documents, active_doc={}, homepage=True, no_menu_class=no_menu_class, hidden_systems_class="")


@app.route("/doc/<doc_id>")
@app.route("/doc/<doc_id>/review")
def app_inksync_docpage(doc_id=None):
    no_menu_class = "no_menu" if (request.args.get("no_menu", "false") != "false" or NO_LEFT_MENU) else ""

    documents = get_user_documents(request.user_id)
    id2doc = {d["id"]: d for d in documents}

    active_doc = {}
    if len(documents) > 0:
        if doc_id is None or doc_id not in id2doc:
            doc_id = documents[0]["id"]
            request.doc_id = doc_id

        active_doc = id2doc[doc_id]

    hidden_systems_class = ""
    if not ENABLE_CHAT:
        hidden_systems_class += " no_chat"
    if not ENABLE_MARKERS:
        hidden_systems_class += " no_markers"
    if not ENABLE_LOCAL:
        hidden_systems_class += " no_local"
    if not ENABLE_WARN_VERIFY_AUDIT:
        hidden_systems_class += " no_verify"
    return render_template("main.html", documents=documents, active_doc=active_doc, no_menu_class=no_menu_class, hidden_systems_class=hidden_systems_class)


@app.route("/save_document_title", methods=["POST"])
def app_save_document_title():
    doc_id = request.form["doc_id"]
    request.doc_id = doc_id
    new_title = request.form["new_title"]

    if os.path.exists("documents/%s.json" % doc_id):
        with open("documents/%s.json" % doc_id) as f:
            doc = json.load(f)
            doc["name"] = new_title
        with open("documents/%s.json" % doc_id, "w") as f:
            json.dump(doc, f, indent=4)

    return {"success": True}


@app.route("/change_view_mode", methods=["POST"])
def app_change_view_mode():
    doc_id = request.form["doc_id"]
    request.doc_id = doc_id
    view_mode = request.form["view_mode"]
    if view_mode not in ["Hover", "Inline"]:
        view_mode = "Hover"

    if os.path.exists("documents/%s.json" % doc_id):
        with open("documents/%s.json" % doc_id) as f:
            doc = json.load(f)
        if "view_mode_history" not in doc:
            doc["view_mode_history"] = []
        doc["view_mode"] = view_mode
        doc["view_mode_history"].append({"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "view_mode": view_mode})
        with open("documents/%s.json" % doc_id, "w") as f:
            json.dump(doc, f, indent=4)
        return {"success": True}
    return {"success": False}


@app.route("/change_markers_disabled", methods=["POST"])
def app_change_markers_disabled():
    doc_id = request.form["doc_id"]
    request.doc_id = doc_id
    markers_disabled = request.form["markers_disabled"]
    if markers_disabled not in ["0", "1"]:
        markers_disabled = "0"

    if os.path.exists("documents/%s.json" % doc_id):
        with open("documents/%s.json" % doc_id) as f:
            doc = json.load(f)
        doc["markers_disabled"] = markers_disabled
        with open("documents/%s.json" % doc_id, "w") as f:
            json.dump(doc, f, indent=4)
        return {"success": True}
    return {"success": False}


@app.route("/delete_doc/<doc_id>")
def app_delete_doc(doc_id):
    request.doc_id = doc_id
    if os.path.exists("documents/%s.json" % doc_id):
        # check if we're the owner_id
        with open("documents/%s.json" % doc_id) as f:
            doc = json.load(f)
            if doc.get("owner_user_id", -1) != request.user_id:
                return redirect("/")

        # remove file
        os.remove("documents/%s.json" % doc_id)
        
    return redirect("/")


@app.route("/save_marker", methods=["POST"])
def app_save_marker():
    doc_id = request.form["doc_id"]
    request.doc_id = doc_id
    marker = json.loads(request.form["marker"])

    if os.path.exists("documents/%s.json" % doc_id):
        with open("documents/%s.json" % doc_id) as f:
            doc = json.load(f)
            if "description" not in marker:
                marker["description"] = ""
            if "strike_style" not in marker:
                marker["strike_style"] = "solid"
            if "strike_color" not in marker:
                marker["strike_color"] = "#E31E3E"

            if "id" not in marker: # we insert it
                marker["id"] = str(ObjectId())
                doc["markers"].append(marker)
            else: # we update it
                for i, m in enumerate(doc["markers"]):
                    if m["id"] == marker["id"]:
                        doc["markers"][i] = marker
                        break
            marker["visible"] = "visible"

        with open("documents/%s.json" % doc_id, "w") as f:
            json.dump(doc, f, indent=4)

        return {"success": True, "markers": doc["markers"]}
    return {"success": False}


@app.route("/delete_marker", methods=["POST"])
def app_delete_marker():
    doc_id = request.form["doc_id"]
    request.doc_id = doc_id
    marker_id = request.form["marker_id"]

    if os.path.exists("documents/%s.json" % doc_id):
        with open("documents/%s.json" % doc_id) as f:
            doc = json.load(f)
            for marker in doc["markers"]:
                if marker["id"] == marker_id:
                    marker["deleted"] = 1

        with open("documents/%s.json" % doc_id, "w") as f:
            json.dump(doc, f, indent=4)

        return {"success": True, "markers": doc["markers"]}
    return {"success": False}


@app.route("/change_marker_visibility", methods=["POST"])
def app_change_marker_visibility():
    doc_id = request.form["doc_id"]
    request.doc_id = doc_id
    marker_ids = request.form["marker_ids"].split(",")
    new_visible = request.form["visible"]

    if os.path.exists("documents/%s.json" % doc_id):
        with open("documents/%s.json" % doc_id) as f:
            doc = json.load(f)
            for marker in doc["markers"]:
                if marker["id"] in marker_ids:
                    marker["visible"] = new_visible

        with open("documents/%s.json" % doc_id, "w") as f:
            json.dump(doc, f, indent=4)

        return {"success": True}
    return {"success": False}


@app.route("/save_doc_state", methods=["POST"])
def app_save_doc_state():
    doc_id = request.form["doc_id"]
    request.doc_id = doc_id
    new_text = request.form["new_text"]
    user_rejected_suggestion_ids = json.loads(request.form["user_rejected_suggestion_ids"])
    user_autodel_suggestion_ids = json.loads(request.form["user_autodel_suggestion_ids"])
    user_accepted_suggestion_ids = json.loads(request.form["user_accepted_suggestion_ids"])
    previous_suggestions = json.loads(request.form["current_suggestions"])
    active_comments = json.loads(request.form["current_comments"])

    if not os.path.exists("documents/%s.json" % doc_id):
        return {"success": False}

    with open("documents/%s.json" % doc_id, "r") as f:
        doc = json.load(f)
        all_suggestions = doc["suggestions"]

    latest_anchor_map = {sug["id"]: sug["anchor_idx"] for sug in previous_suggestions}

    for sug in all_suggestions:
        if sug["id"] in user_rejected_suggestion_ids:
            sug["action"] = "deleted_by_user"
        if sug["id"] in user_accepted_suggestion_ids:
            sug["action"] = "accepted_by_user"
            print(">> Accepted regular edit")
        if sug["id"] in user_autodel_suggestion_ids:
            sug["action"] = "autodel_by_user"
        if sug["id"] in latest_anchor_map:
            sug["anchor_idx"] = latest_anchor_map[sug["id"]]

    if len(user_accepted_suggestion_ids) > 0:
        # Check the brainstorm edits
        for sugg_id in user_accepted_suggestion_ids:
            for brainstorm in doc["brainstorms"]:
                if sugg_id in [s["id"] for s in brainstorm["suggestions"]]:
                    brainstorm["accepted_id"] = sugg_id
                    print(">> Accepted brainstorm edit.")

    # Need to also update the comments in case either the anchor_idx or the selection_text has changed
    comment_map = {c["id"]: c for c in doc["comments"]}
    for comment in active_comments:
        if comment["id"] in comment_map:
            old_comm = comment_map[comment["id"]]
            # skip if already archive
            if old_comm["status"] != "active":
                continue

            old_comm["anchor_idx"] = comment["anchor_idx"]
            old_comm["selection_text"] = comment["selection_text"]
            old_comm["status"] = comment["status"] # In case it was auto deleted

    accepted_type_counts = Counter([(s["suggestion_type"], "accepted") for s in all_suggestions if s["id"] in user_accepted_suggestion_ids] + [(s["suggestion_type"], "rejected") for s in all_suggestions if s["id"] in user_rejected_suggestion_ids])
    for (sug_type, acc_rej), count in accepted_type_counts.most_common():
        if sug_type == "CHAT":
            plural = "suggestions" if count > 1 else "suggestion"
            doc["conversation"].append({"id": str(ObjectId()), "sender": "system", "message": "%d chat %s %s." % (count, plural, acc_rej), "timestamp": datetime.now().isoformat()})
        elif sug_type.startswith("COMMENT_"):
            comment_id = sug_type.split("_")[1]
            if comment_id in comment_map:
                old_comm = comment_map[comment_id]
                plural = "suggestions" if count > 1 else "suggestion"
                old_comm["conversation"].append({"id": str(ObjectId()), "sender": "system", "message": "%d comment %s %s." % (count, plural, acc_rej), "timestamp": datetime.now().isoformat()})

    suggestion_ids = [s["id"] for s in all_suggestions if "action" not in s]
    doc["document_history"].append({"text": new_text, "suggestion_ids": suggestion_ids, "timestamp": datetime.now().isoformat(), "accepted_suggestion_ids": user_accepted_suggestion_ids}) # Last bit for tracability

    # Redo the write, and only return once the write is done
    with open("documents/%s.json" % doc_id, "w") as f:
        json.dump(doc, f, indent=4)
        f.flush()
        f.close()
    return {"success": True}


@app.route("/get_markers_suggestions", methods=["POST"])
def app_get_markers_suggestions():
    doc_id = request.form["doc_id"]
    request.doc_id = doc_id
    if not os.path.exists("documents/%s.json" % doc_id):
        return {"suggestions": []}

    with open("documents/%s.json" % doc_id, "r") as f:
        doc = json.load(f)
    text = doc["document_history"][-1]["text"]

    markers = doc["markers"]
    focus_marker_id = request.form["focus_marker_id"]

    active_markers = [m for m in markers if m.get("deleted", 0) == 0]
    is_focus_query = focus_marker_id != "" and focus_marker_id in [m["id"] for m in active_markers]

    new_suggestions = []
    if len(text) >= 20:
        if is_focus_query:
            active_markers = [m for m in active_markers if m["id"] == focus_marker_id]
        new_suggestions = engine.get_marker_suggestions(text, active_markers, document_id=doc_id)

    #  In case things have moved
    with open("documents/%s.json" % doc_id, "r") as f:
        doc = json.load(f)

    doc["suggestions"] += new_suggestions
    active_suggestions = [sug for sug in doc["suggestions"] if "action" not in sug]

    with open("documents/%s.json" % doc_id, "w") as f:
        json.dump(doc, f, indent=4)
    return {"suggestions": active_suggestions}


@app.route("/send_chat", methods=["POST"])
def app_send_chat():
    doc_id = request.form["doc_id"]
    user_id = request.user_id
    request.doc_id = doc_id
    message = request.form["message"]
    print("[Doc id: %s] [Chat message: %s]" % (doc_id, message))

    if os.path.exists("documents/%s.json" % doc_id):
        with open("documents/%s.json" % doc_id) as f:
            doc = json.load(f)
            doc["conversation"].append({
                "id": str(ObjectId()),
                "sender": "user",
                "message": message,
                "timestamp": datetime.now().isoformat()
            })

        for sug in doc["suggestions"]:
            if sug["suggestion_type"] == "CHAT" and "action" not in sug:
                sug["action"] = "deleted_by_model_chat"

        last_document = doc["document_history"][-1]['text']
        response = engine.generate_chat_response(last_document, doc["conversation"], document_id=doc_id)

        print("[Doc id: %s] [Chat; %d suggestions] [Message: %s]" % (doc_id, len(response["suggestions"]), response["reply"]))
        doc["conversation"].append({"id": str(ObjectId()), "sender": "assistant", "message": response["reply"], "timestamp": datetime.now().isoformat(), "suggestion_ids": [s["id"] for s in response["suggestions"]]})

        all_suggestions = doc["suggestions"] + response["suggestions"]

        active_suggestions = sorted([s for s in all_suggestions if "action" not in s], key=lambda x: x["suggestion_type"] != "CHAT")

        # Save the document history (with new suggestions) and the suggestions
        doc["suggestions"] = all_suggestions

        with open("documents/%s.json" % doc_id, "w") as f:
            json.dump(doc, f, indent=4)
        return {"success": True, "conversation": doc["conversation"], "suggestions": active_suggestions}
    else:
        return {"success": False}


@app.route("/clear_chat", methods=["POST"])
def app_clear_chat():
    doc_id = request.form["doc_id"]
    request.doc_id = doc_id

    if os.path.exists("documents/%s.json" % doc_id):
        with open("documents/%s.json" % doc_id) as f:
            doc = json.load(f)
            # Mark all the messages as "clear": 1
            for msg in doc["conversation"]:
                msg["clear"] = 1

            # Re-add the first message in
            doc["conversation"].append({"id": str(ObjectId()), "sender": "assistant", "message": "Don't hesitate to ask for edit suggestions in the chat.", "timestamp": datetime.now().isoformat()})

            # Dismiss all chat suggestions that were still pending
            for sug in doc["suggestions"]:
                if sug["suggestion_type"] == "CHAT" and "action" not in sug:
                    sug["action"] = "deleted_by_user"

        with open("documents/%s.json" % doc_id, "w") as f:
            json.dump(doc, f, indent=4)

        return {"success": True, "conversation": doc["conversation"]}
    else:
        return {"success": False}


@app.route("/retry_chat", methods=["POST"])
def app_retry_chat():
    doc_id = request.form["doc_id"]
    request.doc_id = doc_id

    if os.path.exists("documents/%s.json" % doc_id):
        with open("documents/%s.json" % doc_id) as f:
            doc = json.load(f)
            
        # Mark the last assistant message as retry: 1
        assistant_messages = [msg for msg in doc["conversation"] if msg["sender"] == "assistant"]
        del_suggestion_ids = []
        if len(assistant_messages) > 0:
            del_suggestion_ids = assistant_messages[-1]["suggestion_ids"]
            assistant_messages[-1]["retry"] = 1

        # Dismiss all chat suggestions that were still pending
        for sug in doc["suggestions"]:
            if "action" not in sug and sug["id"] in del_suggestion_ids:
                sug["action"] = "deleted_by_user_retry"

        last_document = doc["document_history"][-1]['text']
        response = engine.generate_chat_response(last_document, doc["conversation"], document_id=doc_id)

        print("[Doc id: %s] [Chat; %d suggestions] [Message: %s]" % (doc_id, len(response["suggestions"]), response["reply"]))
        doc["conversation"].append({"id": str(ObjectId()), "sender": "assistant", "message": response["reply"], "timestamp": datetime.now().isoformat(), "suggestion_ids": [s["id"] for s in response["suggestions"]]})

        all_suggestions = doc["suggestions"] + response["suggestions"]
        active_suggestions = sorted([s for s in all_suggestions if "action" not in s], key=lambda x: x["suggestion_type"] != "CHAT")

        with open("documents/%s.json" % doc_id, "w") as f:
            json.dump(doc, f, indent=4)

        return {"success": True, "conversation": doc["conversation"], "suggestions": active_suggestions}
    else:
        return {"success": False}


@app.route("/start_brainstorm", methods=["POST"])
def app_start_brainstorm():
    doc_id = request.form["doc_id"]
    request.doc_id = doc_id
    cursor_line_index = int(request.form["cursor_line_index"])
    cursor_position = int(request.form["cursor_position"])
    selection_text = request.form["selection_text"]

    if os.path.exists("documents/%s.json" % doc_id):
        with open("documents/%s.json" % doc_id) as f:
            doc = json.load(f)

            latest_doc = doc["document_history"][-1]["text"]

            response = engine.generate_brainstorm(latest_doc, latest_doc, cursor_line_index, cursor_position, selection_text, document_id=doc_id)
            suggestions = response["suggestions"]

            doc["brainstorms"].append({
                "id": str(ObjectId()),
                "cursor_line_index": cursor_line_index,
                "cursor_position": cursor_position,
                "selection_text": selection_text,
                "timestamp": datetime.now().isoformat(),
                "suggestions": suggestions
            })

        with open("documents/%s.json" % doc_id, "w") as f:
            json.dump(doc, f, indent=4)

        return {"brainstorm_suggestions": suggestions}
    return {"brainstorm_suggestions": []}


@app.route("/start_comment", methods=["POST"])
def app_start_comment():
    doc_id = request.form["doc_id"]
    request.doc_id = doc_id
    anchor_idx = int(request.form["anchor_idx"])
    selection_text = request.form["selection_text"]

    if os.path.exists("documents/%s.json" % doc_id):
        with open("documents/%s.json" % doc_id) as f:
            active_comment_id = str(ObjectId())
            doc = json.load(f)
            doc["comments"].append({
                "id": active_comment_id,
                "anchor_idx": anchor_idx,
                "selection_text": selection_text,
                "creation_timestamp": datetime.now().isoformat(),
                "conversation": [],
                "accepted_suggestion_ids": [],
                "status": "active",
            })

        with open("documents/%s.json" % doc_id, "w") as f:
            json.dump(doc, f, indent=4)

        return {"comments": doc["comments"], "active_comment_id": active_comment_id}
    return {"comments": [], "active_comment_id": ""}


@app.route("/send_comment_reply", methods=["POST"])
def app_send_comment_chat():
    doc_id = request.form["doc_id"]
    request.doc_id = doc_id
    user_id = request.user_id
    comment_id = request.form["comment_id"]
    message = request.form["message"]

    print("[Doc id: %s] [Message: %s]" % (doc_id, message))

    if os.path.exists("documents/%s.json" % doc_id):
        with open("documents/%s.json" % doc_id) as f:
            doc = json.load(f)

        comments = [c for c in doc["comments"] if c["id"] == comment_id]
        if len(comments) == 0:
            return {"comments": doc["comment"]}

        comment = comments[0]
        comment["conversation"].append({"id": str(ObjectId()), "sender": "user", "message": message, "timestamp": datetime.now().isoformat()})

        last_document = doc["document_history"][-1]['text']
        response = engine.generate_comment_response(last_document, last_document, comment["conversation"], comment["selection_text"], comment["anchor_idx"], document_id=doc_id)
        print("[Doc id: %s] [Comment Response; %d suggestions] [Message: %s]" % (doc_id, len(response["suggestions"]), response["reply"]))

        # In the document's suggestions, delete previous comment suggestions
        for sug in doc["suggestions"]:
            if sug["suggestion_type"] == "COMMENT_%s" % comment_id and "action" not in sug:
                sug["action"] = "deleted_by_model_comment"

        for sug in response["suggestions"]:
            sug["suggestion_type"] = "COMMENT_%s" % comment_id

        all_suggestions = doc["suggestions"] + response["suggestions"]
        new_suggestions = [sug for sug in all_suggestions if "action" not in sug]

        doc["suggestions"] = all_suggestions

        comment["conversation"].append({"id": str(ObjectId()), "sender": "assistant", "message": response["reply"], "timestamp": datetime.now().isoformat(), "suggestion_ids": [s["id"] for s in response["suggestions"]]})

        with open("documents/%s.json" % doc_id, "w") as f:
            json.dump(doc, f, indent=4)

        return {"success": True, "comments": doc["comments"], "suggestions": new_suggestions}

    return {"success": False, "comments": [], "suggestions": []}


@app.route("/archive_comment", methods=["POST"])
def app_archive_comment():
    doc_id = request.form["doc_id"]
    request.doc_id = doc_id
    comment_id = request.form["comment_id"]

    if os.path.exists("documents/%s.json" % doc_id):
        with open("documents/%s.json" % doc_id) as f:
            doc = json.load(f)
            for comment in doc["comments"]:
                if comment["id"] == comment_id:
                    comment["status"] = "archived"
                    comment["archive_timestamp"] = datetime.now().isoformat()

            for sug in doc["suggestions"]:
                if sug["suggestion_type"] == "COMMENT_%s" % comment_id and "action" not in sug:
                    sug["action"] = "deleted_by_comment_archive"

        with open("documents/%s.json" % doc_id, "w") as f:
            json.dump(doc, f, indent=4)

        new_suggestions = [sug for sug in doc["suggestions"] if "action" not in sug]
        return {"comments": doc["comments"], "suggestions": new_suggestions}
    return {"comments": []}


@app.route("/verify_suggestion/<doc_id>/<suggestion_id>", methods=["POST"])
def app_verify_suggestion(doc_id, suggestion_id):
    request.doc_id = doc_id
    if os.path.exists("documents/%s.json" % doc_id):
        with open("documents/%s.json" % doc_id) as f:
            doc = json.load(f)
        sug = [s for s in doc["suggestions"] if s["id"] == suggestion_id]
        if len(sug) > 0:
            sug = sug[0]
            latest_text = doc["document_history"][-1]["text"]
            if "verification_queries" not in sug or len(sug["verification_queries"]) == 0:
                response = engine.generate_verify_response(latest_text, sug, document_id=doc_id)
                sug["verification_queries"] = [{"id": str(ObjectId()), "query": q, "visited": "0"} for q in response]

        with open("documents/%s.json" % doc_id, "w") as f:
            json.dump(doc, f, indent=4)

        return {"success": True, "suggestion": sug}
    return {"success": False, "suggestion": {}}


@app.route("/verify_suggestion/<doc_id>/<suggestion_id>/<verification_query_id>", methods=["POST", "GET"])
def app_verify_suggestion_query(doc_id, suggestion_id, verification_query_id):
    request.doc_id = doc_id
    if os.path.exists("documents/%s.json" % doc_id):
        with open("documents/%s.json" % doc_id) as f:
            doc = json.load(f)
        sug = [s for s in doc["suggestions"] if s["id"] == suggestion_id]
        if len(sug) > 0:
            sug = sug[0]
            for q in sug["verification_queries"]:
                if q["id"] == verification_query_id:
                    q["visited"] = "1"
                    with open("documents/%s.json" % doc_id, "w") as f:
                        json.dump(doc, f, indent=4)
                    return redirect("https://www.google.com/search?q=%s" % q["query"]) # Redirect to Google search with query q["query"]

    return {"success": False, "suggestion": {}}


@app.route("/mark_verification_result", methods=["POST"])
def app_mark_verification_result():
    doc_id = request.form["doc_id"]
    request.doc_id = doc_id
    sugg_id = request.form["sugg_id"]
    result = request.form["result"]
    if result not in ["verified", "incorrect", "not_sure"]:
        result = ""

    if os.path.exists("documents/%s.json" % doc_id):
        with open("documents/%s.json" % doc_id) as f:
            doc = json.load(f)
        sug = [s for s in doc["suggestions"] if s["id"] == sugg_id]
        if len(sug) > 0:
            sug = sug[0]
            sug["verif_result"] = result
            print("[User ID: %s] [Suggestion Is Accurate: %s] [Verif Result: %s]" % (request.user_id, sug.get("is_inaccurate", "-1"), result))

        with open("documents/%s.json" % doc_id, "w") as f:
            json.dump(doc, f, indent=4)

        return {"success": True, "suggestion": sug}
    return {"success": False, "suggestion": {}}


@app.route("/get_review_doc", methods=["POST"])
def app_get_review_doc():
    doc_id = request.form["doc_id"]
    request.doc_id = doc_id
    if os.path.exists("documents/%s.json" % doc_id):
        with open("documents/%s.json" % doc_id) as f:
            doc = json.load(f)

        suggestions = doc["suggestions"]
        tracks = run_suggestion_tracing(doc["document_history"], suggestions, final_cleanup=True)
        sug_ids = set([t["suggestion_id"] for t in tracks])

        suggestions = [s for s in suggestions if s["id"] in sug_ids]

        sug_counts = Counter([t["suggestion_id"] for t in tracks])
        suggestions = sorted(suggestions, key=lambda x: sug_counts[x["id"]], reverse=True)
        final_version = doc["document_history"][-1]["text"]
        return {"review_doc": {"suggestions": suggestions, "tracks": tracks, "final_version": final_version.rstrip()}}
    return {"review_doc": []}


@app.route("/interpret_shortcut", methods=["POST"])
def app_interpret_shortcut():
    doc_id = request.form["doc_id"]
    request.doc_id = doc_id
    shortcut_query = request.form["query"]
    if os.path.exists("documents/%s.json" % doc_id):

        with open("documents/%s.json" % doc_id, "r") as f:
            doc = json.load(f)
        if doc is None:
            return {"success": False}
        latest_text = doc["document_history"][-1]["text"]

        response = engine.generate_shortcut_interpretation(latest_text, shortcut_query, document_id=doc_id)
        return {"success": True, "response": response}
    return {"success": False}
