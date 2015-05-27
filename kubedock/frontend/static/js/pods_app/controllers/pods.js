define(['pods_app/app', 'pods_app/models/pods'], function(Pods){

    //function modalDialog(options){
    //    var modal = $('.modal');
    //    if(options.title) modal.find('.modal-title').html(options.title);
    //    if(options.body) modal.find('.modal-body').html(options.body);
    //    if(options.large) modal.addClass('bs-example-modal-lg');
    //    if(options.small) modal.addClass('bs-example-modal-sm');
    //    if(options.show) modal.modal('show');
    //    return modal;
    //}

    Pods.module("WorkFlow", function(WorkFlow, App, Backbone, Marionette, $, _){

        WorkFlow.getCollection = function(){
            if (!WorkFlow.hasOwnProperty('PodCollection')) {
                WorkFlow.PodCollection = new App.Data.PodCollection(podCollectionData);
            }
            return WorkFlow.PodCollection;
        }

        WorkFlow.Router = Marionette.AppRouter.extend({
            appRoutes: {
                'pods': 'showPods',
                'pods/:id': 'showPodItem',
                'newpod': 'createPod',
                'poditem/:id/:name': 'showPodContainer'
            }
        });

        WorkFlow.Controller = Marionette.Controller.extend({

            showPods: function(){
                var that = this;
                require(['pods_app/views/pods_list',
                         'pods_app/views/paginator'], function(){
                    var listLayout = new App.Views.List.PodListLayout();
                    var podCollection = new App.Views.List.PodCollection({
                        collection: WorkFlow.getCollection()
                    });

                    that.listenTo(listLayout, 'show', function(){
                        listLayout.list.show(podCollection);
                        listLayout.pager.show(
                            new App.Views.Paginator.PaginatorView({
                                view: podCollection
                            })
                        );
                    });
                    that.listenTo(listLayout, 'clear:pager', function(){
                        listLayout.pager.empty();
                    });
                    App.contents.show(listLayout);
                });
            },

            showPodItem: function(id){
                var that = this;
                require(['pods_app/views/pod_item',
                         'pods_app/views/paginator'], function(){
                    var itemLayout = new App.Views.Item.PodItemLayout(),
                        model = WorkFlow.getCollection().fullCollection.get(id);

                    if (model === undefined) {
                        Pods.navigate('pods');
                        that.showPods();
                        return;
                    }
                    _.each(model.get('containers'), function(i){
                            i.parentID = this.parentID;
                            //i.kubes = this.kubes;
                        }, {parentID: id, kubes: model.get('kubes')});

                    var _containerCollection = model.get('containers');
                    var newContainerCollection = [];
                    _.each(model.get('dockers'), function(el){
                        var container = {};
                        _.each(_containerCollection, function(c){
                            if(c.name == el.info.name){
                                $.each(c, function(k, v){
                                    container[k] = v;
                                });

                                container['info'] = el.info;
                                $.each(container.info.state, function(k, v){
                                    container['state_repr'] = k;
                                    container['startedAt'] = v.startedAt;
                                });
                            }
                        });
                        newContainerCollection.push(container);
                    });
                    containerCollection = new Backbone.Collection(newContainerCollection);

                    var masthead = new App.Views.Item.PageHeader({
                        model: new Backbone.Model({name: model.get('name')})
                    });

                    var infoPanel = new App.Views.Item.InfoPanel({
                        //childView: App.Views.Item.InfoPanelItem,
                        //childViewContainer: "tbody",
                        collection: containerCollection
                    });

                    that.listenTo(itemLayout, 'display:pod:stats', function(data){
                        var statCollection = new App.Data.StatsCollection(),
                            that = this;
                        statCollection.fetch({
                            data: {unit: data.get('id')},
                            reset: true,
                            success: function(){
                                itemLayout.controls.show(new App.Views.Item.ControlsPanel({
                                    model: new Backbone.Model({id: model.get('id'), graphs: true})
                                }));
                                itemLayout.info.show(new App.Views.Item.PodGraph({
                                    collection: statCollection
                                }));
                            },
                            error: function(){
                                console.log('failed to fetch graphs');
                            }
                        })
                    });

                    that.listenTo(itemLayout, 'display:pod:list', function(data){

                        itemLayout.controls.show(new App.Views.Item.ControlsPanel({
                            model: new Backbone.Model({id: model.get('id'), graphs: false})
                        }));

                        itemLayout.info.show(new App.Views.Item.InfoPanel({
                            //childView: App.Views.InfoPanelItem,
                            //childViewContainer: "tbody",
                            collection: containerCollection
                        }));
                    });

                    that.listenTo(itemLayout, 'show', function(){
                        itemLayout.masthead.show(masthead);
                        itemLayout.controls.show(new App.Views.Item.ControlsPanel({
                            model: new Backbone.Model({id: model.get('id'), graphs: false})
                        }));
                        itemLayout.info.show(infoPanel);
                    });
                    App.contents.show(itemLayout);
                });
            },

            showPodContainer: function(id, name){
                var that = this;
                require(['pods_app/views/pod_create',
                         'pods_app/views/paginator',
                         'pods_app/views/loading'], function(){
                    var wizardLayout = new App.Views.NewItem.PodWizardLayout(),
                        parent_model = WorkFlow.getCollection().fullCollection.get(id),
                        model_data = _.filter(
                            parent_model.get('containers'),
                            function(i){return i.name === this.n},
                            {n: name}
                        )[0],
                        container = _.filter(
                                parent_model.get('dockers'),
                                function(i){return i.info.name === this.n},
                                {n: model_data.name}
                            )[0],
                        container_id = _.last(container.info.containerID.split('/'));
                    $.each(container.info.state, function(k, v){
                        container['state_repr'] = k;
                        container['startedAt'] = v.startedAt;
                    });
                    model_data.container_id = container_id;
                    model_data.node = parent_model.get('dockers')[0].host;
                    if (!model_data.hasOwnProperty('kubes')) model_data['kubes'] = 1;
                    if (!model_data.hasOwnProperty('workingDir')) model_data['workingDir'] = undefined;
                    if (!model_data.hasOwnProperty('args')) model_data['args'] = [];
                    if (!model_data.hasOwnProperty('env')) model_data['env'] = [];
                    if (!model_data.hasOwnProperty('parentID')) model_data['parentID'] = id;
                    if (!model_data.hasOwnProperty('state_repr')) model_data['state_repr'] = container['state_repr'];

                    //this.listenTo(wizardLayout, 'show', function(){
                    //    wizardLayout.steps.show(new App.Views.WizardPortsSubView({
                    //        model: new App.Data.Image(model_data)
                    //    }));
                    //});
                    that.listenTo(wizardLayout, 'show', function(){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardLogsSubView({
                            model: new App.Data.Image(model_data)
                        }));
                    });

                    that.listenTo(wizardLayout, 'step:portconf', function(data){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardPortsSubView({model: data}));
                    });
                    that.listenTo(wizardLayout, 'step:volconf', function(data){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardVolumesSubView({model: data}));
                    });
                    that.listenTo(wizardLayout, 'step:envconf', function(data){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardEnvSubView({model: data}));
                    });
                    that.listenTo(wizardLayout, 'step:resconf', function(data){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardResSubView({model: data}));
                    });
                    that.listenTo(wizardLayout, 'step:otherconf', function(data){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardOtherSubView({model: data}));
                    });
                    that.listenTo(wizardLayout, 'step:statsconf', function(data){
                        var statCollection = new App.Data.StatsCollection();
                        statCollection.fetch({
                            data: {unit: data.get('parentID'), container: data.get('name')},
                            reset: true,
                            success: function(){
                                wizardLayout.steps.show(new App.Views.NewItem.WizardStatsSubView({
                                    containerModel: data,
                                    collection:statCollection
                                }));
                            },
                            error: function(){
                                console.log('failed to fetch graphs');
                            }
                        });
                    });
                    that.listenTo(wizardLayout, 'step:logsconf', function(data){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardLogsSubView({model: data}));
                    });
                    App.contents.show(wizardLayout);
                });
            },

            createPod: function(){
                var that = this;
                require(['pods_app/utils',
                         'pods_app/views/pod_create',
                         'pods_app/views/paginator',
                         'pods_app/views/loading'], function(utils){
                    var model = new App.Data.Pod({name: "Unnamed-1", containers: [], volumes: []}),
                        wizardLayout = new App.Views.NewItem.PodWizardLayout();

                    var processRequest = function(data){
                        var hasPublic = function(containers){
                            for (var i in containers) {
                                for (var j in containers[i].ports) {
                                    if (containers[i].ports[j].hasOwnProperty('isPublic')
                                            && containers[i].ports[j].isPublic) {
                                        return true;
                                    }
                                }
                            }
                            return false;
                        };
                        if (data.has('persistentDrives')) { delete data.attributes.persistentDrives; }
                        _.each(data.get('containers'), function(c){
                            if (c.hasOwnProperty('persistentDrives')) { delete c.persistentDrives; }
                        });
                        if (hasPublic(data.get('containers'))) {
                            data.attributes['set_public_ip'] = true;
                        }
                        else {
                            data.attributes['set_public_ip'] = false;
                        }
                        WorkFlow.getCollection().fullCollection.create(data.attributes, {
                            wait: true,
                            success: function(){
                                Pods.navigate('pods');
                                that.showPods();
                            },
                            error: function(model, response, options, data){
                                console.log('error applying data');
                                var body = response.responseJSON ? JSON.stringify(response.responseJSON.data) : response.responseText;
                                utils.modalDialog({
                                    title: 'Error',
                                    body: body,
                                    show: true
                                });
                            }
                        });
                    };

                    that.listenTo(wizardLayout, 'show', function(){
                        wizardLayout.header.show(new App.Views.NewItem.PodHeaderView({model: model}));
                        wizardLayout.steps.show(new App.Views.NewItem.GetImageView());
                    });
                    that.listenTo(wizardLayout, 'image:fetched', function(data){
                        wizardLayout.footer.show(new App.Views.Paginator.PaginatorView({view: data}));
                    });
                    that.listenTo(wizardLayout, 'clear:pager', function(){
                        wizardLayout.footer.empty();
                    });
                    that.listenTo(wizardLayout, 'step:getimage', function(data){
                        wizardLayout.steps.show(new App.Views.NewItem.GetImageView());
                    });
                    that.listenTo(wizardLayout, 'step:portconf', function(data){
                        wizardLayout.steps.show(new App.Views.NewItem.WizardPortsSubView({model: data}));
                    });
                    that.listenTo(wizardLayout, 'step:envconf', function(data){
                        if (data.has('containers')) { // the pod model, not a container one
                            wizardLayout.steps.show(new App.Views.NewItem.WizardEnvSubView({
                                model: new App.Data.Image(_.last(model.get('containers')))
                            }));
                        }
                        else {
                            wizardLayout.steps.show(new App.Views.NewItem.WizardEnvSubView({model: data}));
                        }
                    });
                    that.listenTo(wizardLayout, 'pod:save', function(data){
                        data.unset('lastAddedImage', {silent: true});
                        data.set({'save_only': true}, {silent: true});
                        processRequest(data);
                    });
                    that.listenTo(wizardLayout, 'pod:run', function(data){
                        data.set({'save_only': false}, {silent: true});
                        processRequest(data);
                    });
                    that.listenTo(wizardLayout, 'step:complete', function(data){
                        _.each(data.get('volumeMounts'), function(mp){
                            var row = model.get('volumes'),
                                entry;
                            if (mp.isPersistent) {
                                entry = {name: mp.name, persistentDisk: mp.persistentDisk};
                                var used = _.filter(data.attributes.persistentDrives,
                                    function(i){return i.pdName === mp.persistentDisk.pdName});
                                if (used.length) {
                                    used[0].used = true;
                                }
                            }
                            else {
                                entry = {name: mp.name, emptyDir: {}};
                            }
                            row.push(entry);
                            delete mp['isPersistent'];
                            delete mp['persistentDisk'];
                        });

                        // strip persistentDrives from a container if any
                        if (data.attributes.hasOwnProperty('persistentDrives')) {
                            if (!model.has('persistentDrives')) {
                                model.attributes['persistentDrives'] = data.attributes.persistentDrives;
                            }
                            delete data.attributes.persistentDrives;
                        }

                        // Here we populate a pod model container
                        var container = _.last(model.get('containers'));
                        _.each(data.attributes, function(value, key, obj){
                            this.container[key] = value;
                        }, {container: container});

                        var rqst = $.ajax({
                            type: 'GET',
                            url: '/api/ippool/getFreeHost'
                        });
                        rqst.done(function(rs){
                            model.set({freeHost: rs.data});
                            wizardLayout.steps.show(new App.Views.NewItem.WizardCompleteSubView({
                                model: model
                            }));
                        });
                    });
                    that.listenTo(wizardLayout, 'image:selected', function(image){
                        var that = this,
                            slash = image.indexOf('/'),
                            name = (slash >= 0) ? image.substring(slash+1) : image,
                            rqst = $.ajax({
                                type: 'POST',
                                url: '/api/images/new',
                                data: {image: image}
                            });
                        name += _.map(_.range(10), function(i){return _.random(1, 10);}).join('');
                        var contents = {
                            image: image, name: name, workingDir: null,
                            ports: [], volumeMounts: [], env: [], args: [], kubes: 1,
                            terminationMessagePath: null
                        };
                        if (model.has('persistentDrives')) {
                            contents['persistentDrives'] = model.get('persistentDrives');
                        }
                        model.get('containers').push(contents);
                        model.set('lastAddedImage', image);
                        rqst.done(function(data){
                            if (data.hasOwnProperty('data')) { data = data['data']; }
                            model.fillContainer(contents, data);
                            wizardLayout.steps.show(new App.Views.NewItem.WizardPortsSubView({model: model}));
                        });
                        wizardLayout.steps.show(new App.Views.Loading.LoadingView());
                    });
                    App.contents.show(wizardLayout);
                });
            }
        });

        WorkFlow.addInitializer(function(){
            var controller = new WorkFlow.Controller();
            new WorkFlow.Router({
                controller: controller
            });
            if (typeof(EventSource) === undefined) {
                console.log('ERROR: EventSource is not supported by browser');
            } else {
                var source = new EventSource("/api/stream");
                source.addEventListener('pull_pods_state', function () {
                    WorkFlow.getCollection().fetch();
                }, false);
                source.onerror = function () {
                    console.log("SSE Error");
                    // TODO Setup here timer to reconnect, maybe via location.reload
                };
            }
        });

    });

    Pods.on('pods:list', function(){
        var controller = new Pods.WorkFlow.Controller();
        Pods.navigate('pods');
        controller.showPods();
    });

    return Pods.WorkFlow.Controller;
});
