define(['app_data/app', 'marionette',
        'tpl!app_data/menu/templates/nav_list.tpl',
        'tpl!app_data/menu/templates/nav_list_item.tpl',
        'bootstrap'],
       function(App, Marionette, navListTpl, navListItemTpl){

    var views = {};

    views.NavListItem = Backbone.Marionette.ItemView.extend({
        template    : navListItemTpl,
        tagName     : 'li',
        className   : 'dropdown',
    });

    views.NavList = Backbone.Marionette.CompositeView.extend({
        template            : navListTpl,
        childView           : views.NavListItem,
        childViewContainer  : 'ul#menu-items',
        templateHelpers: function(){ return {user: App.currentUser}; },
    });

    return views;
});
