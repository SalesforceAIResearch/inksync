var markers = start_document.markers;
var marker_timer = null;
var marker_edit_id = null;
var marker_map = {};
var markers_in_progress = false;

var markers_disabled = true;

function clear_markers() {
    clearInterval(marker_timer);
}

function markers_on_editor_change() {
    clear_markers();
    $("#countdown_nb").html("5");
    if(!markers_disabled && !markers_in_progress) {
        $("#markers_countdown").fadeIn(200);
    }
    marker_timer = setInterval(function() {
        var countdown = parseInt($("#countdown_nb").html());
        if(countdown > 0) {
            $("#countdown_nb").html(countdown-1);
        }
        else {
            clear_markers();
            if (!markers_disabled && !markers_in_progress) {
                $("#markers_countdown").fadeOut(200);
                get_marker_suggestions();
            }
            else {
                console.log("Things got saved here...");
                save_document_state();
            }
            
        }
    }, 1000);
}
function get_marker_suggestions(focus_marker_id) {
    if(markers_disabled || markers_in_progress) {return;}
    if(!focus_marker_id) {focus_marker_id = "";}

    save_document_state([], [], function() {
        var post_obj = {"doc_id": active_doc_id, "focus_marker_id": focus_marker_id};
        $("#main_spinner").fadeIn(200);
        markers_in_progress = true;
        var pre_query_text = get_current_text();
        var callback_fn = function() {
            reload_view();
            if(active_comment_id) {
                build_comment_conversation(active_comment_id);
            }
        }
        $.post(`${api_server}get_markers_suggestions`, post_obj, function(data) {
            $("#main_spinner").fadeOut(200);
            markers_in_progress = false;
            if(data.suggestions) {
                shift_and_save_suggestions(pre_query_text, data.suggestions, callback_fn);
            }
            else {
                callback_fn();
            }
            
        }, "json").fail(function() {
            $("#main_spinner").fadeOut(200);
            markers_in_progress = false;
        });
    });
}
function markers_on_escape_key() {
    if(marker_timer) {
        clear_markers();
        save_document_state();
        $("#markers_countdown").fadeOut(200);
        return true;
    }
    return false;
}
function build_marker_menu() {
    var marker_menu_HTML = "";
    for(var marker of markers) {
        if(marker.deleted) {continue;}
        marker_map[marker.id]=  marker;
        var highlighter = HIGHLIGHTER_SVG.replaceAll("#F77E65", marker.strike_color);
        var num_suggestions = suggestions.filter(s => (s.marker_id == marker.id && s.visible)).length;
        marker_menu_HTML += `<div id='marker_${marker.id}' class='marker_item marker_${marker.visible}' onclick="change_marker_visibility('${marker.id}');">
            <span class='material-icons marker_visibility'>${(marker.visible === "visible")?"visibility":"visibility_off"}</span>
            ${highlighter}
            <span class='marker_name' style='border-style: ${marker.strike_style}; border-color: ${marker.strike_color};'>${marker.name}</span>`;
        if(num_suggestions > 0) {
            marker_menu_HTML += `<span class='marker_num_suggestions'>×${num_suggestions}</span>`;
        }

        marker_menu_HTML += `<div class='focus_marker' onclick="event.stopPropagation(); get_marker_suggestions('${marker.id}');"><span class='material-icons'>refresh</span></div>`;
        // Add an edit_note
        marker_menu_HTML += `<div class='edit_marker' onclick="event.stopPropagation(); edit_marker('${marker.id}');"><span class='material-icons'>edit_note</span></div>
        </div>`;
    }
    $("#marker_list").html(marker_menu_HTML);
    // Make the all marker visible if any of the markers are visible
    var any_visible = markers.find(m => m.visible === "visible");
    $("#marker_all_visibility").html((any_visible)?"visibility":"visibility_off");
}
function change_marker_visibility(marker_id) {
    var new_visible = "visible", marker_ids = [];
    if(marker_id == 'all') {
        new_visible = (!($("#marker_all_visibility").html() == "visibility"))?"visible":"hidden";
        marker_ids = markers.map(m => m.id);
    }
    else {
        var marker = markers.find(m => m.id == marker_id);
        if(!marker) {return;}
        new_visible = (marker.visible==="visible")?"hidden":"visible";
        marker_ids = [marker_id];
    }
    if(marker_ids.length == 0) {return;}
    var post_obj = {"doc_id": active_doc_id, "marker_ids": marker_ids.join(","), "visible": new_visible};
    $.post(`${api_server}change_marker_visibility`, post_obj, function(data) {
        for(var marker of markers) {
            if(marker_ids.includes(marker.id)) {
                marker.visible = new_visible;
            }
        }
        reload_view();
    }, "json");
}
function open_new_marker() {
    if(markers_disabled) {return;}
    $('#marker_del_btn').hide();
    marker_edit_id = null;
    // Back to default values
    $("#marker_name_input").val("");
    $("#marker_color_input").val("#E31E3E");
    $("#marker_style_input").val("solid");
    $("#marker_description_input").val("");
    $('#marker_form_container').show();
}
function edit_marker(marker_id) {
    if(markers_disabled) {return;}
    var marker = markers.find(m => m.id == marker_id);
    if(!marker) {return;}
    $("#marker_name_input").val(marker.name);
    $("#marker_color_input").val(marker.strike_color);
    $("#marker_style_input").val(marker.strike_style);
    $("#marker_description_input").val(marker.description);
    $('#marker_form_container').show();
    $('#marker_del_btn').show();
    marker_edit_id = marker_id;
}
function save_marker() {
    var marker_name = $("#marker_name_input").val();
    var marker_color = $("#marker_color_input").val();
    var marker_style = $("#marker_style_input").val();
    var marker_description = $("#marker_description_input").val();
    if(!marker_name) {
        alert("Please provide a name for the marker");
        return;
    }
    
    var marker_obj = {"name": marker_name, "strike_color": marker_color, "strike_style": marker_style, "description": marker_description};
    if(marker_edit_id) {
        // Then it's an update rather than an insertion
        marker_obj.id = marker_edit_id;
    }
    var marker_str = JSON.stringify(marker_obj);
    var post_obj = {"doc_id": active_doc_id, "marker": marker_str};
    $.post(`${api_server}save_marker`, post_obj, function(data) {
        markers = data.markers;
        build_marker_menu();
        $('#marker_form_container').hide();
    }, "json");
}
function delete_marker() {
    if(!marker_edit_id) {return;}
    var post_obj = {"doc_id": active_doc_id, "marker_id": marker_edit_id};
    $.post(`${api_server}delete_marker`, post_obj, function(data) {
        markers = data.markers;
        build_marker_menu();
        $('#marker_form_container').hide();
    }, "json");
}
function change_markers_to(marker_val, skip_api_save) {
    var new_marker_val = (marker_val == "1");
    if(new_marker_val != markers_disabled) {
        marker_enable_disable(true, skip_api_save);
    }

}
function marker_enable_disable(skip_rerun, skip_api_save) {
    markers_disabled = !markers_disabled;
    $('.checkbox_markers input[type="checkbox"]').prop("checked", !markers_disabled);

    var callback_fn = function() {
        var view_obj = {"doc_id": active_doc_id, "markers_disabled": (markers_disabled)?"1":"0"};
        if(!skip_api_save) {
            $.post(`${api_server}change_markers_disabled`, view_obj);
            if(!markers_disabled && !skip_rerun) {
                get_marker_suggestions(); // Run the markers!
            }
        }
    }

    if(markers_disabled) {
        // dismiss all marker suggestions
        all_marker_suggestions = suggestions.filter(s => (s.marker_id)).map(s => (s.marker_id));
        reject_edits(all_marker_suggestions, function() {
            reload_view();
            callback_fn();
        });
    }
    else {
        callback_fn();
    }
}