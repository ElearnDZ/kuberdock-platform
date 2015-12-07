define(['app_data/app', 'app_data/controller', 'marionette', 'utils',
        'tpl!app_data/public_ips/templates/public_ips_list.tpl',
        'tpl!app_data/public_ips/templates/public_ips_empty.tpl',
        'tpl!app_data/public_ips/templates/public_ips_item.tpl',
        'tpl!app_data/public_ips/templates/public_ips_layout.tpl',
        'bootstrap', 'jquery-ui', 'selectpicker', 'bootstrap3-typeahead', 'mask'],
       function(App, Controller, Marionette, utils,
                publicIPsListTpl,
                publicIPsEmptyTpl,
                publicIPsItemTpl,
                publicIPsLayoutTpl){

    var views = {};

    views.PublicIPsItemView = Marionette.ItemView.extend({
        template: publicIPsItemTpl,
        tagName: 'tr'
    });

    views.PublicIPsEmptyView = Marionette.ItemView.extend({
        template: publicIPsEmptyTpl,
        tagName: 'tr'
    });

    views.PublicIPsView = Marionette.CompositeView.extend({
        template            : publicIPsListTpl,
        childView           : views.PublicIPsItemView,
        emptyView           : views.PublicIPsEmptyView,
        childViewContainer  : 'tbody',
    });

    views.SettingsLayout = Marionette.LayoutView.extend({
        template: publicIPsLayoutTpl,
        regions: {
            nav: 'div#nav',
            main: 'div#details_content'
        },
    });
    return views;
});
