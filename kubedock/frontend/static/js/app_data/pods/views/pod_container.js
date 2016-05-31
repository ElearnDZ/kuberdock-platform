define(['app_data/app', 'app_data/model', 'app_data/utils',
        'tpl!app_data/pods/templates/layout_wizard.tpl',
        'tpl!app_data/pods/templates/pod_container_tab_general.tpl',
        'tpl!app_data/pods/templates/pod_container_tab_env.tpl',
        'tpl!app_data/pods/templates/env_table_row_empty.tpl',
        'tpl!app_data/pods/templates/env_table_row.tpl',
        'tpl!app_data/pods/templates/pod_container_tab_logs.tpl',
        'tpl!app_data/pods/templates/pod_container_tab_stats.tpl',
        'tpl!app_data/pods/templates/pod_item_graph.tpl',
        'bootstrap-editable', 'jqplot', 'jqplot-axis-renderer', 'nicescroll',
        'selectpicker', 'tooltip'],
       function(App, Model, utils,
                layoutWizardTpl,

                podContainerGeneralTabTpl,
                podContainerEnvTabTpl,
                envTableRowEmptyTpl,
                envTableRowTpl,
                podContainerLogsTabTpl,
                podContainerStatsTabTpl,
                podItemGraphTpl){

    var views = {};

    views.PodWizardLayout = Backbone.Marionette.LayoutView.extend({
        template: layoutWizardTpl,
        initialize: function(){
            var that = this;
            this.listenTo(this.steps, 'show', function(view){
                // TODO: can we remove it?
                _([
                    'step:portconf',
                    'step:envconf',
                    'step:statsconf',
                    'step:logsconf',
                ]).each(function(name){
                    that.listenTo(view, name, _.bind(that.trigger, that, name));
                });
            });
        },
        regions: {
            // TODO: 1) move menu and breadcrumbs regions into App;
            //       2) pull common parts out of "steps" into separate regions;
            nav    : '#navbar-steps',
            header : '#header-steps',
            steps  : '#steps',
        },
        onBeforeShow: utils.preloader.show,
        onShow: utils.preloader.hide,
    });

    views.WizardGeneralSubView = Backbone.Marionette.ItemView.extend({
        tagName: 'div',
        template: podContainerGeneralTabTpl,
        id: 'container-page',

        ui: {
            stopContainer  : '#stopContainer',
            startContainer : '#startContainer',
            updateContainer: '.container-update',
            checkForUpdate : '.check-for-update',
        },

        events: {
            'click @ui.stopContainer'  : 'stopContainer',
            'click @ui.startContainer' : 'startContainer',
            'click @ui.updateContainer': 'updateContainer',
            'click @ui.checkForUpdate' : 'checkContainerForUpdate',
        },

        modelEvents: {
            'change': 'render'
        },

        initialize: function(options) {
            var before = this.model.get('before');
            this.podBefore = before ? before.getPod() : this.model.get('after').getPod().editOf();
            this.podAfter = this.podBefore.get('edited_config') || this.podBefore;
            this.model.addNestedChangeListener(this, this.render);
        },

        triggers: {
            'click .go-to-envs'      : 'step:envconf',
            'click .go-to-stats'     : 'step:statsconf',
            'click .go-to-logs'      : 'step:logsconf',
        },

        templateHelpers: function(){
            var before = this.model.get('before'),
                after = this.model.get('after');
            this.podBefore.recalcInfo();
            this.podAfter.recalcInfo();
            return {
                volumes: (before || after).getPod().get('volumes'),

                // TODO: move common parts out of those views
                podID: this.podBefore.id,
                state: before ? before.get('state') : 'new',
                image: (before || after).get('image'),
                sourceUrl: (before || after).get('sourceUrl'),
                kubes: (before || after).get('kubes'),
                limits: (before || after).limits,
                updateIsAvailable: before && before.updateIsAvailable,
                kube_type: this.podBefore.getKubeType(),
                restart_policy: this.podBefore.get('restartPolicy'),
            };
        },

        startContainer: function(){ this.podBefore.cmdStart(); },
        stopContainer: function(){ this.podBefore.cmdStop(); },
        updateContainer: function(){ this.model.get('before').update(); },
        checkContainerForUpdate: function(){
            this.model.get('before').checkForUpdate().done(this.render);
        },
    });

    views.EnvTableRowEmpty = Backbone.Marionette.ItemView.extend({
        template: envTableRowEmptyTpl,
        tagName: 'tr',
    });

    views.EnvTableRow = Backbone.Marionette.ItemView.extend({
        template: envTableRowTpl,
        tagName: 'tr',
    });

    views.WizardEnvSubView = Backbone.Marionette.CompositeView.extend({
        template: podContainerEnvTabTpl,
        tagName: 'div',
        childView: views.EnvTableRow,
        emptyView: views.EnvTableRowEmpty,
        childViewContainer: '.env-table tbody',

        ui: {
            stopContainer  : '#stopContainer',
            startContainer : '#startContainer',
            updateContainer: '.container-update',
            checkForUpdate : '.check-for-update',
        },

        events: {
            'click @ui.stopContainer'  : 'stopContainer',
            'click @ui.startContainer' : 'startContainer',
            'click @ui.updateContainer': 'updateContainer',
            'click @ui.checkForUpdate' : 'checkContainerForUpdate',
        },

        triggers: {
            'click .go-to-ports'  : 'step:portconf',
            'click .go-to-stats'  : 'step:statsconf',
            'click .go-to-logs'   : 'step:logsconf',
        },

        modelEvents: {
            'change': 'render'
        },

        initialize: function(options) {
            var before = this.model.get('before');
            this.podBefore = before ? before.getPod() : this.model.get('after').getPod().editOf();
            this.podAfter = this.podBefore.get('edited_config') || this.podBefore;
            this.model.addNestedChangeListener(this, this.render);

            this.collection = new Model.DiffCollection([], {
                modelType: Model.EnvVar,
                before: this.model.get('before').get('env'),
                after: this.model.get('after').get('env'),
            });
        },

        templateHelpers: function(){
            var before = this.model.get('before'),
                after = this.model.get('after');
            this.podBefore.recalcInfo();
            this.podAfter.recalcInfo();
            return {
                // TODO: move common parts out of those views
                podID: this.podBefore.id,
                state: before ? before.get('state') : 'new',
                image: (before || after).get('image'),
                sourceUrl: (before || after).get('sourceUrl'),
                kubes: (before || after).get('kubes'),
                limits: (before || after).limits,
                updateIsAvailable: before && before.updateIsAvailable,
                kube_type: this.podBefore.getKubeType(),
                restart_policy: this.podBefore.get('restartPolicy'),
            };
        },

        startContainer: function(){ this.podBefore.cmdStart(); },
        stopContainer: function(){ this.podBefore.cmdStop(); },
        updateContainer: function(){ this.model.get('before').update(); },
        checkContainerForUpdate: function(){
            this.model.get('before').checkForUpdate().done(this.render);
        },
    });

    views.WizardStatsSubItemView = Backbone.Marionette.ItemView.extend({
        template: podItemGraphTpl,

        initialize: function(options){ this.container = options.container; },

        ui: {
            chart: '.graph-item'
        },

        onShow: function(){
            var lines = this.model.get('lines'),
                running = this.container.get('state') === 'running',
                series = this.model.get('series'),
                options = {
                title: this.model.get('title'),
                axes: {
                    xaxis: {label: 'time', renderer: $.jqplot.DateAxisRenderer},
                    yaxis: {label: this.model.get('ylabel'), min: 0}
                },
                seriesDefaults: {
                    showMarker: false,
                    rendererOptions: {
                        smooth: true
                    }
                },
                series: series,
                grid: {
                    background: '#ffffff',
                    drawBorder: false,
                    shadow: false
                },
                legend: {
                    show: true,
                    placement: 'insideGrid'
                },
                noDataIndicator: {
                    show: true,
                    indicator: !running ? 'Container is not running...' :
                        'Collecting data... plot will be dispayed in a few minutes.',
                    axes: {
                        xaxis: {
                            min: App.currentUser.localizeDatetime(+new Date() - 1000*60*20),
                            max: App.currentUser.localizeDatetime(),
                            tickOptions: {formatString:'%H:%M'},
                            tickInterval: '5 minutes',
                        },
                        yaxis: {min: 0, max: 150, tickInterval: 50}
                    }
                },
            };

            var points = [];
            for (var i=0; i<lines;i++)
                points.push([]);

            // If there is only one point, jqplot will display ugly plot with
            // weird grid and no line.
            // Remove this point to force jqplot to show noDataIndicator.
            if (this.model.get('points').length === 1)
                this.model.get('points').splice(0);

            this.model.get('points').forEach(function(record){
                var time = App.currentUser.localizeDatetime(record[0]);
                for (var i=0; i<lines; i++)
                    points[i].push([time, record[i+1]]);
            });
            this.ui.chart.jqplot(points, options);
        }
    });

    views.WizardStatsSubView = Backbone.Marionette.CompositeView.extend({
        childView: views.WizardStatsSubItemView,
        childViewContainer: "div.container-stats #monitoring-page",
        template: podContainerStatsTabTpl,
        tagName: 'div',

        childViewOptions: function() {
            return {container: this.model.get('before')};
        },

        events: {
            'click #stopContainer'    : 'stopContainer',
            'click #startContainer'   : 'startContainer',
            'click .container-update' : 'updateContainer',
            'click .check-for-update' : 'checkContainerForUpdate',
        },

        triggers: {
            'click .go-to-ports'     : 'step:portconf',
            'click .go-to-envs'      : 'step:envconf',
            'click .go-to-logs'      : 'step:logsconf'
        },

        modelEvents: {
            'change': 'render'
        },

        initialize: function() {
            this.pod = this.model.get('before').getPod();
            this.model.addNestedChangeListener(this, this.render);
        },

        templateHelpers: function(){
            var before = this.model.get('before');
            this.pod.recalcInfo();
            return {
                // TODO: move common parts out of those views
                updateIsAvailable: before.updateIsAvailable,
                podID: this.pod.id,
                kube_type: this.pod.getKubeType(),
                limits: before.limits,
                restart_policy: this.pod.get('restartPolicy'),
                state: before.get('state'),
                image: before.get('image'),
                sourceUrl: before.get('sourceUrl'),
                kubes: before.get('kubes'),
            };

        },

        startContainer: function(){ this.pod.cmdStart(); },
        stopContainer: function(){ this.pod.cmdStop(); },
        updateContainer: function(){ this.model.get('before').update(); },
        checkContainerForUpdate: function(){
            this.model.get('before').checkForUpdate().done(this.render);
        },
    });

    views.WizardLogsSubView = Backbone.Marionette.ItemView.extend({
        template: podContainerLogsTabTpl,
        tagName: 'div',

        ui: {
            ieditable          : '.ieditable',
            textarea           : '.container-logs',
            stopItem           : '#stopContainer',
            startItem          : '#startContainer',
            updateContainer    : '.container-update',
            checkForUpdate     : '.check-for-update',
            editContainerKubes : '.editContainerKubes',
            changeKubeQty      : 'button.send',
            cancelChange       : 'button.cancel',
            kubeVal            : '.editForm input',
        },

        events: {
            'click @ui.stopItem'           : 'stopItem',
            'click @ui.startItem'          : 'startItem',
            'click @ui.updateContainer'    : 'updateContainer',
            'click @ui.checkForUpdate'     : 'checkContainerForUpdate',
            'click @ui.changeKubeQty'      : 'changeKubeQty',
            'click @ui.editContainerKubes' : 'editContainerKubes',
            'click @ui.cancelChange'       : 'closeChange',
            'keyup @ui.kubeVal'            : 'kubeVal'
        },

        triggers: {
            'click .go-to-ports'     : 'step:portconf',
            'click .go-to-envs'      : 'step:envconf',
            'click .go-to-stats'     : 'step:statsconf'
        },

        modelEvents: {
            'change': 'render'
        },

        initialize: function() {
            this.pod = this.model.get('before').getPod();
            this.model.addNestedChangeListener(this, this.render);
            _.bindAll(this, 'getLogs');
            this.getLogs();
        },

        templateHelpers: function(){
            var before = this.model.get('before');
            this.pod.recalcInfo();
            return {
                logs: before.logs,
                logsError: before.logsError,
                editKubesQty : before.editKubesQty,
                kubeVal : before.kubeVal,

                // TODO: move common parts out of those views
                updateIsAvailable: before.updateIsAvailable,
                parentID: this.pod.id,
                kube_type: this.pod.getKubeType(),
                limits: before.limits,
                restart_policy: this.pod.get('restartPolicy'),
                state: before.get('state'),
                image: before.get('image'),
                sourceUrl: before.get('sourceUrl'),
                kubes: before.get('kubes'),
            };
        },

        onBeforeRender: function () {
            var el = this.ui.textarea;
            if (typeof el !== 'object' || (el.scrollTop() + el.innerHeight()) === el[0].scrollHeight)
                this.logScroll = null;  // stick to bottom
            else
                this.logScroll = el.scrollTop();  // stay at this position
        },

        onRender: function () {
            if (this.logScroll === null)  // stick to bottom
                this.ui.textarea.scrollTop(this.ui.textarea[0].scrollHeight);
            else  // stay at the same position
                this.ui.textarea.scrollTop(this.logScroll);

            if (this.niceScroll !== undefined)
                this.niceScroll.remove();
            this.niceScroll = this.ui.textarea.niceScroll({
                cursorcolor: "#69AEDF",
                cursorwidth: "12px",
                cursorborder: "none",
                cursorborderradius: "none",
                background: "#E7F4FF",
                autohidemode: false,
                railoffset: 'bottom'
            });
        },

        onBeforeDestroy: function () {
            delete this.model.get('before').kubeVal;
            delete this.model.get('before').editKubesQty;
            this.destroyed = true;
            clearTimeout(this.model.get('before').get('timeout'));
            if (this.niceScroll !== undefined)
                this.niceScroll.remove();
        },

        getLogs: function() {
            var that = this;
            this.model.get('before').getLogs(/*size=*/100).always(function(){
                // callbacks are called with model as a context
                if (!that.destroyed) {
                    this.set('timeout', setTimeout(that.getLogs, 10000));
                    that.render();
                }
            });
        },

        editContainerKubes: function(){
            this.model.get('before').editKubesQty = true;
            this.model.get('before').kubeVal = this.model.get('before').get('kubes');
            this.render();
        },

        kubeVal: function(){
            this.model.get('before').kubeVal = this.ui.kubeVal.val();
        },

        changeKubeQty: function(){
            //TODO add change Request
            this.closeChange();
        },

        closeChange: function(){
            delete this.model.get('before').kubeVal;
            delete this.model.get('before').editKubesQty;
            this.render();
        },

        startItem: function(){ this.pod.cmdStart(); },
        stopItem: function(){ this.pod.cmdStop(); },

        updateContainer: function(){ this.model.get('before').update(); },
        checkContainerForUpdate: function(){
            this.model.get('before').checkForUpdate().done(this.render);
        }
    });

    return views;
});
