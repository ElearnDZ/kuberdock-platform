define(['app_data/app', 'app_data/controller', 'marionette', 'app_data/utils',
        'tpl!app_data/pstorage/templates/pv_list.tpl',
        'tpl!app_data/pstorage/templates/pv_list_empty.tpl',
        'tpl!app_data/pstorage/templates/pv_list_item.tpl',
        'tpl!app_data/pstorage/templates/pv_layout.tpl',
        'bootstrap', 'jquery-ui', 'selectpicker',
        'bootstrap3-typeahead', 'mask', 'tooltip'],
       function(App, Controller, Marionette, utils,
                pvListTpl,
                pvListEmptyTpl,
                pvListItemTpl,
                pvLayoutTpl){

    var views = {};

    views.PersistentVolumesEmptyView = Marionette.ItemView.extend({
        template: pvListEmptyTpl,
        tagName: 'tr',
    });

    views.PersistentVolumesItemView = Marionette.ItemView.extend({
        template: pvListItemTpl,
        tagName: 'tr',

        ui: {
            terminate: 'span.terminate-btn',
            tooltip  : '[data-toggle="tooltip"]',
        },

        events: {
            'click @ui.terminate': 'terminateVolume'
        },

        templateHelpers: function(){
            var linkedPods = this.model.get('linkedPods'),
                forbidDeletionMsg;
            if (!this.model.get('forbidDeletion')){
                forbidDeletionMsg = null;
            } else if (this.model.get('in_use')){
                forbidDeletionMsg = 'Volume cannot be deleted, because it\'s used by pod "'
                + this.model.get('pod_name') + '"';
            } else if (linkedPods){
                forbidDeletionMsg = 'Volume cannot be deleted, because it\'s linked to '
                    + (linkedPods.length == 1
                        ? 'pod "' + linkedPods[0].name + '"'
                        : 'pods: "' + _.pluck(linkedPods, 'name').join('", "') + '"');
            }
            return {
                forbidDeletionMsg: forbidDeletionMsg,
            };
        },

        onDomRefresh: function(){ this.ui.tooltip.tooltip(); },

        terminateVolume: function(){
            var that = this;

            if (!this.model.get('forbidDeletion')) {
                utils.modalDialogDelete({
                    title: "Delete persistent volume?",
                    body: "Are you sure you want to delete this persistent volume?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            utils.preloader.show();
                            that.model.destroy({wait: true})
                                .always(utils.preloader.hide)
                                .fail(utils.notifyWindow)
                                .done(function(){ that.remove(); });
                        },
                        buttonCancel: true
                    }
                });
            }
        }
    });

    views.PersistentVolumesView = Marionette.CompositeView.extend({
        template           : pvListTpl,
        childView          : views.PersistentVolumesItemView,
        emptyView          : views.PersistentVolumesEmptyView,
        childViewContainer : 'tbody',

        ui: {
            'th' : 'table th'
        },

        events: {
            'click @ui.th' : 'toggleSort'
        },

        initialize: function(options){
            this.collection.order = options.order || [
                {key: 'name', order: 1},
                {key: 'size', order: 1},
                {key: 'in_use', order: 1},
            ];
            this.collection.fullCollection.sort();
            this.collection.on('change', function(){ this.fullCollection.sort(); });
        },

        templateHelpers: function(){
            return {
                sortingType : this.collection.orderAsDict()
            }
        },

        onShow: function(){
            utils.preloader.hide();
        },

        toggleSort: function(e) {
            var targetClass = e.target.className;
            if (!targetClass) return;
            this.collection.toggleSort(targetClass);
            this.render();
        }
    });


    views.PersistentVolumesLayout = Marionette.LayoutView.extend({
        template: pvLayoutTpl,
        regions: {
            nav : 'div#nav',
            main: 'div#details_content',
            pager: 'div#pager'
        },

        initialize: function(){
            var that = this;
            this.listenTo(this.main, 'show', function(view){
                that.listenTo(view, 'pager:clear', that.clearPager);
            });
        },

        onBeforeShow: function(){
            utils.preloader.show();
        },

        clearPager: function(){
            this.trigger('pager:clear');
        }
    });

    return views;
});
