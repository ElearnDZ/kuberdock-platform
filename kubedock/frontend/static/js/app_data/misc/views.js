define(['app_data/app', 'marionette',
        'tpl!app_data/misc/templates/message_list.tpl',
        'tpl!app_data/misc/templates/message_list_item.tpl',
        'tpl!app_data/misc/templates/page_layout.tpl',
        'tpl!app_data/misc/templates/page_not_found.tpl'],
       function(App, Marionette,
                messageListTpl, messageListItemTpl,
                pageLayoutTpl, pageNotFoundTpl){

    var views = {};

    views.MessageListItem = Marionette.ItemView.extend({
        template: messageListItemTpl,
        className: function(){
            return this.model.get('type') || 'info';
        }
    });

    views.MessageList = Marionette.CompositeView.extend({
        template: messageListTpl,
        childView: views.MessageListItem,
        childViewContainer: '#message-body',
        className: 'message-box',

        ui: {
            'toggler': '.toggler',
            'messageBody': '#message-body'
        },

        events: {
            'click @ui.toggler': 'toggleBody'
        },

        toggleBody: function(evt){
            evt.stopPropagation();
            if (this.ui.messageBody.hasClass('visible')) {
                this.ui.messageBody.show();
            } else {
                this.ui.messageBody.hide();
            }
            this.ui.toggler.toggleClass('move');
            this.ui.messageBody.toggleClass('visible');
            this.ui.messageBody.parent().toggleClass('visible');
        }
    });
    
    views.PageLayout = Marionette.LayoutView.extend({
        template: pageLayoutTpl,
        regions: {
            nav: '#nav',
            main: '#main'
        }
    });
    
    views.PageNotFound = Marionette.ItemView.extend({
        template: pageNotFoundTpl
    });
    
    return views;
});