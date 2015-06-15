define(['pods_app/app',
        'tpl!pods_app/templates/layout_pod_item.tpl',
        'tpl!pods_app/templates/page_header_title.tpl',
        'tpl!pods_app/templates/page_info_panel.tpl',
        'tpl!pods_app/templates/page_container_item.tpl',
        'tpl!pods_app/templates/pod_item_controls.tpl',
        'tpl!pods_app/templates/pod_item_graph.tpl',
        'moment-timezone', 'pods_app/utils',
        'bootstrap', 'bootstrap-editable', 'jqplot', 'jqplot-axis-renderer'
        ],
       function(Pods,
                layoutPodItemTpl,
                pageHeaderTitleTpl,
                pageInfoPanelTpl,
                pageContainerItemTpl,
                podItemControlsTpl,
                podItemGraphTpl,
                moment, utils){

    Pods.module('Views.Item', function(Item, App, Backbone, Marionette, $, _){

        function localizeDatetime(dt, tz){
            try {
                return moment(dt).tz(tz).format('HH:mm:ss YYYY-MM-DD');
            } catch (e){
                console.log(e);
            }
            return moment(dt).format('HH:mm:ss YYYY-MM-DD');
        }

        Item.PodItemLayout = Backbone.Marionette.LayoutView.extend({
            template : layoutPodItemTpl,

            regions: {
                masthead : '#masthead-title',
                controls : '#item-controls',
                info     : '#item-info',
                contents : '#layout-contents'
            },

            initialize: function(){
                var that = this;
                this.listenTo(this.controls, 'show', function(view){
                    that.listenTo(view, 'display:pod:stats', that.showPodStats);
                    that.listenTo(view, 'display:pod:list', that.showPodList);
                });
            },

            showPodStats: function(data){
                this.trigger('display:pod:stats', data);
            },

            showPodList: function(data){
                this.trigger('display:pod:list', data);
            }
        });

        Item.PageHeader = Backbone.Marionette.ItemView.extend({
            template: pageHeaderTitleTpl
        });

        // View for showing a single container item as a container in containers list
        Item.InfoPanelItem = Backbone.Marionette.ItemView.extend({
            template    : pageContainerItemTpl,
            tagName     : 'tr',
            className   : 'container-item',

            templateHelpers: function(){
                var modelIndex = this.model.collection.indexOf(this.model);
                var kubes = this.model.get('kubes');
                var startedAt = this.model.get('startedAt');
                return {
                    index: modelIndex + 1,
                    kubes: kubes ? kubes : 0,
                    startedAt: typeof(startedAt) == 'undefined' ? 'Stopped' : localizeDatetime(startedAt, userSettings.timezone)
                }
            },

            ui: {
                'start'  : '.start-btn',
                'stop'   : '.stop-btn',
                'delete' : '.terminate-btn'
            },

            events: {
                'click @ui.start' : 'startItem',
                'click @ui.stop'  : 'stopItem',
                'click @ui.delete'  : 'deleteItem',
            },

            command: function(evt, cmd){
                var that = this,
                    preloader = $('#page-preloader');
                preloader.show();
                evt.stopPropagation();
                var model = App.WorkFlow.getCollection().fullCollection.get(this.model.get('parentID')),
                    _containers = [],
                    host = null;
                _.each(model.get('containers'), function(itm){
                    if(itm.name == that.model.get('name'))
                        _containers.push(itm.containerID);
                        host = model.get('host');
                });
                $.ajax({
                    url: '/api/podapi/' + model.get('id'),
                    data: {command: cmd, host: host, containers: _containers.join(',')},
                    type: 'PUT',
                    dataType: 'JSON',
                    success: function(rs){
                        preloader.hide();
                    },
                    error: function(xhr){
                        utils.modelError(xhr);
                    }
                });
                //$.ajax({
                //    url: '/api/pods/containers',
                //    data: {action: cmd, host: host, containers: _containers.join(','),
                //           pod_uuid: model.get('id')},
                //    type: 'PUT',
                //    dataType: 'JSON',
                //    success: function(rs){
                //        preloader.hide();
                //    },
                //    error: function(xhr){
                //        utils.modelError(xhr);
                //    }
                //});
            },
            startItem: function(evt){
                this.command(evt, 'start');
            },
            stopItem: function(evt){
                this.command(evt, 'stop');
            },
            deleteItem: function(evt){
                var that = this,
                    name = that.model.get('name');
                utils.modalDialog({
                    title: "Delete container?",
                    body: "Are you sure want to delete container '" + name + "'?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            this.command(evt, 'delete');
                        },
                        buttonCancel: true
                    }
                });
            },
        });

        Item.InfoPanel = Backbone.Marionette.CompositeView.extend({
            template  : pageInfoPanelTpl,
            childView: Item.InfoPanelItem,
            childViewContainer: "tbody",

            events: {
                'click .stop-checked'  : 'stopItems',
                'click .start-checked' : 'startItems',
            },

            command: function(cmd){
                var preloader = $('#page-preloader');
                    preloader.show();
                var model;
                var containers = [];
                containerCollection.forEach(function(i){
                    if (i.get('checked') === true){
                        model = App.WorkFlow.getCollection().fullCollection.get(i.get('parentID'));
                        _.each(model.get('containers'), function(itm){
                            if(itm.name == i.get('name'))
                                containers.push(itm.containerID);
                        });
                    }
                });
                if(model)
               /* model.set({'command': cmd, 'containers': containers});*/
                model.save({'command': cmd, 'containers_action': containers}, {
                    success: function(){
                        preloader.hide();
                    },
                    error: function(model, response, options, data){
                        preloader.hide();
                        utils.modelError(response);
                    }
                });

            },
            startItems: function(evt){
                this.command('start');
            },

            stopItems: function(evt){
                this.command('stop');
            },


        });

        Item.ControlsPanel = Backbone.Marionette.ItemView.extend({
            template: podItemControlsTpl,
            tagName: 'div',
            className: 'pod-controls',

            events: {
                'click .stats-btn'     : 'statsItem',
                'click .list-btn'      : 'listItem',
                'click .start-btn'     : 'startItem',
                'click .stop-btn'      : 'stopItem',
                'click .terminate-btn' : 'terminateItem'
            },

            templateHelpers: function(){
                var thisItem = this.getItem();
                var kubeType = '',
                    labels = thisItem.get('labels'),
                    publicIP = labels !== undefined ? labels['kuberdock-public-ip'] : '';
                _.each(kubeTypes, function(kube){
                    if(parseInt(kube.id) == parseInt(thisItem.get('kube_type')))
                        kubeType = kube.name;
                });
                return {
                    name:          thisItem.get('name'),
                    status:        thisItem.get('status'),
                    replicas:      thisItem.get('replicas'),
                    kubes:         thisItem.get('kubes'),
                    price:         thisItem.get('price'),
                    kubeType:      kubeType,
                    publicIP:      publicIP,
                    serviceIP:     thisItem.get('serviceIP'),
                    restartPolicy: thisItem.get('restartPolicy')
                };
            },

            getItem: function(){
                return App.WorkFlow.getCollection().fullCollection.get(this.model.id);
            },

            statsItem: function(evt){
                evt.stopPropagation();
                var item = this.getItem();
                this.trigger('display:pod:stats', item);
            },

            listItem: function(evt){
                evt.stopPropagation();
                var item = this.getItem();
                this.trigger('display:pod:list', item);
            },

            startItem: function(evt){
                var item = this.getItem(),
                    that = this,
                    preloader = $('#page-preloader');
                    preloader.show();
                evt.stopPropagation();
                item.save({command: 'start'}, {
                    wait: true,
                    success: function(model, response, options){
                        that.render();
                        preloader.hide();
                    },
                    error: function(model, response, options, data){
                        preloader.hide();
                        that.render();
                        utils.modelError(response);
                    }
                });
            },

            stopItem: function(evt){
                var item = this.getItem(),
                    that = this,
                    preloader = $('#page-preloader');
                    preloader.show();
                evt.stopPropagation();
                item.save({command: 'stop'}, {
                    wait: true,
                    success: function(model, response, options){
                        that.render();
                        preloader.hide();
                    },
                    error: function(model, response, options, data){
                        preloader.hide();
                        utils.modelError(response);
                    }
                });
            },

            terminateItem: function(evt){
                var that = this,
                    item = that.getItem(),
                    name = item.get('name'),
                    preloader = $('#page-preloader');
                utils.modalDialog({
                    title: "Delete " + name + "?",
                    body: "Are you sure want to delete pod '" + name + "'?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            preloader.show();
                            item.destroy({
                                wait: true,
                                success: function(){
                                    var col = App.WorkFlow.getCollection();
                                    col.remove(item);
                                    preloader.hide();
                                    window.location.href = '/#pods';
                                },
                                error: function(model, response, options, data){
                                    preloader.hide();
                                    utils.modelError('Could not remove ' + name);
                                }
                            });
                        },
                        buttonCancel: true
                    }
                });
            }
        });

        Item.PodGraphItem = Backbone.Marionette.ItemView.extend({
            template: podItemGraphTpl,

            ui: {
                chart: '.graph-item'
            },

            onShow: function(){
                var lines = this.model.get('lines');
                var options = {
                    title: this.model.get('title'),
                    axes: {
                        xaxis: {label: 'time', renderer: $.jqplot.DateAxisRenderer},
                        yaxis: {label: this.model.get('ylabel')}
                    },
                    seriesDefaults: {
                        showMarker: false,
                        rendererOptions: {
                            smooth: true
                        }
                    },
                    grid: {
                        background: '#ffffff',
                        drawBorder: false,
                        shadow: false
                    }
                };

                var points = [];
                for (var i=0; i<lines; i++) {
                    if (points.length < i+1) {
                        points.push([])
                    }
                }

                this.model.get('points').forEach(function(record){
                    for (var i=0; i<lines; i++) {
                        points[i].push([record[0], record[i+1]])
                    }
                });

                try {
                    this.ui.chart.jqplot(points, options);
                }
                catch(e){
                    console.log('Cannot display graph');
                }

            }
        });

        Item.PodGraph = Backbone.Marionette.CollectionView.extend({
            childView: Item.PodGraphItem
        });

    });

    return Pods.Views.Item;

});
