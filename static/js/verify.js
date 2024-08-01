function mark_verification_result(sugg_id, result) {
    var sugg = suggestions.find(s => s.id == sugg_id);
    if(!sugg && review_doc) {
        sugg = review_doc.suggestions.find(s => s.id == sugg_id);
    }                
    if(!sugg) {return;}

    var post_obj = {"doc_id": active_doc_id, "sugg_id": sugg_id, "result": result};
    $.post(`${api_server}mark_verification_result`, post_obj, function(data) {
        // We receive an updated suggestion
        sugg.verif_result = result;
        $(`.verify_button_${sugg_id}`).removeClass("active_verify_button");
        $(`.verify_button_${sugg_id}.verify_button_${result}`).addClass("active_verify_button");
        if($("body").hasClass("review_mode")) {
            display_review_doc();
        }
    }, "json");
}
function verify_edit(sugg_id) {
    var sugg = suggestions.find(s => s.id == sugg_id);
    if(!sugg && review_doc) {
        sugg = review_doc.suggestions.find(s => s.id == sugg_id);
    }
    if(!sugg) {return;}
    
    if(active_tab != "verify") {
        change_tab("verify");
    }
    if(sugg.verification_queries && sugg.verification_queries.length > 0) {
        console.log("Verifying edit", sugg)
        reload_verify_tab(sugg_id);
        return;
    }
    $("#verify_explainer, #verify_content").hide();
    $("#verify_loading").show();
    var post_obj = {};
    $.post(`${api_server}verify_suggestion/${active_doc_id}/${sugg_id}`, post_obj, function(data) {
        // We receive an updated suggestion
        var new_sugg = data.suggestion;
        // Replace it in the original suggestions
        suggestions = suggestions.map(s => (s.id == sugg_id) ? new_sugg : s);
        if(review_doc) {
            review_doc.suggestions = review_doc.suggestions.map(s => (s.id == sugg_id) ? new_sugg : s); // In case it comes from the review mode.
        }
        
        reload_verify_tab(sugg_id);
    }, "json");
}
function reload_verify_tab(sugg_id) {
    var sugg = suggestions.find(s => s.id == sugg_id);
    if(!sugg && review_doc) {
        sugg = review_doc.suggestions.find(s => s.id == sugg_id);
    }
    if(!sugg) {return;}
    $("#verify_loading, #verify_explainer").hide();
    var verify_HTML = "";
    if(sugg.verification_queries.length > 0) {
        verify_HTML += "<div class='verify_content_intro'>Here are some search queries that can help you verify the information. Click on them to open them in a new tab.</div>";
    }
    else {
        verify_HTML += "<div class='verify_content_intro'>Sorry, we couldn't find any search queries that can help you verify the information.</div>";
    }

    for(var i = 0; i < sugg.verification_queries.length; i++) {
        var verif_query = sugg.verification_queries[i];
        var verif_query_HTML = `<a href="${api_server}verify_suggestion/${active_doc_id}/${sugg_id}/${verif_query.id}" target="_new"><div class="verify_query ${verif_query.visited=='1'?'verif_query_visited':''}" id="verif_query_${verif_query.id}" onclick="$(this).addClass('verif_query_visited')">
            <span class='material-icons'>search</span>${verif_query.query}</div></a>`;
        verify_HTML += verif_query_HTML;
    }
    var verify_buttons_HTML = `<div class='verify_buttons'>
        <div class="verify_button verify_button_${sugg.id} verify_button_verified ${(sugg.verif_result=='verified')?'active_verify_button':''}" onclick="mark_verification_result('${sugg_id}', 'verified');"><span class='material-icons'>check_circle</span> Verified</div>
        <div class="verify_button verify_button_${sugg.id} verify_button_incorrect ${(sugg.verif_result=='incorrect')?'active_verify_button':''}" onclick="mark_verification_result('${sugg_id}', 'incorrect');"><span class='material-icons'>cancel</span> Incorrect</div>
        <div class="verify_button verify_button_${sugg.id} verify_button_not_sure ${(sugg.verif_result=='not_sure')?'active_verify_button':''}" onclick="mark_verification_result('${sugg_id}', 'not_sure');"><span class='material-icons'>help</span> Not sure</div>
    </div>`;
    $("#verify_content").html(verify_HTML).show();
    $("#verify_buttons").html(verify_buttons_HTML).show();
}
