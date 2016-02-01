define(['app_data/app',
        'tpl!app_data/pods/templates/layout_pod_list.tpl',
        'tpl!app_data/pods/templates/pod_list_item.tpl',
        'tpl!app_data/pods/templates/pod_list_empty.tpl',
        'tpl!app_data/pods/templates/pod_list.tpl',
        'app_data/utils',
        'bootstrap'],
       function(App, layoutPodListTpl, podListItemTpl, podListEmptyTpl, podListTpl, utils){

    var podList = {};

    podList.PodListLayout = Backbone.Marionette.LayoutView.extend({
        template: layoutPodListTpl,

        regions: {
            nav: '#layout-nav',
            header: '#layout-header',
            list: '#layout-list',
            pager: '#layout-footer'
        },

        initialize: function(){
            var that = this;
            this.listenTo(this.list, 'show', function(view){
                that.listenTo(view, 'pager:clear', that.clearPager);

            });
            this.listenTo(this.header, 'show', function(view){
                that.listenTo(view, 'collection:filter', that.collectionFilter);
            });
        },

        onBeforeShow: function(){
            utils.preloader.show();
        },

        onShow: function(){
            utils.preloader.hide();
        },

        clearPager: function(){
            this.trigger('pager:clear');
        },

        collectionFilter: function(data){
            this.trigger('collection:filter', data);
        }
    });

    podList.PodListEmpty = Backbone.Marionette.ItemView.extend({
        template : podListEmptyTpl,
        tagName  : 'tr',
    });

    // View for showing a single pod item as a container in pods list
    podList.PodListItem = Backbone.Marionette.ItemView.extend({
        template    : podListItemTpl,
        tagName     : 'tr',
        className   : function(){
            return this.model.is_checked ? 'pod-item checked' : 'pod-item';
        },

        initialize: function(options){
            this.index = options.childIndex;
        },

        templateHelpers: function(){
            return {
                kubes: this.model.getKubes(),
                checked: !!this.model.is_checked,
            };
        },

        ui: {
            start      : '.start-btn',
            stop       : '.stop-btn',
            remove     : '.terminate-btn',
            checkbox   : 'label.custom span',
            podPageBtn : '.poditem-page-btn'
        },

        events: {
            'click @ui.start'      : 'startItem',
            'click @ui.stop'       : 'stopItem',
            'click @ui.remove'     : 'deleteItem',
            'click @ui.podPageBtn' : 'podPage',
            'click @ui.checkbox'   : 'toggleItem'
        },

        modelEvents: {
            'change': 'render'
        },

        podPage: function(evt){
            evt.stopPropagation();
            App.navigate('pods/' + this.model.id, {trigger: true});
        },

        startItem: function(evt){
            evt.stopPropagation();
            App.commandPod('start', this.model).always(this.render);
        },

        deleteItem: function(evt){
            evt.stopPropagation();
            var that = this;
            utils.modalDialogDelete({
                title: "Delete",
                body: 'Are you sure you want to delete "' + that.model.get('name') + '" pod?',
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        that.model.destroy();
                    },
                    buttonCancel: true
               }
           });
        },

        stopItem: function(evt){
            evt.stopPropagation();
            App.commandPod('stop', this.model).always(this.render);
        },

        toggleItem: function(evt){
            var tgt = $(evt.target);
            evt.stopPropagation();
            tgt.prop('checked', !tgt.prop('checked'));
            this.trigger('item:clicked');
        }
    });

    podList.PodCollection = Backbone.Marionette.CompositeView.extend({
        template            : podListTpl,
        childView           : podList.PodListItem,
        tagName             : 'div',
        className           : 'container',
        emptyView           : podList.PodListEmpty,
        childViewContainer  : 'tbody',

        ui: {
            'runPods'       : '.runPods',
            'stopPods'      : '.stopPods',
            'removePods'    : '.removePods',
            'toggleCheck'   : 'thead label.custom span',
            'th'            : 'table th'
        },

        events: {
            'click @ui.runPods'    : 'runPods',
            'click @ui.stopPods'   : 'stopPods',
            'click @ui.toggleCheck': 'toggleCheck',
            'click @ui.removePods' : 'removePods',
            'click @ui.th'         : 'toggleSort'
        },

        templateHelpers: function(){
            return {
                allChecked: this.collection.fullCollection.allChecked ? true : false,
                checked: this.collection.fullCollection.checkedNumber,
                isCollection : this.collection.fullCollection.length < 1 ? 'disabled' : '',
                sortingType : this.sortingType
            }
        },

        initialize: function(){
            if (!this.collection.fullCollection.hasOwnProperty('checkedNumber')) {
                this.collection.fullCollection.checkedNumber = 0;
            }
            this.counter = 1;
            this.sortingType = {
                name : 1,
                replicas : 1,
                status : 1,
                kube_type : 1
            };
        },

        toggleSort: function(e) {
            var that = this,
                targetClass = e.target.className;

            if (targetClass) {
                this.collection.setSorting(targetClass, this.counter);
                this.collection.fullCollection.sort();
                this.counter = this.counter * (-1);

                if (that.sortingType[targetClass] == 1){
                    _.each(that.sortingType, function(item, index){
                        that.sortingType[index] = 1;
                    })
                    that.sortingType[targetClass] = -1;
                } else {
                    that.sortingType[targetClass] = 1;
                }
                this.render();
            }
        },

        toggleCheck: function(evt){
            var tgt = evt.target;
            evt.stopPropagation();
            if (this.collection.fullCollection.length > 0){
                if (this.collection.fullCollection.allChecked){
                    this.collection.fullCollection.allChecked = false;
                    this.collection.fullCollection.checkedNumber = 0;
                    this.collection.fullCollection.each(function(m){m.is_checked = false;});
                }
                else {
                    this.collection.fullCollection.allChecked = true;
                    this.collection.fullCollection.checkedNumber = this.collection.fullCollection.length;
                    this.collection.fullCollection.each(function(m){m.is_checked = true;});
                }
            }
            this.render();
        },

        childViewOptions: function(model, index){
            return {
                childIndex: index
            };
        },

        childEvents: {
            'item:clicked': function(view){
                var model = this.collection.at(view.index);
                model.is_checked = model.is_checked
                    ? (this.collection.fullCollection.checkedNumber--, false)
                    : (this.collection.fullCollection.checkedNumber++, true);
                this.collection.fullCollection.checkedNumber == this.collection.length
                    ? this.collection.fullCollection.allChecked = true
                    : this.collection.fullCollection.allChecked = false
                this.render();
            }
        },

        removePods: function(evt){
            evt.stopPropagation();
            var body;
                that = this,
                items = that.collection.fullCollection.filter(function(i){return i.is_checked});
            if (items.length > 1){
                body = 'Are you sure you want to delete selected pods?';
            } else {
                body = 'Are you sure you want to delete "' + items[0].get('name') + '" pod?';
            }
            utils.modalDialogDelete({
                title: "Delete",
                body: body,
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        utils.preloader.show();
                        var deferreds = _.map(items, function(item) {
                            return item.destroy({wait: true})
                                .fail(utils.notifyWindow);
                        }, this);
                        $.when.apply($, deferreds).always(utils.preloader.hide);

                        that.collection.fullCollection.checkedNumber = 0;
                        that.collection.fullCollection.allChecked = false;
                        that.render();
                    },
                    buttonCancel: true
               }
           });
        },

        runPods: function(evt){
            evt.stopPropagation();
            this.sendCommand('start');
        },

        stopPods: function(evt){
            evt.stopPropagation();
            this.sendCommand('stop');
        },

        sendCommand: function(command){
            var items = this.collection.fullCollection.filter(function(i){return i.is_checked});

            utils.preloader.show();
            var deferreds = _.map(items, function(item) {
                item.is_checked = false;
                this.collection.fullCollection.checkedNumber--;
                return item.command(command).fail(utils.notifyWindow);
            }, this);
            $.when.apply($, deferreds).always(utils.preloader.hide);

            this.collection.fullCollection.allChecked = false;
            this.render();
        },

        onBeforeDestroy: function(){
            this.trigger('pager:clear');
        }
    });

    return podList;
});
