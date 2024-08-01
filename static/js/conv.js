// Anything related to the chat and the comment features
var active_comment_id = null;
var comments = start_document.comments;
var chat_conv = start_document.conversation;
var chat_disabled = $("body").hasClass("no_chat");

function conv2html(conversation, chat_suggestions) {
    var chat_HTML = "";
    var num_messages = 0;
    var last_real = null;
    for(var message of conversation) {
        if((message.clear && message.clear == 1) || (message.retry && message.retry == 1)) {continue;}
        num_messages += 1;
        var chat_message_HTML = `<div class='chat_message_row'><div class='chat_message chat_${message.sender}'><div class='chat_message_text'>`;
        if(message.sender == "system") {
            // Materials info icon
            chat_message_HTML += "<span class='material-icons chat_message_icon'>info</span>";
        }
        if(message.sender == "user" || message.sender == "assistant") {
            last_real = message.sender;
        }
        chat_message_HTML += `${message.message}</div>`;
        chat_message_HTML += "</div></div>";
        chat_HTML += chat_message_HTML;
    }
    chat_HTML += `<div class='chat_actions'>`;
    if(chat_suggestions.length > 0) {
        var chat_highlighter = HIGHLIGHTER_SVG.replaceAll("#F77E65", "#000000");
        chat_HTML += `${chat_highlighter} ${chat_suggestions.length} ${chat_suggestions.length == 1 ? "suggestion" : "suggestions"} | <span class='chat_action' onclick="accept_chat_edits();">Accept All</span> | <span class='chat_action' onclick="reject_chat_edits();">Dismiss All</span>`;
    }

    if(num_messages > 1 && active_tab == "chat" && last_real == "assistant") {
        chat_HTML += `<div class='chat_retry_row'><span onclick="retry_chat();"><span class='material-icons chat_message_icon'>refresh</span> <span class='chat_action'>Retry</span></span></div>`;
    }
    chat_HTML += `</div>`;
    return chat_HTML;
}
function build_chat_conversation() {
    var chat_suggestions = suggestions.filter(s => s.suggestion_type == "CHAT");
    var chat_HTML = "";
    if(chat_conv.length > 1) {
        chat_HTML += `<div class='comment_actions'><span class='comment_archive' onclick="clear_chat();"><span class='material-icons'>delete</span> Clear</span></div>`;
    }
    chat_HTML += conv2html(chat_conv, chat_suggestions);
    $("#chat_messages").html(chat_HTML);
    $("#chat_messages").animate({ scrollTop: $('#chat_messages').prop("scrollHeight")}, 200);
}
function accept_chat_edits() {
    var chat_suggestion_ids = [];
    if(active_tab == "chat") {
        chat_suggestion_ids = suggestions.filter(s => s.suggestion_type == "CHAT").map(s => s.id);
    }
    else if(active_tab == "comment") {
        chat_suggestion_ids = suggestions.filter(s => s.suggestion_type == "COMMENT_"+active_comment_id).map(s => s.id);
    }
    if(chat_suggestion_ids.length == 0) {return;}
    accept_edits(chat_suggestion_ids);
}
function reject_chat_edits(callback_fn) {
    var chat_suggestion_ids = [];
    if(active_tab == "chat") {
        chat_suggestion_ids = suggestions.filter(s => s.suggestion_type == "CHAT").map(s => s.id);
    }
    else if(active_tab == "comment") {
        chat_suggestion_ids = suggestions.filter(s => s.suggestion_type == "COMMENT_"+active_comment_id).map(s => s.id);
    }
    if(chat_suggestion_ids.length == 0) {
        if(callback_fn) {callback_fn();}
        return;
    }
    reject_edits(chat_suggestion_ids, callback_fn);
}
var chat_message_waiting = false;
function show_chat_spinner() {
    $(".chat_spinner").show(); $(".chat_send_icon").hide();
}
function hide_chat_spinner() {
    $(".chat_spinner").hide(); $(".chat_send_icon").show();
}
function retry_chat() {
    if(chat_message_waiting) {return false;}
    if(active_tab != "chat") {return false;}
    chat_message_waiting = true;
    show_chat_spinner();
    $(".chat_actions").hide();
    var pre_query_text = get_current_text();
    var post_obj = {"doc_id": active_doc_id};
    $.post(`${api_server}retry_chat`, post_obj, function(data) {
        chat_conv = data.conversation;
        var new_suggestions = data.suggestions;
        console.log("New suggestions", new_suggestions);
        chat_message_waiting = false;
        hide_chat_spinner();
        shift_and_save_suggestions(pre_query_text, new_suggestions, function() {
            reload_view();
            build_chat_conversation();
        });
    }, "json");
}
function send_chat() {
    var message = $(".chat_input:visible").val();
    if(!message) {return false;}
    if(chat_message_waiting) {return false;}
    console.log("Sending message", message);

    // If you say 'clear' or 'reset', then clear the chat
    if(message.toLowerCase() == "clear" || message.toLowerCase() == "reset" || message.toLowerCase() == "archive") {
        if(active_comment_id) {
            archive_comment(active_comment_id);
        }
        else {
            clear_chat();
        }
        return false;
    }

    chat_message_waiting = true;
    show_chat_spinner();
    $(".chat_input").val("");

    var pre_query_text = get_current_text();
    if(active_tab == "chat") {
        // Add the message to chat conv
        chat_conv.push({"sender": "user", "message": message});
        build_chat_conversation();

        var post_obj = {"doc_id": active_doc_id, "message": message};
        
        $.post(`${api_server}send_chat`, post_obj, function(data) {
            chat_conv = data.conversation;
            chat_message_waiting = false;
            hide_chat_spinner();
            shift_and_save_suggestions(pre_query_text, data.suggestions, function() {
                reload_view();
                build_chat_conversation();
            });
        }, "json");                
    }
    else if(active_tab == "comment") {
        add_comment_reply(message);
    }
    else {
        console.log("Unknown tab", active_tab);
    }
    return false;
}
function add_comment_reply(message) {
    var comment = comments.find(c => c.id == active_comment_id);

    comment.conversation.push({"sender": "user", "message": message});
    suggestions = suggestions.filter(s => s.suggestion_type != "COMMENT_"+active_comment_id);
    build_comment_conversation(active_comment_id);
    show_chat_spinner();

    var post_obj = {"doc_id": active_doc_id, "comment_id": active_comment_id, "message": message};
    console.log("Sending comment", post_obj);
    $.post(`${api_server}send_comment_reply`, post_obj, function(data) {
        comments = data.comments;
        suggestions = data.suggestions;
        chat_message_waiting = false;
        hide_chat_spinner();
        
        build_comment_conversation(active_comment_id);
        reload_view();
    }, "json");
}
function clear_chat() {
    reject_chat_edits(function() {
        var post_obj = {"doc_id": active_doc_id};
        $.post(`${api_server}clear_chat`, post_obj, function(data) {
            chat_conv = data.conversation;
            build_chat_conversation();
        }, "json");
    });
}
function start_comment_click() {
    var anchor_idx = get_text_anchor_idx();
    if(anchor_idx < 0) {
        console.log("Could not find selection text", selection_text);
        return;
    }
    start_comment(anchor_idx, selection_text);
}
function start_comment(anchor_idx, commented_text, callback_fn) {
    var post_obj = {"doc_id": active_doc_id, "anchor_idx": anchor_idx, "selection_text": commented_text};
    $.post(`${api_server}start_comment`, post_obj, function(data) {
        comments = data.comments; //.filter(c => c.status == "active");
        reload_view();
        build_comment_conversation(data.active_comment_id);
        $("#comment_send_container .chat_input").focus();
        if(callback_fn) {callback_fn();}
    }, "json");
}
function build_comment_conversation(comment_id) {
    var comment = comments.find(c => c.id == comment_id);
    var comment_suggestions = suggestions.filter(s => s.suggestion_type == "COMMENT_"+comment_id);
    if(!comment) {return;}

    if(active_comment_id != comment_id || active_tab != "comment") {
        $(".active_comment").removeClass("active_comment");
        active_comment_id = comment_id;
        change_tab("comment");
        $(`#comment_span_${comment_id}`).addClass("active_comment");
    }

    var comment_HTML = `<div class='comment_actions'><span class='comment_archive' onclick="archive_comment('${comment_id}');"><span class='material-icons'>archive</span> Resolve</span></div>`;
    if(comment.conversation.length == 0) {
        comment_HTML += "<div class='comment_no_message'>Write a message to get suggestions.</div>";
    }
    
    comment_HTML += conv2html(comment.conversation, comment_suggestions);
    $("#comment_explainer").hide();
    $("#comment_chat_content").html(comment_HTML);
    $("#comment_chat_content").animate({ scrollTop: $('#comment_chat_content').prop("scrollHeight")}, 200);
    if(comment_suggestions.length > 0) {
        reload_view(); // might be required
    }
}
function archive_comment(comment_id) {
    var post_obj = {"doc_id": active_doc_id, "comment_id": comment_id};
    $.post(`${api_server}archive_comment`, post_obj, function(data) {
        comments = data.comments.filter(c => c.status == "active");
        suggestions = data.suggestions;
        reload_view();
        change_tab("chat");
    }, "json");
}