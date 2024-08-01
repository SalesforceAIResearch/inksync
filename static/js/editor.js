var line_index = 0, position = 0;
var cursor_index = { line_index, position };
var doc_history = start_document.document_history;
var current_text = doc_history[doc_history.length-1].text;
var local_disabled = $("body").hasClass("no_local");
var selection_text;
var active_tab = "";

String.prototype.replaceAll = function(search, replacement) {
    var target = this;
    return target.replace(new RegExp(search, 'g'), replacement);
};


function get_current_text() {
    var htmlContent = $("#main_container").html();
    var tempElement = document.createElement('div');
    tempElement.style.display = 'none';
    tempElement.innerHTML = htmlContent;
    
    $(tempElement).find(".no_show").remove();
    $(tempElement).find(".inline_visible").remove();
    tempElement.innerHTML = tempElement.innerHTML.replaceAll("<div><br></div>", "<br>").replaceAll("</div>", "<br>").replaceAll("<div>", "")                
    tempElement.innerHTML = tempElement.innerHTML.replaceAll("<br>", "\n");
    
    var plainText = tempElement.textContent || tempElement.innerText;
    tempElement.remove();
    // If the last character is \n then remove it
    if(plainText[plainText.length-1] == "\n") {
        plainText = plainText.substring(0, plainText.length-1);
    }
    calculate_stats_row();
    return plainText;
}
function save_new_text() {
    var new_text = get_current_text();
    var shift_obj = shift_suggestions(current_text, new_text, suggestions);
    suggestions = shift_obj.new_suggestions;
    comments = shift_obj.new_comments;
    var delete_suggestion_ids = shift_obj.delete_suggestion_ids;
    current_text = new_text;
    calculate_stats_row();
    return delete_suggestion_ids;
}
function save_document_state(user_accepted_suggestion_ids, user_rejected_suggestion_ids, callback_fn) {
    var new_plain_text = get_current_text();
    if(new_plain_text == current_text && !user_accepted_suggestion_ids && !user_rejected_suggestion_ids) {
        console.log("... but it was skipped");
        if(callback_fn) callback_fn(); // Nothing has changed, don't save
        return;
    }
    if(!user_accepted_suggestion_ids) user_accepted_suggestion_ids = [];
    if(!user_rejected_suggestion_ids) user_rejected_suggestion_ids = [];
    var auto_del_sug_ids = save_new_text();

    user_accepted_suggestion_ids = JSON.stringify(user_accepted_suggestion_ids);
    user_rejected_suggestion_ids = JSON.stringify(user_rejected_suggestion_ids);
    user_autodel_suggestion_ids = JSON.stringify(auto_del_sug_ids);

    var post_obj = {"doc_id": active_doc_id, "new_text": new_plain_text, "user_accepted_suggestion_ids": user_accepted_suggestion_ids, "user_rejected_suggestion_ids": user_rejected_suggestion_ids, "user_autodel_suggestion_ids": user_autodel_suggestion_ids, "current_suggestions": JSON.stringify(suggestions), "current_comments": JSON.stringify(comments)};
    $.post(`${api_server}save_doc_state`, post_obj, function(data) {
        if(callback_fn) {
            callback_fn();
        }
    }, "json").fail(function(data) {
        console.log("Failed to get suggestions");
    });
}
function shift_and_save_suggestions(pre_query_text, new_suggestions, callback_fn) {
    // A (potentially long) query has run, and we received suggestions based on that version.
    // We need to optionally shift those suggestions, and save the new ones.
    // If there are loose ends, we probably need to save that.
    console.log("In the shifting::", new_suggestions)
    save_document_state([], [], function() {
        var delete_suggestion_ids = [];
        var any_change = false;
        if(pre_query_text == current_text) {
            // No shifting needed
            suggestions = new_suggestions;
        }
        else {
            var shift_obj = shift_suggestions(pre_query_text, current_text, new_suggestions);
            suggestions = shift_obj.new_suggestions; // new suggestions that have been shifted   
            delete_suggestion_ids = shift_obj.delete_suggestion_ids;
            any_change = shift_obj.any_change; 
        }
        console.log("Post shifting::", suggestions)
        if(delete_suggestion_ids.length > 0 || any_change) {
            save_document_state(); // Save the ones that directly got deleted
        }
        if(callback_fn) {callback_fn();}
    });
}
function is_suggestion_present(text, suggestion) {
    // Check that the suggestion.original_text is present at suggestion.anchor_idx
    var start_idx = suggestion.anchor_idx;
    var end_idx = start_idx + suggestion.original_text.length;
    is_present = text.substring(start_idx, end_idx) == suggestion.original_text
    if(!is_present) {
        // console.log("Suggestion not present", suggestion);
    }
    return is_present;
}
function reload_view() {
    var annotations = [], occupied_ranges = [];
    // 1. Add the brainstorm if there is one                
    if(brainstorm_obj && !local_disabled) {
        var anchor_idx = brainstorm_obj.anchor_idx;
        var end = anchor_idx + brainstorm_obj.selection_text.length;
        occupied_ranges.push({"start": anchor_idx, "end": end}); // make sure other suggestions are not displayed
        var brainstorm_sugg = {"anchor_idx": anchor_idx, "original_text": brainstorm_obj.selection_text, "suggestion_type": "BRAINSTORM_SYSTEM"};
        if(is_suggestion_present(current_text, brainstorm_sugg)) {
            annotations.push(brainstorm_sugg);
        }
    }

    // 2. add comments
    for(var comment of comments) {
        comment.original_text = comment.selection_text;
        if(comment.status != "active" || local_disabled) {continue;} // Only show active comments
        var anchor_idx = comment.anchor_idx;
        var end = anchor_idx + comment.selection_text.length;
        var comment_suggestions = suggestions.filter(s => s.suggestion_type == "COMMENT_"+comment.id);
        if(comment.id == active_comment_id && comment_suggestions.length > 0) {
            for(var sugg of comment_suggestions) {
                if(is_suggestion_present(current_text, sugg)) {
                    var sugg_anchor_idx = sugg.anchor_idx;
                    var sugg_end = sugg_anchor_idx + sugg.original_text.length;
                    if(!any_overlap(sugg_anchor_idx, sugg_end, occupied_ranges)) {
                        var new_sugg = JSON.parse(JSON.stringify(sugg));
                        new_sugg.suggestion_type = "COMMENT_SUGGESTION";
                        occupied_ranges.push({"start": sugg_anchor_idx, "end": sugg_end}); // make sure other suggestions are not displayed
                        annotations.push(new_sugg);
                    }
                }
            }
        }
        if(!any_overlap(anchor_idx, end, occupied_ranges)) {
            // Add the comment itself, if it fits in
            if(is_suggestion_present(current_text, comment)) {
                occupied_ranges.push({"start": anchor_idx, "end": end}); // make sure other suggestions are not displayed
                annotations.push({"id": comment.id, "anchor_idx": anchor_idx, "original_text": comment.selection_text, "suggestion_type": "COMMENT"});
            }
        }
    }
    // 3. add suggestions
    for(var sugg of suggestions) {
        // If the suggestion starts with COMMENT_, then skip it, we've already dealt with it
        sugg.visible=false; // used for marker counting
        if(sugg.suggestion_type.startsWith("COMMENT_")) {continue;}
        if(markers_disabled && sugg.suggestion_type != "CHAT") {continue;}
        if(chat_disabled && sugg.suggestion_type == "CHAT") {continue;}
        if(!is_suggestion_present(current_text, sugg)) {continue;}
        var anchor_idx = sugg.anchor_idx;
        var end = anchor_idx + sugg.original_text.length;
        if(!any_overlap(anchor_idx, end, occupied_ranges)) {
            sugg.visible = true;
            occupied_ranges.push({"start": anchor_idx, "end": end}); // make sure other suggestions are not displayed
            annotations.push(sugg);
        }
    }
    annotations.sort(function(a, b) {return b.anchor_idx - a.anchor_idx;});

    // Let's build the HTML
    var HTML = current_text;
    for(var i = 0; i < annotations.length; i++) {
        var anno = annotations[i];
        // For each sugg: split there, and add a <span> tag
        var anchor_idx = anno.anchor_idx;
        var end = anchor_idx + anno.original_text.length;
        var anno_type = anno.suggestion_type;
        
        var before = HTML.substring(0, anchor_idx);
        var after = HTML.substring(end);
        if(anno_type == "BRAINSTORM_SYSTEM") {
            var brainstorm_hover = `<div id="brainstorm_content" contenteditable="false" class="no_show"><div id="close_brainstorm" onclick="close_brainstorm();"><span class="material-icons">close</span></div><div id="brainstorm_suggestions"></div></div>`;
            HTML = before + `<span id="brainstorm_span">${anno.original_text} ${brainstorm_hover}</span>` + after;
        }
        else if(anno_type == "COMMENT") {
            HTML = before + `<span id="comment_span_${anno.id}" class="comment_span ${(active_comment_id == anno.id)?"active_comment":""}" contenteditable="false" onclick="build_comment_conversation('${anno.id}');">${anno.original_text}</span>` + after;
        }
        else {
            var marker = marker_map[anno.marker_id]; // If there's a marker and it is hidden, skip
            if(marker && marker.visible == "hidden") {continue;}
            HTML = before + build_suggestion_HTML(anno) + after;
        }
    }
    var new_HTML = fancy_nl2br(HTML);
    $("#main_container").html(new_HTML);
    if(cursor_index) {
        try {
            reload_cursor(cursor_index);
        } catch(e) {
            console.log("Failed to reload cursor", e);
        }
    }
    build_chat_conversation();
    build_marker_menu();
    calculate_stats_row();
}
function calculate_stats_row() {
    var N_words = current_text.split(" ").length + 1;
    var N_characters = current_text.length;

    $("#doc_num_words").html(N_words);
    $("#doc_num_chars").html(N_characters);
}
function fancy_nl2br(HTML) {
    var lines = HTML.split("\n");
    var new_HTML = "";
    for(var i = 0; i < lines.length; i++) {
        var line_HTML = "";
        var line_content = lines[i];
        if(line_content == "") {
            line_content = "<br>";
        }
        line_HTML = "<div>"+line_content+"</div>";
        new_HTML += line_HTML;
    }
    return new_HTML;
}
function get_visible_text(child) {
    if(child.nodeType == 3) {
        return child.textContent;
    }
    var tempElement = document.createElement('div');
    tempElement.style.display = 'none';
    tempElement.innerHTML = child.innerHTML;
    $(tempElement).find(".no_show").remove();
    $(tempElement).find(".inline_visible").remove();
    var plainText = tempElement.textContent || tempElement.innerText;
    tempElement.remove();
    return plainText;
}
function save_cursor() {
    const selection = window.getSelection();
    selection_text = selection.toString();
    $('#hover_button').hide();
    if (selection.rangeCount > 0) {
        var range = selection.getRangeAt(0);
        if($("#brainstorm_span").length > 0) {
            close_brainstorm();
        }
        if(selection_text.length > 0) {
            var rect = range.getBoundingClientRect();
            $("#hover_button").css("top", (rect.bottom+window.scrollY+7)+"px").css("left", (((rect.right+rect.left)/2)+window.scrollX)+"px").show();
        }

        var main_container = $("#main_container")[0];
        var original_parent = range.commonAncestorContainer;
        var line_div = original_parent;
        if(!line_div.parentElement) {return;}
        // continue going to parent until the direct parent is main_container
        while(line_div.parentElement != main_container) {
            line_div = line_div.parentElement;
            if(!line_div) {return;}
        }
        var subline_elem = original_parent;
        while(subline_elem.parentElement != line_div) {
            subline_elem = subline_elem.parentElement;
            if(!subline_elem) {return;}
        }
        
        var line_index = Array.from(main_container.children).indexOf(line_div);
        var position = range.startOffset;
        if(original_parent != line_div) {
            // We might be in a span or something, we need to add to the position the text length of all the left elements
            var line_div_children = line_div.childNodes;
            var subline_index = Array.from(line_div_children).indexOf(subline_elem);
            for(var i = 0; i < subline_index; i++) {
                var child = line_div_children[i];
                if(child.nodeType == 3) {
                    position += child.textContent.length;
                } else {
                    // position += get_visible_text(child).length;
                    position += child.innerText.length;
                }
            }
        }
        cursor_index = { line_index, position };
    }
}
function reload_cursor(cursor_index) {
    // return; // Temporary for the demo
    var lineIndex = cursor_index.line_index;
    var position = cursor_index.position;
    var mainContainer = $("#main_container")[0];
    var lineDiv = mainContainer.children[lineIndex];
    var sublineElem = lineDiv.firstChild;
    var offset = 0;
    while (sublineElem) {
        // var sublineLength = sublineElem.textContent.length;
        var sublineLength = get_visible_text(sublineElem).length;
        if (offset + sublineLength >= position) {
        var range = document.createRange();
        
        if(sublineElem.nodeType != 3) {
            // It might be a <br /> in which case it's not type 3 but doesn't have a firstChild
            if(sublineElem.firstChild) {
                sublineElem = sublineElem.firstChild;
            }
        }

        range.setStart(sublineElem, position - offset);
        range.setEnd(sublineElem, position - offset);
        var selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        return;
        }
        offset += sublineLength;
        sublineElem = sublineElem.nextSibling;
    }
    console.log("Could not find cursor position", cursor_index, offset);
}
function get_text_anchor_idx() {
    var indices = [];
    var idx = current_text.indexOf(selection_text);
    while(idx != -1) {
        indices.push(idx);
        idx = current_text.indexOf(selection_text, idx+1);
    }
    if(indices.length == 0) {
        return -1;
    }

    // Now for each index, find its line index
    var best_line_diff = 100;
    var anchor_idx = -1;
    for(var i = 0; i < indices.length; i++) {
        var idx = indices[i];
        var line_index = current_text.substring(0, idx).split("\n").length - 1;
        var line_diff = Math.abs(line_index - cursor_index.line_index);
        if(line_diff < best_line_diff) {
            best_line_diff = line_diff;
            anchor_idx = idx;
        }
    }
    return anchor_idx;
}
function save_document_title(doc_id) {
    var new_title = $("#document_name_input").val();
    var post_obj = {"doc_id": doc_id, "new_title": new_title};
    $.post(`${api_server}save_document_title`, post_obj, function(data) {
        $(`.document_item_${doc_id} span`).html(new_title);
    }, "json");
}
function change_tab(new_tab) {
    $(".active_tab").removeClass("active_tab");
    $(`#${new_tab}_tab`).addClass("active_tab");
    $(".tab_content").hide();
    $(`.tab_${new_tab}_content`).show();
    active_tab = new_tab;
    if(new_tab == "chat") {
        active_comment_id = null;
        $(".active_comment").removeClass("active_comment");
        $("#comment_explainer").show();
        $("#comment_chat_content").html("");
        reload_view(); // In case comment suggestions were visible
    }
    else if(new_tab == "comment") {
        if(active_comment_id) {
            $("#comment_send_container").show();
        }
        else {
            $("#comment_send_container").hide();
        }
    }
    if(new_tab != "verify") {
        $("#verify_loading, #verify_content").hide();
        $("#verify_explainer").show();
    }
}
function handle_editor_change(e) {
    save_cursor();
    markers_on_editor_change();
}
