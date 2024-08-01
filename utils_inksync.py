from app_params import DEFAULT_MARKERS, default_marker_type
from bson.objectid import ObjectId
from datetime import datetime
import sys, os, json


def get_user_documents(user_id):
    documents, id2doc = [], {}
    for fn in os.listdir("documents/"):
        if fn.endswith(".json") and fn.startswith("user_%s_" % user_id):
            with open("documents/" + fn) as f:
                try:
                    documents.append(json.load(f))
                except:
                    pass

    documents = sorted(documents, key=lambda x: x["document_history"][-1]["timestamp"], reverse=True)
    documents = [d for d in documents if d.get("owner_user_id", -1) == user_id]
    return documents


def create_starter_document(user_id, initial_text="", marker_type=None):
    marker_type = marker_type if marker_type else default_marker_type
    default_markers = DEFAULT_MARKERS[marker_type]
    # if doc_id is None:
    doc_id = "user_%s_%s" % (user_id, str(ObjectId()))
    return {
        "id": doc_id,
        "owner_user_id": user_id,
        "name": "New Document",
        "document_history": [{"text": initial_text, "timestamp": datetime.now().isoformat(), "suggestion_ids": []}],
        "suggestions": [],
        "markers": default_markers,
        "conversation": [
            {
                "id": str(ObjectId()),
                "sender": "assistant",
                "message": "Don't hesistate get help in the chat.",
                "timestamp": datetime.now().isoformat()
            }
        ],
        "brainstorms": [],
        "comments": [],
        "view_mode": "Inline",
        "markers_disabled": "0",
        "view_mode_history": []
    }

if __name__ == "__main__":

    if len(sys.argv) >= 2:
        doc_id = sys.argv[1]
        if os.path.isfile("documents/%s.json" % doc_id):
            with open("documents/%s.json" % doc_id, "r") as f:
                doc = json.load(f)
            
            doc["markers"] = DEFAULT_MARKERS["simplification"]
            with open("documents/%s.json" % doc_id, "w") as f:
                json.dump(doc, f, indent=2)
            
            print("Document updated!")
        else:
            print("Document not found!")
