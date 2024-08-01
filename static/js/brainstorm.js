var brainstorm_started = false, brainstorm_suggestions = [], brainstorm_obj = null;

function start_brainstorm_click() {
    var anchor_idx = get_text_anchor_idx();
    if(anchor_idx < 0) {
        console.log("Could not find selection text", selection_text);
        close_brainstorm();
        return;
    }
    return start_brainstorm(cursor_index.line_index, cursor_index.position, selection_text, anchor_idx);
}
function start_brainstorm(cursor_line_index, cursor_position, query_text, anchor_idx) {
    brainstorm_started = true;
    brainstorm_obj = {"doc_id": active_doc_id, "cursor_line_index": cursor_line_index, "cursor_position": cursor_position, "selection_text": query_text, "anchor_idx": anchor_idx};

    reload_view();
    $("#brainstorm_span").addClass("loading_brainstorm");

    $.post(`${api_server}start_brainstorm`, brainstorm_obj, function(data) {
        $("#brainstorm_span").removeClass("loading_brainstorm").addClass("loaded_brainstorm");
        $("#hover_button").hide();

        brainstorm_suggestions = data.brainstorm_suggestions;
        var brainstorm_content_HTML = "";
        for(var sugg of brainstorm_suggestions) {
            build_suggestion_HTML(sugg); // This builds the explanation_HTML
            brainstorm_content_HTML += `<div class='brainstorm_suggestion' onclick="accept_brainstorm_suggestion('${sugg.id}')">${sugg.explanation_HTML}</div>`;
        }
        $("#brainstorm_suggestions").html(brainstorm_content_HTML);
    }, 
    "json").fail(function(data) {
        console.log("Failed to get brainstorm suggestions");
        close_brainstorm();
    });
}
function onblur_brainstorm() {
    setTimeout(function() {
        if (!brainstorm_started) {
            $("#hover_button").hide();
        }
    }, 300);    
}

function accept_brainstorm_suggestion(sugg_id) {
    // Get the suggestion, add it to the main suggestions, reload the view, accept it, and close the brainstorm
    var sugg = brainstorm_suggestions.find(s => s.id == sugg_id);
    close_brainstorm();
    if(!sugg) {return;}
    suggestions.unshift(sugg);
    reload_view(); // important to reload view so that it is added in
    accept_edits([sugg_id]);
}
function close_brainstorm() {
    if(!brainstorm_started) {return;}
    brainstorm_started = false;
    brainstorm_obj = null;
    $("#hover_button").removeClass("loaded").removeClass("loading").hide();
    $("#brainstorm_suggestions").html("");
    $("#brainstorm_span").addClass("hidden_brainstorm");
    $("#brainstorm_content").hide();
}