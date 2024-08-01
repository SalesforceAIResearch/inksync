// If click ESC, cancel marker_timer if it exists
$(document).keyup(function(e) {
    if (e.key === "Escape") { // escape key maps to keycode `27`
        // if there's an active comment, close it
        var action_taken = markers_on_escape_key();
        if(!action_taken) {
            if(active_comment_id) {
                change_tab("chat");
            }
            else if($("#brainstorm_span").length > 0) {
                close_brainstorm();
            }
        }
    }
});
function shortcut_bracket_check(key_code) {
    // See if there is any selection_text, if so
    var should_prevent_default = false;
    var anchor_idx = -1, end_anchor_idx = -1;
    var inside_text = "";
    save_new_text();

    var latest_text = current_text+"";
    if(selection_text.length > 0) {
        var anchor_idx = get_text_anchor_idx();
        if(anchor_idx >= 0) {
            inside_text = selection_text;
            should_prevent_default = true;
        }
        end_anchor_idx = anchor_idx+inside_text.length;
    }
    else {
        // Here, we are going to check: if it is a closing bracket, and there is an opening bracket not yet closed, then this closes it & we should trigger a query
        save_cursor();
        var line = current_text.split("\n")[cursor_index.line_index];
        var line_before_cursor = line.substring(0, cursor_index.position);
        var line_after_cursor = line.substring(cursor_index.position);
        console.log("Line before cursor", line_before_cursor);
        console.log("Line after cursor", line_after_cursor);
        if(key_code == 221 && line_before_cursor.indexOf("[") >= 0) {
            // get all the text before the cursor
            console.log("Found a closing bracket, and there is an opening bracket not yet closed");
            var opening_bracket_idx = line_before_cursor.lastIndexOf("[");
            inside_text = line_before_cursor.substring(opening_bracket_idx+1);
            anchor_idx = latest_text.indexOf(inside_text) - 1; // get rid of the opening bracket
            end_anchor_idx = anchor_idx+inside_text.length + 1; // Add the opening brack
            should_prevent_default = true;
        }
        else if(key_code == 219 && line_after_cursor.indexOf("]") >= 0) {
            // get all the text after the cursor
            console.log("Found an opening bracket, and there is a closing bracket not yet opened");
            var closing_bracket_idx = line_after_cursor.indexOf("]");
            inside_text = line_after_cursor.substring(0, closing_bracket_idx);
            console.log(">>>>", inside_text);
            anchor_idx = latest_text.indexOf(inside_text);
            end_anchor_idx = anchor_idx+inside_text.length + 1; // Remove the closing bracket
            should_prevent_default = true;
        }
    }
    if(inside_text.length > 0 && anchor_idx >= 0) {
        var new_text = latest_text.substring(0, anchor_idx) + "[" + inside_text + "]" + latest_text.substring(end_anchor_idx);
        var shift_obj = shift_suggestions(latest_text, new_text, suggestions);
        suggestions = shift_obj.new_suggestions;
        comments = shift_obj.new_comments;
        current_text = new_text;
        
        reload_view();
        markers_on_escape_key(); // force the markers to abord
        // Get the new anchor_idx, and the query_text
        var query_anchor_idx = anchor_idx;
        var query_text = "["+inside_text+"]";
        save_document_state([], [], function() {
            var post_obj = {"doc_id": active_doc_id, "query": query_text};
            $.post(`${api_server}interpret_shortcut`, post_obj, function(data) {
                console.log("Got shortcut interpretation", data);
                if(data.response == "BRAINSTORM") {
                    // We want to run it as a brainstorm query
                    // start_brainstorm(cursor_line_index, cursor_position, query_text, anchor_idx)
                    start_brainstorm(cursor_index.line_index, cursor_index.position, query_text, query_anchor_idx);
                }
                else {
                    // We want to run it as a comment query: (1) replace that text with a space " ", (2) assign a comment to this space
                    // var comment_string = "[COMMENT: "+inside_text+"]";
                    var comment_string = "[COMMENT]";
                    var new_text = current_text.substring(0, query_anchor_idx) + comment_string + current_text.substring(query_anchor_idx+query_text.length);
                    var shift_obj = shift_suggestions(current_text, new_text, suggestions);
                    suggestions = shift_obj.new_suggestions;
                    comments = shift_obj.new_comments;
                    current_text = new_text;
                    reload_view();
                    save_document_state([], [], function() {
                        start_comment(query_anchor_idx, comment_string, function() {
                            // Add a comment 
                            console.log(">>>", active_comment_id, inside_text);
                            add_comment_reply(inside_text);
                        });
                    });
                }
            });
        });
    }
    return should_prevent_default;
}