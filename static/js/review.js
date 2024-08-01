var review_doc = null;

function hover_review_suggestion(sug_id, need_to_animate) {
    if(!review_doc) {return;}
    $('.active_track').removeClass('active_track');
    $('.review_track_'+sug_id).addClass('active_track');

    $('.active_review_sug').removeClass('active_review_sug');
    $('.review_sug_'+sug_id).addClass('active_review_sug');
    var sug_elem = $('.review_sug_'+sug_id)[0];
    var sug_elem_top = sug_elem.getBoundingClientRect().top;
    var sug_elem_bottom = sug_elem.getBoundingClientRect().bottom;
    var sug_elem_height = sug_elem_bottom - sug_elem_top;
    var sug_elem_parent = sug_elem.parentElement;
    var sug_elem_parent_top = sug_elem_parent.getBoundingClientRect().top;
    if(need_to_animate) {
        $("#review_sug_list").animate({scrollTop: sug_elem_parent.scrollTop + sug_elem_top - sug_elem_parent_top - sug_elem_height}, 200);
    }
}
function blur_review_suggestion() {
    $('.active_track').removeClass('active_track');
    $('.active_review_sug').removeClass('active_review_sug');
}
function display_review_doc() {
    if(!review_doc) {return;}
    console.log(review_doc)
    var tracks = review_doc.tracks;
    var rev_suggestions = review_doc.suggestions;
    var selected_tracks = [];
    tracks.sort(function(a, b) {return b.replace_text.length - a.replace_text.length;});
    var ranges = [];
    for(var track of tracks) {
        var anchor_idx = track.anchor_idx;
        var end = anchor_idx + track.replace_text.length;
        if(!any_overlap(anchor_idx, end, ranges)) {
            selected_tracks.push(track);
            ranges.push({"start": anchor_idx, "end": end});
        }
    }
    
    // sort tracks by inverse order of anchor_idx
    selected_tracks.sort(function(a, b) {return b.anchor_idx - a.anchor_idx;});

    var main_review_HTML = review_doc.final_version;
    var any_unchecked = false;
    for(var track of selected_tracks) {
        var anchor_idx = track.anchor_idx;
        var end = anchor_idx + track.replace_text.length;                    
        var sug = rev_suggestions.find(s => s.id == track.suggestion_id);
        var new_info = sug.new_info;
        var severity_level = "severity_1";
        if(new_info == "no") {
            severity_level = "severity_0";
        }
        if(sug.verif_result == "verified") {
            severity_level = "severity_verified";
        }
        else if(sug.verif_result == "incorrect") {
            severity_level = "severity_incorrect";
        }
        else if(sug.verif_result == "not_sure") {
            severity_level = "severity_not_sure";
        }
        else {
            any_unchecked = true;
        }
        var before = main_review_HTML.substring(0, anchor_idx);
        var after = main_review_HTML.substring(end);

        var sugg_HTML = `<span class='suggestion review_track review_track_${track.suggestion_id} ${severity_level}' onmouseover="hover_review_suggestion('${track.suggestion_id}', 1);" onmouseout="blur_review_suggestion();" onclick="verify_edit('${track.suggestion_id}');">${track.replace_text}`
        // onclick prevent default & stop propagation
        sugg_HTML += `<div class='no_show hover_box hover_box_medium' onclick="event.stopPropagation();"><div class='invis_connector'></div>`;
        if(new_info == "yes") {
            var warning_text = "Edit contains new <i>unverified information.</i>";
            sugg_HTML += `<div class='hover_box_row hover_box_warning_row warning_level_1'><span class='material-icons'>warning</span> ${warning_text}</div>`;
            sugg_HTML += `<div class='hover_box_row hover_verify_row' onclick="verify_edit('${track.suggestion_id}');"><span class='material-icons'>policy</span> Perform Verification</div>`;
            sugg_HTML += `<div class='quick_verify_buttons'><div class="verify_button verify_button_${sug.id} verify_button_verified ${(sug.verif_result=='verified')?'active_verify_button':''}"onclick="mark_verification_result('${sug.id}', 'verified');"><span class='material-icons'>check_circle</span> Verified</div><div class="verify_button verify_button_${sug.id} verify_button_incorrect ${(sug.verif_result=='incorrect')?'active_verify_button':''}" onclick="mark_verification_result('${sug.id}', 'incorrect');"><span class='material-icons'>cancel</span> Incorrect</div><div class="verify_button verify_button_${sug.id} verify_button_not_sure ${(sug.verif_result=='not_sure')?'active_verify_button':''}" onclick="mark_verification_result('${sug.id}', 'not_sure');"><span class='material-icons'>help</span> Not sure</div></div>`;
        }
        else {
            sugg_HTML += `<div class='hover_box_row hover_box_warning_row warning_level_0'><span class='material-icons'>verified</span> No new information</div>`;
        }
        sugg_HTML += "</div>";
        sugg_HTML += "</span>";
        main_review_HTML = before + sugg_HTML + after;
        ranges.push({"start": anchor_idx, "end": end});
     }
    var main_review_HTML = fancy_nl2br(main_review_HTML);
    $("#review_main_container").html(main_review_HTML);
    if(!any_unchecked && is_study2) {
        $("#study_btn3").removeClass("left_panel_button_disabled");
    }
    // Make the suggestion_list
    var sug_list_HTML = "";
    for(var sug of rev_suggestions) {
        var sug_tracks = tracks.filter(t => t.suggestion_id == sug.id);
        var new_info = sug.new_info;
        var severity_level = "sug_severity_0";
        if(new_info == "yes") {
            severity_level = "sug_severity_1";
        }

        if(sug.verif_result == "verified") {
            severity_level = "sug_severity_verified";
        }
        else if(sug.verif_result == "incorrect") {
            severity_level = "sug_severity_incorrect";
        }
        else if(sug.verif_result == "not_sure") {
            severity_level = "sug_severity_not_sure";
        }
        if(sug_tracks.length == 0) {
            severity_level = "sug_severity_deleted";
        }
        if(!sug.explanation_HTML) {
            build_suggestion_HTML(sug);
        }
        // Get last 4 characters of the id
        var short_name = sug.id.substring(sug.id.length - 4);
        sug_list_HTML += `<div class='review_suggestion review_sug_${sug.id} ${severity_level}' onmouseover="hover_review_suggestion('${sug.id}');" onclick="verify_edit('${sug.id}');"><div class='suggestion_name'>Suggestion ${short_name}</div><div class='explanation'>${sug.explanation_HTML}</div></div>`;
    }
    $("#review_sug_list").html(sug_list_HTML);
}
function start_review() {
    if($("body").hasClass("review_mode")) {
        $("body").removeClass("review_mode");
        // Remove the /review from the url
        var new_url = window.location.href.replace("/review", "");
        window.history.pushState({path:new_url},'',new_url);
    }
    else {
        $("body").addClass("review_mode");
        change_tab("verify");
        // Add the /review to the url, deal with ?get parameters appropriately
        var current_url = window.location.href;
        if(current_url.indexOf("?") > -1) {
            if(current_url.indexOf("/review?") == -1) {
                var new_url = current_url.replace("?", "/review?");
                window.history.pushState({path:new_url},'',new_url);
            }
        }
        else if(current_url.indexOf("/review") == -1) {
            var new_url = current_url + "/review";
            window.history.pushState({path:new_url},'',new_url);
        }
        $.post(`${api_server}get_review_doc`, {"doc_id": active_doc_id}, function(data) {
            review_doc = data.review_doc;
            display_review_doc();
        }, "json");
    }
}