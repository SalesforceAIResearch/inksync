var suggestions = start_document.suggestions.filter(s => !s.action);
var edit_view_type = "Hover"; // The two options are `hover` or `inline`

function shift_suggestions(old_text, new_text, suggestions, print) {
    var opcodes = new difflib.SequenceMatcher(null, old_text, new_text).getOpcodes();
    var any_change = false;
    var idx_map = {};
    for(var op of opcodes) {
        var tag = op[0], i1 = op[1], i2 = op[2], j1 = op[3], j2 = op[4];
        if(tag == "equal") {
            for(var i = i1, j = j1; i < i2; i++, j++) {
                idx_map[i] = j;
            }
        }
    }
    var delete_suggestion_ids = [];
    var new_suggestions = [];
    for(var old_suggestion of suggestions) {
        var start_idx = old_suggestion.anchor_idx;
        var end_idx = start_idx;
        if(old_suggestion.original_text) {
            end_idx += old_suggestion.original_text.length;
        }
        if(!(end_idx in idx_map) || !(start_idx in idx_map)) {
            // This text has been completely deleted from the end
            delete_suggestion_ids.push(old_suggestion.id);
            any_change = true;
            continue;
        }

        if(end_idx - start_idx != idx_map[end_idx] - idx_map[start_idx]) {
            // Something inside the edit has been deleted
            delete_suggestion_ids.push(old_suggestion.id);
            any_change = true;
            continue;
        }
        var new_start_idx = idx_map[start_idx];
        if(new_start_idx != start_idx) {
            any_change = true;
        }
        // Make a deep copy
        var new_suggestion = JSON.parse(JSON.stringify(old_suggestion));
        new_suggestion.anchor_idx = new_start_idx;
        new_suggestions.push(new_suggestion);
    }
    // Need to shift the comments as well
    for(var comment of comments) {
        var start_idx = comment.anchor_idx;
        var end_idx = start_idx;

        if(comment.selection_text) {
            end_idx += comment.selection_text.length;
        }

        // Check if in at the current index, there is the selection_text, if so do nothing
        if(new_text.substring(start_idx, end_idx) == comment.selection_text) {
            continue;
        }

        var new_start_idx = idx_map[start_idx];
        var new_end_idx = idx_map[end_idx];
        if(new_start_idx != start_idx) {
            any_change = true;
        }
        if(new_end_idx === undefined || new_start_idx === undefined) {
            // This text has been completely deleted from the end
            comment.status = "auto_deleted";
            any_change = true;
            continue;
        }
        else if(end_idx - start_idx != idx_map[end_idx] - idx_map[start_idx]) {
            comment.selection_text = new_text.substring(new_start_idx, new_end_idx);
        }
        comment.anchor_idx = new_start_idx;
    }
    return {"new_suggestions": new_suggestions, "new_comments": comments, "delete_suggestion_ids": delete_suggestion_ids, "any_change": any_change};
}
function build_suggestion_HTML(sugg) {
    if(!sugg.explanation_HTML) {
        // Compute the explanation in HTML
        if(sugg.replace_text !== null) {
            // We treat this edit as a replace
            var original_text = sugg.original_text;
            if(sugg.suggestion_type == "BRAINSTORM" && sugg.original_text.startsWith("[") && sugg.original_text.endsWith("]") && !sugg.replace_text.startsWith("[") && !sugg.replace_text.endsWith("]")) {
                original_text = sugg.original_text.substring(1, sugg.original_text.length - 1);
            }
            var original_words = original_text.replaceAll("\n", "<br>").split(" "); // For now, it's imperfect, but avoid newlines...
            var replace_words = sugg.replace_text.replaceAll("\n", "<br>").split(" "); // For now, it's imperfect, but avoid newlines...
            var opcodes = new difflib.SequenceMatcher(null, original_words, replace_words).getOpcodes();
            sugg.explanation_HTML = "";
            sugg.inline_HTML = "";
            for(var op of opcodes) {
                var tag = op[0], i1 = op[1], i2 = op[2], j1 = op[3], j2 = op[4];
                var ori = original_words.slice(i1, i2).join(" ");
                var rep = replace_words.slice(j1, j2).join(" ");
                if(tag == "equal") {
                    sugg.explanation_HTML += `<span class='explanation_equal'>${ori}</span>`;
                }
                if(tag == "delete") {
                    sugg.explanation_HTML += `<span class='explanation_delete'>${ori}</span>`;
                }
                if(tag == "insert") {
                    sugg.explanation_HTML += `<span class='explanation_insert'>${rep}</span>`;
                }
                if(tag == "replace") {
                    sugg.explanation_HTML += `<span class='explanation_delete'>${ori}</span>`;
                    sugg.explanation_HTML += `<span class='explanation_insert'>${rep}</span>`;
                }
            }
        }
    }
    var marker = marker_map[sugg.marker_id];
    var sugg_box_size = (sugg.explanation_HTML.length < 120) ? "hover_box_small" : "hover_box_medium"

    if(!marker) {
        if(sugg.suggestion_type == "CHAT") {
            marker = {"name": "Chat", "strike_color": "#000000", "strike_style": "solid"};
        }
        else if(sugg.suggestion_type == "COMMENT_SUGGESTION") {
            marker = {"name": "Comment Suggestion", "strike_color": "#ffc848", "strike_style": "solid", "background": "#fef1d8"};
        }
        else {
            console.log(">> Could not find marker", sugg.marker_id); // For now, invisible marker
            marker = {"name": "Invisible", "strike_color": "transparent", "strike_style": "solid"};
        }
    }

    var sugg_style = `style="border-bottom-style: ${marker.strike_style}; border-bottom-color: ${marker.strike_color}; ${marker.background ? `background-color: ${marker.background};` : ""}"`;
    var sugg_HTML = `<span id='suggestion_${sugg.id}' class='suggestion' ${sugg_style}><span class='inline_hidden'>${sugg.original_text.replaceAll("\n", "<br>")}</span><span class='inline_visible' contenteditable="false">${sugg.explanation_HTML}</span>`;
    sugg_HTML += `<div class='no_show hover_box ${sugg_box_size}' contenteditable="false"><div class='invis_connector'></div>`;

    var needs_verif = sugg.new_info == "yes";
    if(needs_verif) {
        // Add the warning if needed based on the 
        var warning_text = "Edit contains new <i>unverified information.</i>";
        sugg_HTML += `<div class='hover_box_row hover_box_warning_row warning_level_1'><span class='material-icons'>warning</span> ${warning_text}</div>`;
    }
    sugg_HTML += `<div class='hover_box_row hover_box_accept_row' onclick="accept_edits(['${sugg.id}']);"><span class='inline_hidden'>${sugg.explanation_HTML}</span><div class='accept_subtext'><span class='material-icons'>check</span> Accept Suggestion</div></div>`;
    if(needs_verif) {
        sugg_HTML += `<div class='hover_box_row hover_verify_row' onclick="verify_edit('${sugg.id}');"><span class='material-icons'>policy</span> Verify Suggestion</div>`;
    }
    sugg_HTML += `<div class='hover_box_row hover_reject_row' onclick="reject_edits(['${sugg.id}']);"><span class='material-icons'>close</span> Dismiss Suggestion</div>`;
    sugg_HTML += "</div>";
    sugg_HTML += "</span>";
    return sugg_HTML;
}
function accept_edits(sugg_ids) {
    for(var sugg_id of sugg_ids) {
        var sugg = suggestions.find(s => s.id == sugg_id);
        if(!sugg) {continue;}
        if(sugg.replace_text === null) {continue;}

        var replace_text = sugg.replace_text;
        $('#suggestion_'+sugg_id).html(replace_text).removeClass("suggestion").addClass("completed_suggestion");
        suggestions = suggestions.filter(s => s.id != sugg_id);
        if(active_comment_id && sugg.suggestion_type == "COMMENT_"+active_comment_id) {
            // We also need to update the span of the comment so it is up to date
            var comment = comments.find(c => c.id == active_comment_id);
            comment.selection_text = sugg.replace_text;
            comment.anchor_idx = sugg.anchor_idx;
        }
    }
    save_document_state(sugg_ids, [], function() {
        reload_view();
        if(active_comment_id) { // We need to update the comment
            build_comment_conversation(active_comment_id);
        }    
    });
}
function reject_edits(sugg_ids, callback_fn) {
    for(var sugg_id of sugg_ids) {
        var sugg = suggestions.find(s => s.id == sugg_id);
        if(sugg) {
            suggestions = suggestions.filter(s => s.id != sugg_id);
        }
    }
    save_document_state([], sugg_ids, function() {
        reload_view();
        if(active_comment_id) { // We need to update the comment
            build_comment_conversation(active_comment_id);
        }
        if(callback_fn) {callback_fn();}
    });
}
function any_overlap(start, end, ranges) {
    for(var range of ranges) {
        if(!(end <= range.start || range.end <= start)) {
            return true;
        }
    }
    return false;
}
function change_view_to(view, skip_api_save) {
    if(view != edit_view_type) {
        swap_view_mode(skip_api_save);
    }
}
function swap_view_mode(skip_api_save) {
    if(edit_view_type == "Inline") {
        edit_view_type = "Hover";
        $(".checkbox_view input[type='checkbox']").prop("checked", false);
    }
    else {
        edit_view_type = "Inline";
        $(".checkbox_view input[type='checkbox']").prop("checked", true);
    }
    var view_obj = {"doc_id": active_doc_id, "view_mode": edit_view_type};
    if(!skip_api_save) {
        $.post(`${api_server}change_view_mode`, view_obj);
    }
    change_view_type();
}
function change_view_type() {
    $("#view_type").html("&mdash; "+edit_view_type);
    if(edit_view_type == "Inline") {
        $("#main_container").addClass("inline_mode");
    }
    else {
        $("#main_container").removeClass("inline_mode");
    } 
}
