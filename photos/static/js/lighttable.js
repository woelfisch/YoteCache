var this_catalog = "unknown";
var media_list = [];
var urls = {};

var first_date = display_timestamp(new Date(Date.now()).toISOString());
var last_date = display_timestamp(new Date(Date.now()).toISOString());

var may_edit = false;
var may_move = false;
var cache_size = 200;
var filmstrip_prefetch = 10;

var media_data = new Map();
var media_by_slide = [];

var csrftoken;
var cur_catalog_idx;

/* needs to be global as thumbnails get loaded asynchronously */
var cur_filmstrip_first = 0;
var cur_filmstrip_last = 0;


function verify_index(idx) {
    if (idx < 0) return 0;
    if (idx >=  media_list.length) return media_list.length-1;
    return idx;
}

var CacheAgeCounter = 0;

/* ===== set preview image ===== */

function set_preview_image(media) {
    $.mobile.loading("show");

    if (media)
        cur_catalog_idx = media_list.indexOf(media.id);

    if (!media || cur_catalog_idx < 0) {
        $("#media-rating").prop("disabled", true);
        $("#media-label").prop("disabled", true);
        $("#media-catalog").prop("disabled", true);
        $("#media-reject").prop("disabled", true);
        $("#media-bulk").prop("disabled", true);
        update_image_metadata({
            media_file: "No File",
            date: "1970-01-01T00:00:00Z",
            catalog: this_catalog,
            rating: 0,
            rejected: true,
            label: "None",
            exposure_time: .008,
            gain_value: 100,
            f_number: 8,
            focal_length: 50,
        });
    } else {
        $("#image-preview").css("background-image", "url("+media.preview+")");
        update_image_metadata(media);

        window.location.hash=media.id;
        set_filmstrip_slide();
        $("#image-fullsize").attr("src", media.fullsize);
        $("#media-home").attr("href", urls.index+"#"+media.id);
    }
}

/* ===== helper functions for preview window ===== */

function display_timestamp(date) {
    dt=date.split("T");
    return dt[0]+" "+dt[1].substr(0,5);
}

function exposure(tval) {
    if (tval < 1)
        return "1/"+(1/tval).toFixed(0);
    return tval.toFixed(0);
}

function rating_stars_main(element, rating) {
    var stars=$(element+" > .glyphicon");
    for (r=0; r < 5; r++) {
        if (r < rating) {
            $(stars[r]).removeClass("glyphicon-star-empty");
            $(stars[r]).addClass("glyphicon-star");
        } else {
            $(stars[r]).removeClass("glyphicon-star");
            $(stars[r]).addClass("glyphicon-star-empty");
        }
    }
}

function show_reject_main(rejected) {
    if (rejected) {
        $("#media-rejected-true").show();
        $("#media-rejected-false").hide();
    } else {
        $("#media-rejected-false").show();
        $("#media-rejected-true").hide();
    }
}

function show_label_main(label) {
    var color="grey"
    if (label && label != "None")
        color=label;
    $("#media-label > .glyphicon").css("color", color);
}

function sanitize_catalog(catalog) {
    return catalog.replace(/(^\s*)|(\s*$)|[\r\n/]/g, "");
}

function amend_catalog_dropdown(catalog, name, click_handler) {
    var found=false;
    $("."+name+"-link").each(function(idx) {
        if (sanitize_catalog($(this).text()) ==  catalog) {
            found=true;
            return false;
        }
    });
    if (found) return;

    catalog=catalog.replace(/[<>&'"]/g, function(s) { return "&#"+s.charCodeAt(0)+";"});

    var new_element = $(
    '<li role="presentation" class="'+name+'-item">'+
    '   <a role="menuitem" tabindex="-1" href="#" class="'+name+'-link">'+catalog+'</a>'+
    '</li>');

    new_element.insertBefore("."+name+" > ul > .endoflist");
    var anchor = new_element.children("a");
    anchor.on("click", click_handler);
}

function show_catalog_main(catalog) {
    amend_catalog_dropdown(catalog, "media-catalog", set_catalog)
    amend_catalog_dropdown(catalog, "bulk-condition-catalog", bulk_condition_set_catalog)
    amend_catalog_dropdown(catalog, "bulk-action-catalog", bulk_action_set_catalog)
}

function update_metadata_main(data) {
    $("#media-file").text(data.media_file)
    $("#media-date").text(display_timestamp(data.date));

    document.title="PhotoYote | "+$("#media-file").text()+" | "+$("#media-date").text()
    // $("#media-mime-type").text(data.mime_type);
    show_catalog_main(data.catalog);
    show_label_main(data.label);
    rating_stars_main("#media-rating", data.rating);
    show_reject_main(data.rejected);
    $("#media-exposure").text(exposure(data.exposure_time)+" s");
    $("#media-f-number").text(data.f_number);
    $("#media-focal-length").text(data.focal_length+" mm");
    $("#media-gain").text(data.gain_value);
}

/* ===== filmstrip ===== */

var event_queue = $.Deferred().resolve();
function get_media_data_from_server(json_string, func) {
        return $.ajax({
            url: urls.filmstrip,
            type: "POST",
            data: $.param({"csrfmiddlewaretoken":  csrftoken, "json": json_string}),
            dataType: "json",
            success: function(json) {
                for (var k=0; k < json.length; k++) {
                    var m = json[k].fields;
                    m['ts'] = CacheAgeCounter++;
                    m['tn'] = new Image();
                    m['tn'].src = m['thumbnail'];
                    media_data.set(m['id'], m);
                    func(m['id'], m);
                }
            },
            error: function(xhr, status, errorThrown) {
                console.log("Error: "+errorThrown);
                console.log("Status: "+status);
                console.dir( xhr);
            }
        });
}

function get_media_data_from_cache(items, func) {
    var toload = new Array();
    var ids;

    if (typeof items == 'number')
        ids = [items];

    if (Array.isArray(items))
        ids = items;

    for (var k=0; k < ids.length; k++) {
        if (media_data.has(ids[k])) {
            // console.log(ids[k]," in cache");
            var m=media_data.get(ids[k]);
            m['ts'] = CacheAgeCounter++;
            func(ids[k], m);
        } else {
            // console.log(ids[k]," not in cache");
            toload.push(ids[k]);
        }
    }

    return toload;
}

var last_event;
function get_media_data(items, func) {
    var toload = get_media_data_from_cache(items, func);

    if (toload.length > 0) {
        if (event_queue.state() == "pending") {
            last_event = last_event.then(function() { return get_media_data(toload, func); });
        } else {
            event_queue = get_media_data_from_server(JSON.stringify({"ids": toload}), func);
            last_event = event_queue;
        }

        var len = media_data.size - cache_size;
        if (len > 0) {
            var ats = new Array();
            var cur_id = media_list[cur_catalog_idx];
            media_data.forEach(function(val, key, obj) {
            if (val['id'] != cur_id)        // do not expire current image
                    ats.push([val['ts'], key]);
            });
            ats.sort(function(a, b) { return a[0]-b[0]; });
            // console.log('expiring', len, 'out of', ats.length, 'cache entries');
            for (var k=0; k < len; k++) {
                // console.log('expiring', ats[k][1]);
                media_data.delete(ats[k][1]);
            }
        }
    }

    return $.Deferred().resolve();
}

function set_media_by_slide() {
    media_by_slide = media_list.slice(cur_filmstrip_first, cur_filmstrip_last+1);
}

function setup_slide(slide, data) {
            var idx = media_list.indexOf(data.id);
            var sl = $("#slide_"+slide);
            var tn = $("div.thumbnail-image", sl);

            $(sl).data("media", data.id);
            $(sl).data("media_idx", idx);
            $(tn).css("background-image", "url("+data["tn"].src+")");
            $(tn).on("click vclick", {media: data}, function(ev) {
                set_preview_image(ev.data.media);
            });

            $(".filename", sl).text(data.filename);
            $(".date", sl).text(display_timestamp(data.date));
            data.slide = slide;
            update_metadata_filmstrip(data);
            $(sl).show();

            data.pv = new Image();
            data.pv.src = data.preview;
}

function reload_filmstrip(refresh_preview) {
    var first = verify_index(cur_filmstrip_first-filmstrip_prefetch);
    var last = verify_index(cur_filmstrip_last+filmstrip_prefetch);
    var ids = media_list.slice(first, last+1);
    set_media_by_slide();

    get_media_data(ids, function gmd_reload(id, data) {
        var slide = media_by_slide.indexOf(id)+1;
        if (slide) {
            setup_slide(slide, data);
            if (refresh_preview && media_list.indexOf(id) == cur_catalog_idx)
                set_preview_image(data);
        }
    });
}

function setup_filmstrip() {
    // console.log("catalog_idx, media =",cur_catalog_idx, media_list[cur_catalog_idx]);
    if (cur_catalog_idx > media_list.length-6) {
        cur_filmstrip_last = verify_index(cur_catalog_idx+6);
        cur_filmstrip_first = verify_index(cur_filmstrip_last-5);
    } else {
        cur_filmstrip_first = verify_index(cur_catalog_idx-2);
        cur_filmstrip_last = verify_index(cur_filmstrip_first+5);
    }

    reload_filmstrip(true);
}

/* ===== helper functions for filmstrip ===== */

function rating_stars_filmstrip(sl, rating) {
    var stars=$(".starrating > span > .glyphicon", sl);
    for (r=0; r < 5; r++) {
        // $(stars[r]).removeClass("glyphicon-star-empty");
        if (r < rating) {
            $(stars[r]).addClass("glyphicon-star");
        } else {
            $(stars[r]).removeClass("glyphicon-star");
        }
    }
}

function show_reject_filmstrip(sl, rejected) {
    if (rejected) {
        $(".reject-flag", sl).show();
        $(".thumbnail", sl).addClass("tn-rejected");
    } else {
        $(".reject-flag", sl).hide();
        $(".thumbnail", sl).removeClass("tn-rejected");
    }
}

function show_label_filmstrip(sl, label) {
    if (!label || label == "None") {
        $(".media-label-flag", sl).hide();
    } else {
        $(".media-label-flag", sl).show();
        $(".media-label-flag > .glyphicon-flag", sl).css("color", label);
    }
}

function show_catalog_filmstrip(sl, catalog) {
    $("#media-catalog > span.media-catalog-title").text(catalog);
    if (catalog == this_catalog)
        $(".export-flag", sl).hide();
    else
        $(".export-flag", sl).show();
}

function show_current_media(sl) {
    if ($(sl).data("media_idx") == cur_catalog_idx)
        $(sl).css('border-color', 'black');
    else
        $(sl).css('border-color', 'white');
}

function update_metadata_filmstrip(data) {
    var sl=$("#slide_"+data.slide);
    rating_stars_filmstrip(sl, data.rating);
    show_reject_filmstrip(sl, data.rejected);
    show_label_filmstrip(sl, data.label);
    show_catalog_filmstrip(sl, data.catalog);
    show_current_media(sl);
}

function set_filmstrip_slide() {
    for (var idx = 1; idx <= 6; idx++) {
        var sl = $("#slide_"+idx);
        show_current_media(sl);
    }
}

/* ===== update preview and filmstrip ===== */

function set_rating() {
    var rating=$(this).data("rating");
    var stars="#"+$(this).parent().attr("id");

    get_media_data_from_cache(media_list[cur_catalog_idx], function gmd_rating(id, media) {
        if (media.rating == rating)
            rating--;
        if (rating < 0)
            rating=1;
        rating_stars_main(stars, rating);
        media.rating = rating;
        set_image_metadata({rating: rating});
    });
}

function toggle_reject() {
    get_media_data_from_cache(media_list[cur_catalog_idx], function gmd_reject(id, media) {
        var new_state = !media.rejected
        media.rejected = new_state;
        show_reject_main(new_state);
        set_image_metadata({rejected: new_state});
    });
}

function set_label() {
    var label=$(this).data("label");
    show_label_main(label);
    set_image_metadata({label: label});
}

function set_catalog() {
    var catalog = sanitize_catalog($(this).text());
    set_image_metadata({catalog: catalog});
}

function add_catalog(ev) {
    var catalog = sanitize_catalog($(this).val());
    $(this).val("");
    $("#media-catalog").click();
    set_image_metadata({catalog: catalog});
}

function update_image_metadata(data) {
    update_metadata_main(data);
    update_metadata_filmstrip(data);
    $.mobile.loading("hide");
}

/* ===== get or set image data ===== */

function set_image_metadata(values) {
    var cur_id = media_list[cur_catalog_idx];
    get_media_data_from_server(JSON.stringify({
        "ids": [cur_id],
        "set": values,
    }), function(id, media) {
        var slide = 0;
        for (var sl=1; sl <= 6; sl++) {
            if ($("#slide_"+sl).data("media") == id)
                slide = sl;
        }
        media.slide = slide;

        if (id == cur_id)
            update_image_metadata(media);
        else
            update_metadata_filmstrip(media)
    });
}

/* ===== navigation ===== */

function previous_image() {
    var idx = verify_index(cur_catalog_idx-1);
    if (idx == cur_catalog_idx)
        return;

    cur_catalog_idx = idx;
    if (cur_catalog_idx == cur_filmstrip_first-1)
        slide_strip_right();
    if (cur_catalog_idx < cur_filmstrip_first || cur_catalog_idx > cur_filmstrip_last)
        setup_filmstrip();

    get_media_data(media_list[cur_catalog_idx], function gmd_scroll(id, media) {
        set_preview_image(media);
    });
}

function next_image() {
    var idx = verify_index(cur_catalog_idx+1);
    if (idx == cur_catalog_idx)
        return;

    cur_catalog_idx = idx;
    if (cur_catalog_idx == cur_filmstrip_last+1)
        slide_strip_left();
    if (cur_catalog_idx < cur_filmstrip_first || cur_catalog_idx > cur_filmstrip_last)
        setup_filmstrip();

    get_media_data(media_list[cur_catalog_idx], function gmd_scroll(id, media) {
        set_preview_image(media);
    });
}

function first_image() {
    cur_catalog_idx = verify_index(0);
    setup_filmstrip();
}

function last_image() {
    cur_catalog_idx = verify_index(media_list.length-1);
    setup_filmstrip();
}

function slide_strip_left() {
    if (cur_filmstrip_last+1 == media_list.length)
        return;

    var remove = cur_filmstrip_first-filmstrip_prefetch;
    if (remove >= 0) {
        var m = media_data.get(media_list[remove]);
        if (m) {
            m.slide = 0;
            m.pv = undefined;
        }
    }

    cur_filmstrip_last++;
    cur_filmstrip_first++;

    var last_idx = verify_index(cur_filmstrip_last+filmstrip_prefetch);
    var ids = media_list.slice(cur_filmstrip_first, last_idx+1);
    set_media_by_slide();

    get_media_data(ids, function gmd_slide(id, data) {
        var slide = media_by_slide.indexOf(id)+1;
        if (slide)
            setup_slide(slide, data);
    });
}

function slide_strip_right() {
    if (cur_filmstrip_first == 0)
        return;

    var remove = cur_filmstrip_last+filmstrip_prefetch;
    if (remove < media_list.length) {
        var m = media_data.get(media_list[remove]);
        if (m) {
            m.slide = 0;
            m.pv = undefined;
        }
    }

    cur_filmstrip_first--;
    cur_filmstrip_last--;

    var first_idx = verify_index(cur_filmstrip_first-filmstrip_prefetch);
    var ids = media_list.slice(first_idx, cur_filmstrip_last+1);
    set_media_by_slide();

    get_media_data(ids, function gmd_slide(id, data) {
        var slide = media_by_slide.indexOf(id)+1;
        if (slide)
            setup_slide(slide, data);
    });
}

var slide_scroll_mouse_pos;
function slide_scroll(ev) {
    ev.preventDefault();
    ev.stopPropagation();

    var delta = ev.pageX - slide_scroll_mouse_pos;
    if (Math.abs(delta) < 40) return;

    if (delta > 0)
        slide_strip_right();
    else
        slide_strip_left();

    slide_scroll_mouse_pos = ev.pageX;
}

function slide_start_scroll(ev) {
    slide_scroll_mouse_pos = ev.pageX;
    $(this).on("mousemove vmousemove", slide_scroll);
    ev.preventDefault();
    ev.stopPropagation();
}

function slide_stop_scroll(ev) {
    $(this).off("mousemove");
    $(this).off("vmousemove");
}



/* ===== bulk operations ===== */

var bulk_operation_data = { };

function bulk_get_dropdown_value(node, selector) {
    var this_class=$("span", node).attr("class");
    var this_style=$("span", node).attr("style");
    var this_text=$(node).text();

    $(selector+"-selected-icon").attr("class", this_class).removeAttr("style").attr("style", this_style).show();
    $(selector+"-selected").text(this_text);
    return this_text.replace(/(^\s*)|(\s*$)|[\r\n]/g, "");
}

function bulk_action_value_hide() {
    $(".bulk-action-rating").hide();
    $(".bulk-action-label").hide();
    $(".bulk-action-catalog").hide();
    $("#bulk-submit").prop("disabled", true);
    $("#bulk-cancel").prop("disabled", false);
}

function bulk_action_attribute_hide() {
    $("#bulk-action-attribute").prop("disabled", true);
    $("#bulk-action-attribute-selected-icon").hide();
    $("#bulk-action-attribute-selected").text("Action");
    bulk_action_value_hide();
}

function bulk_condition_value_hide() {
    $(".bulk-condition-rating").hide();
    $(".bulk-condition-label").hide();
    $(".bulk-condition-catalog").hide();
    bulk_action_attribute_hide();
}

function bulk_condition_operator_hide() {
    $(".bulk-condition-operator-rating").hide();
    $(".bulk-condition-operator-equal").hide();
    $(".bulk-condition-operator-range").hide();
    $(".bulk-condition-date").hide();
    bulk_condition_value_hide();
}

function bulk_modal_open() {
    bulk_condition_operator_hide();
    $("#bulk-condition-attribute-selected-icon").hide();
    $("#bulk-condition-attribute-selected").text("Select");
    $("#bulk-action-modal").modal('show');
}

function bulk_condition_set_attribute() {
    bulk_condition_operator_hide();

    var flags = {"All": "all", "Rejected": "reject", "Published": "publish"};
    bulk_operation_data.select = {};
    bulk_operation_data.set = {};

    var attribute = bulk_get_dropdown_value(this, "#bulk-condition-attribute");

    if (attribute in flags) {
        bulk_operation_data.select.item = flags[attribute];
        $("#bulk-action-attribute").prop("disabled", false);
    } else
    if (attribute == "Rating") {
        bulk_operation_data.select.item = "rating";
        bulk_operation_data.select.operator="eq";
        $("#bulk-condition-operator-rating-selected").text(" = ");
        $("#bulk-condition-operator-rating-selected").data("operator", bulk_operation_data.select.operator);
        $(".bulk-condition-operator-rating").show();
        $("#bulk-condition-rating-selected").html("Rating");
        $("#bulk-condition-rating").prop("disabled", false);
        $(".bulk-condition-rating").show();
    } else
    if (attribute == "Label") {
        bulk_operation_data.select.item = "label";
        bulk_operation_data.select.operator="eq";
        $("#bulk-condition-operator-equal-selected").text(" is ");
        $("#bulk-condition-operator-equal-selected").data("operator", bulk_operation_data.select.operator);
        $(".bulk-condition-operator-equal").show();
        $("#bulk-condition-label-selected-icon").hide();
        $("#bulk-condition-label-selected").text("Label");
        $("#bulk-condition-label").prop("disabled", false);
        $(".bulk-condition-label").show();
    } else
    if (attribute == "Catalog") {
        bulk_operation_data.select.item = "catalog";
        bulk_operation_data.select.operator="eq";
        $("#bulk-condition-operator-equal-selected").text(" is ");
        $("#bulk-condition-operator-equal-selected").data("operator", bulk_operation_data.select.operator);
        $(".bulk-condition-operator-equal").show();
        $("#bulk-condition-catalog-selected").text(this_catalog);
        $("#bulk-condition-catalog").prop("disabled", false);
        $("#bulk-action-attribute").prop("disabled", false);
        $(".bulk-condition-catalog").show();
    } else
    if (attribute == "Timestamp") {
        bulk_operation_data.select.item = "date";
        bulk_operation_data.select.operator="eq";
        $("#bulk-condition-operator-range-selected").text(" between ");
        $("#bulk-condition-operator-range-selected").data("operator", bulk_operation_data.select.operator);
        $(".bulk-condition-operator-range").show();
        $(".bulk-condition-date").show();
        bulk_operation_data.select.value = {};
        bulk_condition_set_start_date();
        bulk_condition_set_end_date();
        $("#bulk-action-attribute").prop("disabled", false);
    }
}

function bulk_condition_set_operator_rating() {
    bulk_get_dropdown_value(this, "#bulk-condition-operator-rating");
    $("#bulk-condition-rating").prop("disabled", false);
    bulk_operation_data.select.operator=$(this).data("operator");
}

function bulk_condition_set_operator_equal() {
    bulk_get_dropdown_value(this, "#bulk-condition-operator-equal");
    $(".bulk-condition-equal").show();
    if (bulk_operation_data.select.item == "label") {
        $("#bulk-condition-label").prop("disabled", false);
    } else {
        bulk_operation_data.select.value=$("#bulk-condition-catalog-selected").text();
        $("#bulk-condition-catalog").prop("disabled", false);
        $("#bulk-action-attribute").prop("disabled", false);
    }

    bulk_operation_data.select.operator=$(this).data("operator");
}

function bulk_condition_set_operator_range() {
    bulk_get_dropdown_value(this, "#bulk-condition-operator-range");
    $("#bulk-condition-range").prop("disabled", false);
    bulk_operation_data.select.operator=$(this).data("operator");
}

function bulk_condition_set_rating() {
    var rating=$(this).data("rating");
    $("#bulk-condition-rating-selected").html($(this).html());
    bulk_operation_data.select.value = rating;
    $("#bulk-action-attribute").prop("disabled", false);
}

function bulk_condition_set_label() {
    bulk_get_dropdown_value(this, "#bulk-condition-label");
    bulk_operation_data.select.value = $(this).data("label");
    $("#bulk-action-attribute").prop("disabled", false);
}

function bulk_condition_set_catalog() {
    var catalog=$(this).text()
    $(".bulk-condition-catalog-title").text(catalog);
    bulk_operation_data.select.value = catalog;
    $("#bulk-action-attribute").prop("disabled", false);
}

function bulk_condition_set_start_date() {
    bulk_operation_data.select.value.start=$("#bulk-condition-date-start").data("DateTimePicker").date().format("YYYY-MM-DD HH:mm");
}

function bulk_condition_set_end_date() {
    bulk_operation_data.select.value.end=$("#bulk-condition-date-end").data("DateTimePicker").date().format("YYYY-MM-DD HH:mm");
}

function bulk_action_set_attribute() {
    bulk_action_value_hide();
    bulk_operation_data.set = {}
    var attribute = bulk_get_dropdown_value(this, "#bulk-action-attribute");

    var flags = {"Reject": "reject", "Publish": "publish"};
    if (attribute in flags) {
        $("#bulk-submit").prop("disabled", false);
        bulk_operation_data.set.item = flags[attribute];
    } else
    if (attribute == "Set rating") {
        bulk_operation_data.set.item = "rating";
        $("#bulk-action-rating-selected").html("Rating");
        $(".bulk-action-rating").show();
    } else
    if (attribute == "Set label") {
        bulk_operation_data.set.item = "label";
        $("#bulk-action-label-selected-icon").hide();
        $("#bulk-action-label-selected").text("Label");
        $(".bulk-action-label").show();
    } else
    if (attribute == "Move to catalog") {
        $("#bulk-submit").prop("disabled", false);
        bulk_operation_data.set.item = "catalog";
        bulk_operation_data.set.value = this_catalog;
        $("#bulk-action-catalog-selected").text(bulk_operation_data.set.value);
        $(".bulk-action-catalog").show();
    }
}

function bulk_action_set_rating() {
    var rating=$(this).data("rating");
    $("#bulk-action-rating-selected").html($(this).html());
    bulk_operation_data.set.value = rating;
    $("#bulk-submit").prop("disabled", false);
}

function bulk_action_set_label() {
    var label = bulk_get_dropdown_value(this, "#bulk-action-label");
    bulk_operation_data.set.value = label;
    $("#bulk-submit").prop("disabled", false);
}

function bulk_action_set_catalog() {
    var catalog=$(this).text();
    bulk_operation_data.set.value = catalog;
    $(".bulk-action-catalog-title").text(catalog);
    $("#bulk-submit").prop("disabled", false);
}

function bulk_action_add_catalog() {
    var catalog = sanitize_catalog($(this).val());
    $(this).val("");
    amend_catalog_dropdown(catalog, "bulk-action-catalog", bulk_action_set_catalog)
    amend_catalog_dropdown(catalog, "bulk-condition-catalog", bulk_condition_set_catalog)
    amend_catalog_dropdown(catalog, "media-catalog", set_catalog)
    $(".bulk-action-catalog > ul > .bulk-action-catalog-item :last").click();
}

function bulk_submit() {
    $.mobile.loading("show");
    bulk_operation_data.ids = media_list;

    $.ajax({
        url: urls.bulk,
        type: "POST",
        data: $.param({"csrfmiddlewaretoken":  csrftoken,  "json": JSON.stringify(bulk_operation_data)}),
        dataType: "json",
        success: function(json) {
            if (json.length < 1) {
                $.mobile.loading("hide");
                return;
            }

            for (idx=0; idx < json.length; idx++) {
                // console.log("modified, removing:", json[idx]);
                media_data.delete(json[idx]);
            }

            var preview_in_filmstrip = (cur_catalog_idx >= cur_filmstrip_first) && (cur_catalog_idx <= cur_filmstrip_last);

            if (preview_in_filmstrip) {
                reload_filmstrip(true);
            } else {
                get_media_data(media_list[cur_catalog_idx], function gmd_bulk(id, data) {
                    set_preview_image(data);
                });

                reload_filmstrip(false);
            }
            $.mobile.loading("hide");
        },
        error: function(xhr, status, errorThrown) {
            console.log("Error: "+errorThrown);
            console.log("Status: "+status);
            console.dir( xhr);
            $.mobile.loading("hide");
        }
    });
    $("#bulk-action-modal").modal('hide');
}

/* ===== fullsize image viewer ==== */

function view_fullsize() {
        var page_width = $(".page-lighttable").get(0).clientWidth;
        var page_height = $(".page-lighttable").get(0).clientHeight;
        var window_width = $(window).width();
        var window_height = $(window).height();
        var img = $(".image-fullsize");

        if (page_width > window_width)
            page_width = window_width;
        if (page_height > window_height)
            page_height = window_height;

        var dims = {
            width: page_width,
            height: page_height,
            transform: "",
            "transform-origin": "",
        };

        $(".page-lighttable").hide();
        $(".page-image").css(dims);
        $(img).css(dims);

        $(".page-image").show();

        var img_width = $("#image-fullsize").get(0).naturalWidth;
        var img_height = $("#image-fullsize").get(0).naturalHeight;

        var scale_factor_w = page_width / img_width;
        var scale_factor_h = page_height / img_height;
        var scale_factor;

        if (scale_factor_h < scale_factor_w)
            scale_factor = scale_factor_h;
        else
            scale_factor = scale_factor_w;

        $(img).panzoom("destroy");

        $(img).panzoom({
            minScale: 0.05,
            maxScale: 1,
            disableZoom: false, // ARGLBARGLGNAH
            disablePan: false,
            focal: {clientX: 0, clientY: 0},
        });

        $(img).panzoom("zoom", scale_factor, {focal: {clientX: 0, clientY: 0}});

        $("#image-fullsize").on("mousewheel", function(ev) {
            console.log("wheel");
            ev.preventDefault();
            var delta = ev.delta || ev.originalEvent.wheelDelta;
            var zoom_out = delta? delta < 0: ev.originalEvent.deltaY > 0;
            $(img).panzoom("zoom", zoom_out, {
                increment: 0.05,
                animate: false,
                focal: ev,
            });
        });

}

/* ===== initializing ==== */

function lighttable_setup(args) {
    if (args.catalog == undefined) {
        console.log("lighttable_setup: catalog missing");
        return;
    }
    this_catalog = args.catalog;

    if (args.media_list == undefined) {
        console.log("lighttable_setup: media_list missing");
        return;
    }
    media_list = args.media_list;

    if (args.urls == undefined) {
        console.log("lighttable_setup: urls missing")
        return;
    }
    urls = args.urls;

    if (args.start_date != undefined)
        first_date = args.start_date;
    if (args.end_date != undefined)
        last_date = args.end_date;
    if (args.may_edit != undefined)
        may_edit = args.may_edit
    if (args.may_move != undefined)
        may_move = args.may_move;
    if (args.cache_size != undefined)
        cache_size = args.cache_size;
    if (args.prefetch != undefined)
        filmstrip_prefetch = args.prefetch;

    csrftoken= $("input[name='csrfmiddlewaretoken']").attr("value");

    var media_id = window.location.hash.substring(1);
    if (media_id == undefined || media_id == "")
        cur_catalog_idx = 0;
    else
        cur_catalog_idx = media_list.indexOf(media_id*1);

    $.mobile.loading("show");

    // set_preview_image();
    setup_filmstrip();
    $(".image-center-overlay").on("dragstart", function() { return false; });

    $("#media-prev").on("taphold", first_image);
    $("#media-next").on("taphold", last_image);

    $("#media-prev").on("click", previous_image);
    $("div.preview").on("swiperight", previous_image);
    $("#media-next").on("click", next_image);
    $("div.preview").on("swipeleft", next_image);

    $("div.image-preview-container").on("click", view_fullsize);

    $("div.image-fullsize-close").on("click", function() {
        $(".page-image").hide();
        $(".page-lighttable").show();
    });

    $("div.filmstrip").on("mousedown vmousedown", slide_start_scroll);
    $("div.filmstrip").on("mouseup mouseleave vmouseup", slide_stop_scroll);

    if (may_edit) {
        $("#media-reject").prop("disabled", false);
        $("#media-label").prop("disabled", false);

        $("#media-rating > span").on("click", set_rating);
        $("#media-reject").on("click", toggle_reject);
        $(".media-label-link").on("click", set_label);
    } else {
        $("#media-reject").prop("disabled", true);
        $("#media-label").prop("disabled", true);
        $(".bulk-action-edit").addClass("disabled", true);
    }

    if (may_move) {
        $("#media-bulk").prop("disabled", false);
        $("#media-catalog").prop("disabled", false);
        $(".media-catalog-input,.bulk-action-catalog-input").on("click", function(ev) {
            ev.stopPropagation();
        });

        $(".media-catalog-link").on("click", set_catalog);
        $(".media-catalog-input").on("change", add_catalog);
    } else {
        $("#media-catalog").prop("disabled", true);
        $(".bulk-action-move").addClass("disabled");
    }

    $("#media-bulk").prop("disabled", !(may_edit || may_move));

    $.fn.modal.Constructor.prototype.enforceFocus = function() {};
    $("#media-bulk").on("click", bulk_modal_open);
    $(".bulk-condition-attribute-link").on("click", bulk_condition_set_attribute);
    $(".bulk-condition-operator-rating-link").on("click", bulk_condition_set_operator_rating);
    $(".bulk-condition-operator-equal-link").on("click", bulk_condition_set_operator_equal);
    $(".bulk-condition-operator-range-link").on("click", bulk_condition_set_operator_range);
    $(".bulk-condition-rating-link").on("click", bulk_condition_set_rating);
    $(".bulk-condition-label-link").on("click", bulk_condition_set_label);
    $(".bulk-condition-catalog-link").on("click", bulk_condition_set_catalog);

    $(".bulk-action-attribute-link").on("click", bulk_action_set_attribute);
    $(".bulk-action-rating-link").on("click", bulk_action_set_rating);
    $(".bulk-action-label-link").on("click", bulk_action_set_label);
    $(".bulk-action-catalog-link").on("click", bulk_action_set_catalog);
    $(".bulk-action-catalog-input").on("change", bulk_action_add_catalog);

    $("#bulk-submit").on("click", bulk_submit);

    $("#bulk-condition-date-start").datetimepicker({
        format: "YYYY-MM-DD HH:mm",
        minDate: first_date,
        maxDate: last_date,
        defaultDate: first_date
    });
    $("#bulk-condition-date-start").on("dp.change", bulk_condition_set_start_date);

    $("#bulk-condition-date-end").datetimepicker({
        format: "YYYY-MM-DD HH:mm",
        minDate: first_date,
        maxDate: last_date,
        defaultDate: last_date
    });
    $("#bulk-condition-date-end").on("dp.change", bulk_condition_set_end_date);
}
