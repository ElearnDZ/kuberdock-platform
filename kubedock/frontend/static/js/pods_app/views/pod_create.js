define(['pods_app/app',
        'tpl!pods_app/templates/layout_wizard.tpl',
        'tpl!pods_app/templates/breadcrumb_header.tpl',
        'tpl!pods_app/templates/wizard_image_collection_item.tpl',
        'tpl!pods_app/templates/wizard_get_image.tpl',
        'tpl!pods_app/templates/wizard_set_container_pending_basic_settings.tpl',
        'tpl!pods_app/templates/wizard_set_container_settled_basic_settings.tpl',
        'tpl!pods_app/templates/wizard_set_container_env.tpl',
        'tpl!pods_app/templates/wizard_set_container_logs.tpl',
        'tpl!pods_app/templates/wizard_set_container_stats.tpl',
        'tpl!pods_app/templates/pod_item_graph.tpl',
        'tpl!pods_app/templates/wizard_set_container_complete.tpl',
        'pods_app/utils',
        'bootstrap', 'bootstrap-editable', 'jqplot',
        'jqplot-axis-renderer', 'numeral', 'selectpicker', 'mousewheel', 'jscrollpane'],
       function(Pods,
                layoutWizardTpl,
                breadcrumbHeaderTpl,
                wizardImageCollectionItemTpl,
                wizardGetImageTpl,
                wizardSetContainerPendingBasicSettingsTpl,
                wizardSetContainerSettledBasicSettingsTpl,
                wizardSetContainerEnvTpl,
                wizardSetContainerLogsTpl,
                wizardSetContainerStatsTpl,
                podItemGraphTpl,
                wizardSetContainerCompleteTpl,
                utils){

    Pods.module('Views.NewItem', function(NewItem, App, Backbone, Marionette, $, _){

        NewItem.PodWizardLayout = Backbone.Marionette.LayoutView.extend({
            template: layoutWizardTpl,
            initialize: function(){
                var that = this;
                this.listenTo(this.steps, 'show', function(view){
                    that.listenTo(view, 'step:getimage', that.getImage);
                    that.listenTo(view, 'image:selected', that.imageSelected);
                    that.listenTo(view, 'step:portconf', that.portConf);
                    that.listenTo(view, 'step:volconf', that.volConf);
                    that.listenTo(view, 'step:envconf', that.envConf);
                    that.listenTo(view, 'step:resconf', that.resConf);
                    that.listenTo(view, 'step:otherconf', that.otherConf);
                    that.listenTo(view, 'step:statsconf', that.statsConf);
                    that.listenTo(view, 'step:logsconf', that.logsConf);
                    that.listenTo(view, 'step:complete', that.completeConf);
                    that.listenTo(view, 'image:fetched', that.imageFetched);
                    that.listenTo(view, 'pager:clear', that.clearPager);
                    that.listenTo(view, 'pod:save', that.podSave);
                    that.listenTo(view, 'image:searchsubmit', that.imageSearchSubmit);
                    that.listenTo(view, 'image:getnextpage', that.imageGetNextPage);
                });
            },
            regions: {
                header: '#header-steps',
                steps: '#steps',
                sidebar: '#sidebar',
                footer: '#footer-steps'
            },
            getImage: function(data){
                this.trigger('step:getimage', data);
            },
            imageSelected: function(image, auth){
                this.trigger('image:selected', image, auth);
            },
            portConf: function(data){
                this.trigger('step:portconf', typeof data === 'string' ? data : data.model);
            },
            volConf: function(data){
                this.trigger('step:volconf', data.model);
            },
            envConf: function(data){
                this.trigger('step:envconf', typeof data === 'string' ? data : data.model);
            },
            resConf: function(data){
                this.trigger('step:resconf', data.model);
            },
            otherConf: function(data){
                this.trigger('step:otherconf', data.model);
            },
            statsConf: function(data){
                this.trigger('step:statsconf', data.model);
            },
            logsConf: function(data){
                this.trigger('step:logsconf', data.model);
            },
            completeConf: function(data){
                this.trigger('step:complete', data.model);
            },
            imageFetched: function(data){
                this.trigger('image:fetched', data);
            },
            clearPager: function(){
                this.trigger('clear:pager');
            },
            podSave: function(data){
                this.trigger('pod:save', data.model);
            },
            imageSearchSubmit: function(data){
                this.trigger('image:searchsubmit', data);
            },
            imageGetNextPage: function(collection, query){
                this.trigger('image:getnextpage', collection, query);
            }
        });

        NewItem.PodHeaderView = Backbone.Marionette.ItemView.extend({
            template: breadcrumbHeaderTpl,
            tagName: 'div',

            initialize: function(options){
                this.model = options.model;
            },

            ui: {
                podsList     : '.podsList',
                peditable    : '.peditable',
            },

            events: {
                'click @ui.podsList' : 'showPodsList',
            },

            onRender: function(){
                var that = this;
                this.ui.peditable.editable({
                    type: 'text',
                    mode: 'inline',
                    success: function(response, newValue) {
                        that.model.set({name: newValue});
                        $.notify('New pod name "' + newValue + '" is saved', {
                            autoHideDelay: 5000,
                            clickToHide: true,
                            globalPosition: 'bottom left',
                            className: 'success',
                        });
                    },
                    validate: function(newValue) {
                        var model = App.WorkFlow.getCollection().find(
                            function(item) {
                                return item.get('name') == newValue;
                            }
                        );
                        if (newValue.length > 63){
                            utils.notifyWindow('The maximum length of the Pod name must be less than 63 characters');
                            return ' ';
                        }
                        if (model) {
                            utils.notifyWindow('Pod with name "' + newValue + '" already exists. Try another name.');
                            return ' ';
                        }
                    }
                });
            },

            showPodsList: function(){
                Pods.navigate('pods', {trigger: true});
            }
        });

        NewItem.ImageListItemView = Backbone.Marionette.ItemView.extend({
            template: wizardImageCollectionItemTpl,
            tagName: 'div',
            className: 'item',

            triggers: {
                'click .add-item': 'image:selected'
            },
        });

        NewItem.GetImageView = Backbone.Marionette.CompositeView.extend({
            template: wizardGetImageTpl,
            childView: NewItem.ImageListItemView,
            childViewContainer: '#data-collection',
            tagName: 'div',

            initialize: function(options){
                this.registryURL = options.registryURL;
                this.query = options.query;
            },

            templateHelpers: function(){
                var showPaginator = this.collection.length ? true : false;
                return {
                    showPaginator: showPaginator
                }
            },

            ui: {
                username          : '#username',
                podsList          : '.podsList',
                password          : '#password',
                moreImage         : '.btn-more',
                privateWrapper    : '.private',
                loginPrivateUres  : '.login-user',
                selectImage       : '.select-image',
                imageSource       : '.image-source',
                selectpicker      : '.selectpicker',
                searchImageButton : '.search-image',
                loader            : 'div#load-control',
                searchControl     : 'div.search-control',
                privateField      : '#private-image-field',
                input             : 'input#search-image-field'
            },

            events: {
                'click @ui.selectImage'       : 'selectImage',
                'click @ui.moreImage'         : 'loadNextPage',
                'click @ui.podsList'          : 'showPodsList',
                'click @ui.searchImageButton' : 'onSearchClick',
                'keypress @ui.input'          : 'onInputKeypress',
                'keypress @ui.privateField'   : 'selectImageByEnterKey',
                'keypress @ui.username'       : 'selectImageByEnterKey',
                'keypress @ui.password'       : 'selectImageByEnterKey',
                'change @ui.imageSource'      : 'imageSourceOnChange',
            },

            childEvents: {
                'image:selected' : 'childImageSelected'
            },

            onRender: function(){
                this.ui.selectpicker.selectpicker();
            },

            selectImageByEnterKey: function(evt){
                if (evt.which === 13) {  // 'Enter' key
                    evt.stopPropagation();
                    this.selectImage();
                }
            },

            // image was selected directly by image url
            selectImage: function(){
                var image = this.ui.privateField.val(),
                    auth;

                if (image.length === 0) {
                    this.ui.privateField.focus();
                    utils.notifyWindow('Please, enter image url');
                    return;
                }
                if (this.ui.username.val() && this.ui.password.val()) {
                    auth = {username: this.ui.username.val(),
                            password: this.ui.password.val()};
                }
                this.trigger('image:selected', image, auth);
            },

            imageSourceOnChange: function(){
                var val = this.ui.imageSource.val();
                if (val == "Docker Hub"){
                    this.ui.input.parent().show();
                    this.ui.privateWrapper.hide();
                    this.ui.loginPrivateUres.slideUp();
                    this.ui.searchImageButton.parent().show();
                } else if (val == "Other registries"){
                    this.ui.input.parent().hide();
                    this.ui.privateWrapper.show();
                    this.ui.loginPrivateUres.slideDown();
                    this.ui.searchImageButton.parent().hide();
                    this.ui.privateField.attr('placeholder','[registry/]namespace/image');
                    this.ui.privateField.addClass('private-registry');
                } else {
                    this.ui.input.parent().hide();
                    this.ui.privateWrapper.show();
                    this.ui.loginPrivateUres.slideDown();
                    this.ui.searchImageButton.parent().hide();
                    this.ui.privateField.attr('placeholder','namespace/image');
                    this.ui.privateField.removeClass('private-registry');
                }
            },

            appendLoader: function(control){
                var loader = $('<div class="state load-state" id="image-search-small-loader"></div>');
                loader.append($('<span class="small-loader"></span>'))
                    .append($('<span>Loading...</span>'));
                if (control === undefined) {
                    this.ui.searchControl.empty().append(loader);
                } else {
                    control.empty().append(loader);
                }
            },

            removeLoader: function(){
                $('#image-search-small-loader').remove();
            },

            onInputKeypress: function(evt){
                evt.stopPropagation();
                if (evt.which === 13) { // 'Enter' key
                    if (this.ui.input.val().length !== 0){
                        this.appendLoader();
                        this.trigger('image:searchsubmit', this.ui.input.val().trim());
                    } else {
                        this.ui.input.focus();
                        utils.notifyWindow('First enter image name or part of image name to search');
                    }
                }
            },

            onSearchClick: function(evt){
                evt.stopPropagation();
                if (this.ui.input.val().length !== 0){
                    this.appendLoader();
                    this.trigger('image:searchsubmit', this.ui.input.val().trim());
                } else {
                    this.ui.input.focus();
                    utils.notifyWindow('First enter image name or part of image name to search');
                }
            },

            onShow: function(){
                this.ui.input.focus();
            },

            showPodsList: function(){
                Pods.navigate('pods', {trigger: true});
            },

            childViewOptions: function(){
                var registryURL = this.registryURL;
                return {
                    registryURL: registryURL
                }
            },

            // image was selected from search results
            childImageSelected: function(data){
                this.trigger('image:selected', data.model.get('name'));
            },

            loadNextPage: function(){
                this.appendLoader(this.ui.loader.removeClass('btn-more'));
                this.trigger('image:getnextpage', this.collection, this.query);
            }
        });

        NewItem.WizardPortsSubView = Backbone.Marionette.ItemView.extend({
            tagName: 'div',

            getTemplate: function(){
                return this.model.has('parentID')
                    ? wizardSetContainerSettledBasicSettingsTpl
                    : wizardSetContainerPendingBasicSettingsTpl;
            },
            className: function(){
                return this.model.has('parentID') ? '' : 'container';
            },
            id: function(){
                return this.model.has('parentID') ? 'container-page' : 'add-image';
            },

            ui: {
                containerPort  : '.containerPort .ieditable',
                podPort        : '.hostPort .ieditable',
                mountPath      : '.mountPath.ieditable',
                iseditable     : '.iseditable',
                iveditable     : '.iveditable',
                addPort        : '.add-port',
                addDrive       : '.add-drive',
                nextStep       : '.next-step',
                prevStep       : '.prev-step',
                persistent     : '.persistent',
                addVolume      : '.add-volume',
                removePort     : '.remove-port',
                publicIp       : 'input.public',
                input_command  : 'input.command',
                removeVolume   : '.remove-volume',
                restartPolicy  : '.restart-policy',
                addDriveCancel : '.add-drive-cancel',
                podPorts       : '.hostPort',

                stopContainer  : '#stopContainer',
                startContainer : '#startContainer',
                updateContainer: '.container-update',
                checkForUpdate : '.check-for-update',
            },

            events: {
                'click @ui.prevStep'       : 'goBack',
                'click @ui.nextStep'       : 'goNext',
                'click @ui.addPort'        : 'addItem',
                'click @ui.addDrive'       : 'addDrive',
                'click @ui.addVolume'      : 'addVolume',
                'click @ui.publicIp'       : 'togglePublic',
                'click @ui.addDriveCancel' : 'cancelAddDrive',
                'click @ui.removePort'     : 'removePortEntry',
                'click @ui.persistent'     : 'togglePersistent',
                'click @ui.removeVolume'   : 'removeVolumeEntry',
                'change @ui.restartPolicy' : 'changePolicy',
                'change @ui.input_command' : 'changeCommand',

                'click @ui.stopContainer'  : 'stopContainer',
                'click @ui.startContainer' : 'startContainer',
                'click @ui.updateContainer': 'updateContainer',
                'click @ui.checkForUpdate' : 'checkContainerForUpdate',
            },

            initialize: function(options) {
                this.pod = options.pod;
                var that = this,
                    volumes = this.pod.get('volumes');
                _.each(this.model.get('volumeMounts'), function(vm){
                    if (!vm.name) {
                        vm.name = that.generateName(vm.mountPath);
                    }
                    var item = _.findWhere(volumes, {name: vm.name});
                    if (item === undefined) {
                        volumes.push({name: vm.name, localStorage: true});
                    }
                });

                if (this.model.has('parentID'))
                    this.listenTo(App.WorkFlow.getCollection(), 'pods:collection:fetched', function(){
                        var pod = App.WorkFlow.getCollection().fullCollection.get(
                            this.model.get('parentID'));
                        this.model.set(pod.getContainer(this.model.get('name')).attributes);
                        this.render();
                    });
            },

            triggers: {
                'click .complete'        : 'step:complete',
                'click .go-to-volumes'   : 'step:volconf',
                'click .go-to-envs'      : 'step:envconf',
                'click .go-to-resources' : 'step:resconf',
                'click .go-to-other'     : 'step:otherconf',
                'click .go-to-stats'     : 'step:statsconf',
                'click .go-to-logs'      : 'step:logsconf',
            },

            changePolicy: function(evt){
                evt.stopPropagation();
                this.model.set('restartPolicy', $(evt.target).val())
            },

            changeCommand: function(evt){
                evt.stopPropagation();
                var cmd = $(evt.target).val();
                if (cmd != '') {
                    this.model.set('args', [cmd])
                }
            },

            templateHelpers: function(){
                var model = App.WorkFlow.getCollection().fullCollection.get(this.model.get('parentID')),
                    kubeType;

                if (model !== undefined){
                    kube_id = model.get('kube_type');
                    _.each(kubeTypes, function(kube){
                        if(parseInt(kube.id) == parseInt(kube_id))
                            kubeType = kube;
                    });
                }

                return {
                    updateIsAvailable: this.model.updateIsAvailable,
                    sourceUrl: this.model.get('sourceUrl'),
                    hasPersistent: this.pod.persistentDrives !== undefined,
                    showPersistentAdd: this.hasOwnProperty('showPersistentAdd')
                        ? this.showPersistentAdd
                        : false,
                    ip: this.model.get('ip'),
                    kube_type: kubeType,
                    restart_policy: model !== undefined ? model.get('restartPolicy') : '',
                    podName: model !== undefined ? model.get('name') : '',
                    volumeEntries: this.composeVolumeEntries()
                };
            },

            startContainer: function(){
                App.WorkFlow.commandPod('start', this.model.get('parentID'));
            },
            stopContainer: function(){
                App.WorkFlow.commandPod('stop', this.model.get('parentID'));
            },
            updateContainer: function(){
                App.WorkFlow.updateContainer(this.model);
            },
            checkContainerForUpdate: function(){
                App.WorkFlow.checkContainerForUpdate(this.model).done(this.render);
            },

            addItem: function(evt){
                evt.stopPropagation();
                this.model.get('ports').push({containerPort: null, hostPort: null, protocol: 'tcp', isPublic: false});
                this.render();
            },

            addVolume: function(evt){
                evt.stopPropagation();
                this.model.get('volumeMounts').push({mountPath: null, name: null});
                this.render();
            },

            addDrive: function(evt){
                evt.stopPropagation();
                var tgt = $(evt.target),
                    volumes = this.pod.get('volumes');
                if (this.hasOwnProperty('showPersistentAdd')) {
                    var cells = tgt.closest('div').children('span'),
                        pdName = cells.eq(0).children('input').first().val().trim(),
                        pdSize = parseInt(cells.eq(1).children('input').first().val().trim());
                    if (!pdName || !pdSize) return;
                    if (this.hasOwnProperty('currentIndex')) {
                        var vmEntry = this.model.get('volumeMounts')[this.currentIndex],
                            vol = _.findWhere(volumes, {name: vmEntry.name});
                        this.releasePersistentDisk(vol);
                        vol['persistentDisk'] = {pdName: pdName, pdSize: pdSize};
                    }
                    delete this.showPersistentAdd;
                }
                else {
                    this.currentIndex = tgt.closest('tr').index();
                    var itemName = this.model.get('volumeMounts')[this.currentIndex].name;
                    this.showPersistentAdd = itemName;
                }
                this.render();
            },

            composeVolumeEntries: function(){
                 /* we don't want to add additional fields to volumeMounts
                  * that's why we produce temporary volumeEntries
                  */
                var volumes = this.pod.get('volumes');
                return _.map(this.model.get('volumeMounts'), function(vm){
                    var item = _.findWhere(volumes, {name: vm.name});
                    var rv = {mountPath: vm.mountPath, name: vm.name};
                    if (item === undefined) return _.extend(rv, {isPersistent: false});
                    if ('persistentDisk' in item) {
                        rv['isPersistent'] = true;
                        rv['persistentDisk'] = _.clone(item.persistentDisk);
                    }
                    else {
                        rv['isPersistent'] = false;
                    }
                    return rv;
                });
            },

            cancelAddDrive: function(evt){
                evt.stopPropagation();
                if (this.hasOwnProperty('showPersistentAdd')) {
                    delete this.showPersistentAdd;
                }
                this.render();
            },

            togglePublic: function(evt){
                evt.stopPropagation();
                var index = $(evt.target).closest('tr').index(),
                    entry = this.model.get('ports')[index];
                if (entry.isPublic) {
                    entry.isPublic = false;
                }
                else {
                    entry.isPublic = true;
                }
                this.render();
            },

            generateName: function(path){
                return path.replace(/^\//, '').replace(/\//g, '-')
                    + _.map(_.range(10),
                        function(i){return _.random(1, 10)}).join('');
            },

            togglePersistent: function(evt){
                evt.stopPropagation();
                var tgt = $(evt.target),
                    index = tgt.closest('tr').index(),
                    row = this.model.get('volumeMounts')[index],
                    that = this;

                this.toggleVolumeEntry(row);

                if (this.pod.persistentDrives === undefined) {
                    var pdCollection = new App.Data.PersistentStorageCollection();
                        utils.preloader.show();
                        pdCollection.fetch({
                            wait: true,
                            data: {'free-only': true},
                            success: function(collection, response, opts){
                                that.pod.persistentDrives = _.map(collection.models, function(m){
                                    return that.transformKeys(m.attributes);
                                });
                                utils.preloader.hide();
                                that.render();
                            },
                            error: function(){
                                utils.preloader.hide();
                            }
                        });
                }
                else {
                    this.render();
                }
            },

            toggleVolumeEntry: function(row){
                var vItem = _.findWhere(this.pod.get('volumes'), {name: row.name});
                if (vItem === undefined) return;
                if ('persistentDisk' in vItem) {
                    this.releasePersistentDisk(vItem);
                    delete vItem.persistentDisk;
                    vItem.localStorage = true;
                }
                else if ('localStorage' in vItem) {
                    delete vItem.localStorage;
                    vItem.persistentDisk = {pdName: null, pdSize: null};
                }
            },

            transformKeys: function(obj){
                return _.object(
                    _.map(
                        _.pairs(
                            _.pick(_.clone(obj), 'name', 'size')),
                    function(i){
                        return [
                            'pd'
                                + i[0].charAt(0).toUpperCase()
                                + i[0].slice(1),
                            i[1]
                    ]})
                );
            },

            // if volume uses PD, release it
            releasePersistentDisk: function(volume){
                if (!_.has(volume, 'persistentDisk') ||
                    this.pod.persistentDrives === undefined) return;
                var disk = _.findWhere(this.pod.persistentDrives,
                                       {pdName: volume.persistentDisk.pdName});
                if (disk === undefined) return;
                disk.used = false;
            },

            removePortEntry: function(evt){
                evt.stopPropagation();
                var tgt = $(evt.target),
                    index = tgt.closest('tr').index(),
                    ports = this.model.get('ports');
                ports.splice(index, 1);
                this.render();
            },

            removeVolumeEntry: function(evt){
                evt.stopPropagation();
                var tgt = $(evt.target),
                    index = tgt.closest('tr').index(),
                    volumeMounts = this.model.get('volumeMounts');
                this.pod.deleteVolumes([volumeMounts[index].name]);
                volumeMounts.splice(index, 1);
                this.render();
            },

            goNext: function(evt){
                var that = this,
                    podContainersPorts = [],
                    uniqueContainerPorts = [],
                    podContainersHostPorts = [],
                    uniqueContainerHostPorts = [],
                    volumes = this.pod.get('volumes'),
                    vm = this.model.get('volumeMounts');

                /* mountPath and persistent disk check */
                for (var i=0; i<vm.length; i++) {
                    if (!vm[i].mountPath) {
                        utils.notifyWindow('Container path must be set!');

                        return;
                    }
                    if (!vm[i].name) {
                        var itemName = vm[i].mountPath.charAt(0) === '/'
                            ? vm[i].mountPath.substring(1)
                            : vm[i].mountPath;
                        vm[i].name = itemName.replace(new RegExp('/','g'), '-')
                            + _.map(_.range(10),
                                    function(i){return _.random(1, 10)}).join('');
                    }
                    var vol = _.findWhere(volumes, {name: vm[i].name});
                    if (vol.hasOwnProperty('persistentDisk')) {
                        var pd = vol.persistentDisk;
                        if (!pd.hasOwnProperty('pdSize') ||
                            !pd.hasOwnProperty('pdName') || !pd.pdName) {
                            utils.notifyWindow('Persistent options must be set!');
                            return;
                        }
                    }
                };

                /* check ports */
                _.each(this.pod.get('containers'), function(container){
                    _.each(container.ports, function(item){
                        var port = parseInt(item.containerPort,10),
                            hostPort = parseInt(item.hostPort,10);

                        if (port) podContainersPorts.push(port);
                        if (hostPort) podContainersHostPorts.push(hostPort);
                    })
                })

                uniqueContainerPorts = _.uniq(podContainersPorts);
                uniqueContainerHostPorts = _.uniq(podContainersHostPorts);

                if (podContainersPorts.length != uniqueContainerPorts.length){
                    utils.notifyWindow('You have a duplicate container port in ' + this.model.get('name') + ' container!');
                }
                else if (podContainersHostPorts.length != uniqueContainerHostPorts.length){
                    utils.notifyWindow('You have a duplicate pod port in ' + this.model.get('name') + ' container!');
                }
                else {
                    this.trigger('step:envconf', this);
                }
            },

            goBack: function(evt){
                this.pod.deleteVolumes(
                    _.pluck(this.model.get('volumeMounts'), 'name')
                );
                this.trigger('step:getimage');
            },

            onRender: function(){
                var that = this,
                    disks = [];

                this.ui.input_command.val(this.filterCommand(this.model.get('args')));

                if (this.pod.persistentDrives !== undefined) {
                    disks = _.map(this.pod.persistentDrives, function(i){
                        var item = {value: i.pdName, text: i.pdName};
                        if (i.used) { item.disabled = true; }
                        return item;
                    });
                }

                var validatePort = function(newValue) {
                    newValue = parseInt(newValue);
                    if (isNaN(newValue) || newValue < 1 || newValue > 65535) {
                        utils.notifyWindow('Port must be a number in range 1-65535.');
                        return ' ';  // return string - means validation not passed
                    }
                    return {newValue: newValue};
                };

                this.ui.podPort.editable({
                    type: 'text',
                    mode: 'inline',
                    validate: function(newValue) {
                        if (newValue === '') return;  // host port accepts empty value
                        return validatePort(newValue);
                    },
                    success: function(response, newValue) {
                        var index = $(this).closest('tr').index(),
                            port = that.model.get('ports')[index];
                        port.hostPort = newValue === '' ? null : newValue;
                    }
                });

                this.ui.containerPort.editable({
                    type: 'text',
                    mode: 'inline',
                    validate: validatePort,
                    success: function(response, newValue) {
                        var index = $(this).closest('tr').index();
                        that.model.get('ports')[index].containerPort = newValue;
                    }
                });

                this.ui.mountPath.editable({
                    type: 'text',
                    mode: 'inline',
                    success: function(response, newValue) {
                        var index = $(this).closest('tr').index(),
                            mountEntry = that.model.get('volumeMounts')[index],
                            newName = that.generateName(newValue),
                            volumes = that.pod.get('volumes'),
                            volume = _.findWhere(volumes, {name: mountEntry.name});
                        if (volume !== undefined)
                            volume.name = newName;
                        else
                            volumes.push({name: newName, localStorage: true});
                        mountEntry.mountPath = newValue;
                        mountEntry.name = newName;
                    }
                });

                this.ui.iseditable.editable({
                    type: 'select',
                    value: 'tcp',
                    source: [{value: 'tcp', text: 'tcp'}, {value: 'udp', text: 'udp'}],
                    mode: 'inline',
                    showbuttons: false,
                    success: function(response, newValue) {
                        var index = $(this).closest('tr').index();
                        that.model.get('ports')[index]['protocol'] = newValue;
                    }
                });

                this.ui.iveditable.editable({
                    type: 'select',
                    value: null,
                    source: disks,
                    mode: 'inline',
                    showbuttons: false,
                    success: function(response, newValue) {
                        var index = $(this).closest('tr').index(),
                            entry = that.model.get('volumeMounts')[index],
                            pEntry = _.findWhere(that.pod.persistentDrives, {pdName: newValue}),
                            vol = _.findWhere(that.pod.get('volumes'), {name: entry.name});
                        that.releasePersistentDisk(vol);
                        if (vol) {
                            vol.persistentDisk = _.pick(pEntry, 'pdName', 'pdSize');
                            pEntry.used = true;
                            that.render();
                        }
                    }
                });
            },

            filterCommand: function(command) {
                command = _.map(command, function(e) {
                    return e.indexOf(' ') > 0 ? '"' + e + '"': e;
                });
                return command.join(' ');
            }
        });

        NewItem.WizardEnvSubView = Backbone.Marionette.ItemView.extend({
            template: wizardSetContainerEnvTpl,
            tagName: 'div',

            ui: {
                ieditable  : '.ieditable',
                table      : '#data-table',
                reset      : '.reset-button',
                input      : '.change-input',
                addItem    : '.add-env',
                removeItem : '.remove-env',
                nameField  : 'input.name',
                next       : '.next-step',
                navButtons : '.nav-buttons',

                stopContainer  : '#stopContainer',
                startContainer : '#startContainer',
                updateContainer: '.container-update',
                checkForUpdate : '.check-for-update',
            },

            events: {
                'click @ui.addItem'    : 'addItem',
                'click @ui.removeItem' : 'removeItem',
                'click @ui.reset'      : 'resetFielsdsValue',
                'change @ui.input'     : 'onChangeInput',
                'click @ui.next'       : 'finalStep',
                'focus @ui.nameField'  : 'removeError',

                'click @ui.stopContainer'  : 'stopContainer',
                'click @ui.startContainer' : 'startContainer',
                'click @ui.updateContainer': 'updateContainer',
                'click @ui.checkForUpdate' : 'checkContainerForUpdate',
            },

            triggers: {
                'click .prev-step'       : 'step:volconf',
                'click .go-to-ports'     : 'step:portconf',
                'click .go-to-volumes'   : 'step:volconf',
                'click .go-to-resources' : 'step:resconf',
                'click .go-to-other'     : 'step:otherconf',
                'click .go-to-stats'     : 'step:statsconf',
                'click .go-to-logs'      : 'step:logsconf',
            },

            initialize: function() {
                this.listenTo(App.WorkFlow.getCollection(), 'pods:collection:fetched', function(){
                    var pod = App.WorkFlow.getCollection().fullCollection.get(
                        this.model.get('parentID'));
                    this.model.set(pod.getContainer(this.model.get('name')).attributes);
                    this.render();
                });
            },

            onDomRefresh: function(){
                if (utils.hasScroll()) {
                    this.ui.navButtons.addClass('fixed');
                } else {
                    this.ui.navButtons.removeClass('fixed');
                }
            },

            templateHelpers: function(){
                var kubeType,
                    model = App.WorkFlow.getCollection().fullCollection.get(this.model.get('parentID'));

                if (model !== undefined){
                    kube_id = model.get('kube_type');
                    _.each(kubeTypes, function(kube){
                        if(parseInt(kube.id) == parseInt(kube_id))
                            kubeType = kube;
                    });
                }

                return {
                    updateIsAvailable: this.model.updateIsAvailable,
                    sourceUrl: this.model.get('sourceUrl'),
                    isPending: !this.model.has('parentID'),
                    ip: this.model.get('ip'),
                    kube_type: kubeType,
                    restart_policy: model !== undefined ? model.get('restartPolicy') : '',
                    podName: model !== undefined ? model.get('name') : ''
                };
            },

            startContainer: function(){
                App.WorkFlow.commandPod('start', this.model.get('parentID'));
            },
            stopContainer: function(){
                App.WorkFlow.commandPod('stop', this.model.get('parentID'));
            },
            updateContainer: function(){
                App.WorkFlow.updateContainer(this.model);
            },
            checkContainerForUpdate: function(){
                App.WorkFlow.checkContainerForUpdate(this.model).done(this.render);
            },

            removeError: function(evt){
                var target = $(evt.target);
                if (target.hasClass('error')) target.removeClass('error');
            },

            finalStep: function(){
                var success = true,
                    pattern = /^[a-zA-Z][a-zA-Z0-9-_\.]*$/;

                _.each(this.ui.nameField, function(field){
                    if (!pattern.test(field.value)){
                        $(field).addClass('error');
                        success = false
                    }
                })

                if (this.ui.nameField.hasClass('error')) utils.scrollTo($('input.error').first());

                !success ?
                utils.notifyWindow('First symbol must be letter in variables name') :
                this.trigger('step:complete', this);
            },

            addItem: function(evt){
                evt.stopPropagation();
                var env = this.model.get('env');
                env.push({name: null, value: null});
                this.render();
            },


            removeItem: function(evt){
                var env = this.model.get('env'),
                    item = $(evt.target);
                    index = item.parents('tr').index();
                    item.parents('tr').remove();
                    env.splice(index, 1);

                    this.render();
            },

            resetFielsdsValue: function(){
                this.model.set('env', _.map(this.model.origEnv, _.clone));
                this.render();
            },

            onChangeInput: function(evt){
                var env = this.model.get('env'),
                    tgt = $(evt.target),
                    row = tgt.closest('tr'),
                    index = row.index();
                if (tgt.hasClass('name')) {
                    env[index].name = tgt.val().trim();
                }
                else if (tgt.hasClass('value')) {
                    env[index].value = tgt.val().trim();
                }
            },
        });

        NewItem.WizardStatsSubItemView = Backbone.Marionette.ItemView.extend({
            template: podItemGraphTpl,

            initialize: function(options){ this.container = options.container; },

            ui: {
                chart: '.graph-item'
            },

            onShow: function(){
                var lines = this.model.get('lines'),
                    running = this.container.get('state') === 'running',
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
                    grid: {
                        background: '#ffffff',
                        drawBorder: false,
                        shadow: false
                    },
                    noDataIndicator: {
                        show: true,
                        indicator: !running ? 'Container is not running...' :
                            'Collecting data... plot will be dispayed in a few minutes.',
                        axes: {
                            xaxis: {
                                min: utils.localizeDatetime(new Date(+new Date() - 1000*60*20)),
                                max: utils.localizeDatetime(new Date()),
                                tickOptions: {formatString:'%H:%M'},
                                tickInterval: '5 minutes',
                            },
                            yaxis: {min: 0, max: 150, tickInterval: 50}
                        }
                    },
                };

                var points = [];
                for (var i=0; i<lines; i++) {
                    if (points.length < i+1) {
                        points.push([]);
                    }
                }

                // If there is only one point, jqplot will display ugly plot with
                // weird grid and no line.
                // Remove this point to force jqplot to show noDataIndicator.
                if (this.model.get('points').length == 1)
                    this.model.get('points').splice(0);

                this.model.get('points').forEach(function(record){
                    for (var i=0; i<lines; i++) {
                        points[i].push([
                            utils.localizeDatetime(record[0]),
                            record[i+1]
                        ]);
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

        NewItem.WizardStatsSubView = Backbone.Marionette.CompositeView.extend({
            childView: NewItem.WizardStatsSubItemView,
            childViewContainer: "div.container-stats #monitoring-page",
            template: wizardSetContainerStatsTpl,
            tagName: 'div',

            childViewOptions: function() {
                return {container: this.model};
            },

            initialize: function(options){
                this.listenTo(App.WorkFlow.getCollection(), 'pods:collection:fetched', function(){
                    var pod = App.WorkFlow.getCollection().fullCollection.get(
                        this.model.get('parentID'));
                    this.model.set(pod.getContainer(this.model.get('name')).attributes);
                    this.render();
                });
            },

            events: {
                'click #stopContainer'    : 'stopContainer',
                'click #startContainer'   : 'startContainer',
                'click .container-update' : 'updateContainer',
                'click .check-for-update' : 'checkContainerForUpdate',
            },

            triggers: {
                'click .go-to-ports'     : 'step:portconf',
                'click .go-to-volumes'   : 'step:volconf',
                'click .go-to-envs'      : 'step:envconf',
                'click .go-to-resources' : 'step:resconf',
                'click .go-to-other'     : 'step:otherconf',
                'click .go-to-stats'     : 'step:statsconf',
                'click .go-to-logs'      : 'step:logsconf'
            },

            templateHelpers: function(){
                var parentID = this.model.get('parentID'),
                    pod = App.WorkFlow.getCollection().fullCollection.get(parentID),
                    kubeType;
                if (pod !== undefined){
                    kube_id = pod.get('kube_type');
                    _.each(kubeTypes, function(kube){
                        if(parseInt(kube.id) == parseInt(kube_id))
                            kubeType = kube;
                    });
                }

                return {
                    updateIsAvailable: this.model.updateIsAvailable,
                    parentID: parentID,
                    isPending: !this.model.has('parentID'),
                    image: this.model.get('image'),
                    name: this.model.get('name'),
                    state: this.model.get('state'),
                    kube_type: kubeType,
                    restart_policy: pod !== undefined ? pod.get('restartPolicy') : '',
                    kubes: this.model.get('kubes'),
                    podName: pod !== undefined ? pod.get('name') : '',
                };

            },

            startContainer: function(){
                App.WorkFlow.commandPod('start', this.model.get('parentID'));
            },
            stopContainer: function(){
                App.WorkFlow.commandPod('stop', this.model.get('parentID'));
            },
            updateContainer: function(){
                App.WorkFlow.updateContainer(this.model);
            },
            checkContainerForUpdate: function(){
                App.WorkFlow.checkContainerForUpdate(this.model).done(this.render);
            },
        });

        NewItem.WizardLogsSubView = Backbone.Marionette.ItemView.extend({
            template: wizardSetContainerLogsTpl,
            tagName: 'div',

            ui: {
                ieditable : '.ieditable',
                textarea  : '.container-logs',
                stopItem  : '#stopContainer',
                startItem : '#startContainer',
                updateContainer: '.container-update',
                checkForUpdate : '.check-for-update',
            },

            events: {
                'click @ui.stopItem'  : 'stopItem',
                'click @ui.startItem' : 'startItem',
                'click @ui.updateContainer': 'updateContainer',
                'click @ui.checkForUpdate' : 'checkContainerForUpdate',
            },

            templateHelpers: function(){
                var model = App.WorkFlow.getCollection().fullCollection.get(this.model.get('parentID')),
                    kubeType;
                if (model !== undefined){
                    kube_id = model.get('kube_type');
                    _.each(kubeTypes, function(kube){
                        if(parseInt(kube.id) == parseInt(kube_id))
                            kubeType = kube;
                    });
                }
                return {
                    updateIsAvailable: this.model.updateIsAvailable,
                    sourceUrl: this.model.get('sourceUrl'),
                    isPending: !this.model.has('parentID'),
                    podName: model !== undefined ? model.get('name') : '',
                    kube_type: kubeType,
                    restart_policy: model !== undefined ? model.get('restartPolicy') : '',
                };
            },

            triggers: {
                'click .go-to-ports'     : 'step:portconf',
                'click .go-to-volumes'   : 'step:volconf',
                'click .go-to-envs'      : 'step:envconf',
                'click .go-to-resources' : 'step:resconf',
                'click .go-to-other'     : 'step:otherconf',
                'click .go-to-stats'     : 'step:statsconf'
            },

            initialize: function() {
                _.bindAll(this, 'getLogs');
                this.listenTo(App.WorkFlow.getCollection(), 'pods:collection:fetched', function(){
                    var pod = App.WorkFlow.getCollection().fullCollection.get(
                            this.model.get('parentID'));
                    this.model.set(pod.getContainer(this.model.get('name')).attributes);
                    if (!this.model.has('logs'))
                        this.model.set('logs', []);
                    this.render();
                });

                this.model.set('logs', []);
                this.getLogs();
            },

            getLogs: function() {
                var containerName = this.model.get('name'),
                    size = 100,
                    url = '/api/logs/container/' + containerName +
                          '?size=' + size;
                $.ajax({
                    url: url,
                    dataType : 'json',
                    type: 'GET',
                    context: this,
                    complete: function(){
                        this.model.set('timeout', setTimeout(this.getLogs, 10000));
                    },
                    success: function(data){
                        var seriesByTime = _.indexBy(this.model.get('logs'), 'start');
                        _.each(data.data.reverse(), function(serie) {
                            var lines = serie.hits.reverse(),
                                oldSerie = seriesByTime[serie.start];
                            if (lines.length && oldSerie && oldSerie.hits.length) {
                                // if we have some logs, append only new lines
                                var first = lines[0],
                                    index = _.sortedIndex(oldSerie.hits, first, 'time_nano');
                                lines.unshift.apply(lines, _.first(oldSerie.hits, index));
                            }
                        });
                        this.model.set('logs', data.data);
                        this.render();
                    },
                    error: function(){ utils.notifyWindow('Log not found'); },
                });
            },

            startItem: function(){
                App.WorkFlow.commandPod('start', this.model.get('parentID'));
            },
            stopItem: function(){
                App.WorkFlow.commandPod('stop', this.model.get('parentID'));
            },
            updateContainer: function(){
                App.WorkFlow.updateContainer(this.model);
            },
            checkContainerForUpdate: function(){
                App.WorkFlow.checkContainerForUpdate(this.model).done(this.render);
            },

            onBeforeDestroy: function () {
                clearTimeout(this.model.get('timeout'));
            },

            onBeforeRender: function () {
                // remember scroll position
                var el = this.ui.textarea,
                    jspAPI = el.data ? el.data('jsp') : undefined,
                    logScrollPercent = jspAPI ? jspAPI.getPercentScrolledY() : null;
                if (logScrollPercent < 1)  // if not scrolled to the end, stay
                    this.logScroll = jspAPI ? jspAPI.getContentPositionY() : null;
                else  // otherwise stick to bottom
                    this.logScroll = null;
            },

            onRender: function () {
                this.ui.textarea.jScrollPane();
                var jspAPI = this.ui.textarea.data('jsp');
                if (!jspAPI) return;
                if (this.logScroll === null)
                    jspAPI.scrollToPercentY(1);  // stick to bottom
                else
                    jspAPI.scrollToY(this.logScroll);  // stay at the same position
            },
        });

        NewItem.WizardCompleteSubView = Backbone.Marionette.ItemView.extend({
            template: wizardSetContainerCompleteTpl,
            tagName: 'div',

            initialize: function(){
                this.package = this.getUserPackage();
                // kubeTypes is taken from index.html
                var default_kube = _.findWhere(kubeTypes, {is_default: true});
                if (default_kube === undefined) {
                    default_kube = kubeTypes[0];
                }
                if(!this.model.has('kube_type')){
                    this.model.attributes['kube_type'] = default_kube.id;
                }
                this.recalcTotal();
            },

            templateHelpers: function() {

                return {
                    last_edited      : this.model.last_edited_container,
                    isPublic         : this.isPublic,
                    isPerSorage      : this.isPerSorage,
                    cpu_data         : this.cpu_data,
                    ram_data         : this.ram_data,
                    hdd_data         : this.hdd_data,
                    containerPrices  : this.containerPrices,
                    total_price      : this.total_price,
                    kube_types       : kubeTypes,
                    restart_policies : {'Always': 'Always', 'Never': 'Never', 'OnFailure': 'On Failure'},
                    restart_policy   : this.model.get('restartPolicy'),
                    image_name_id    : this.model.get('lastAddedImageNameId'),
                    package          : this.package,
                    price_ip         : this.getFormattedPrice(this.package.price_ip),
                    price_pstorage   : this.getFormattedPrice(this.package.price_pstorage)
                };
            },

            ui: {
                'ieditable'               : '.ieditable',
                'policy'                  : 'select.restart-policy',
                'kubeTypes'               : 'select.kube_type',
                'kubeQuantity'            : 'select.kube-quantity',
                'editPolicy'              : '.edit-policy',
                'editPolycyDescription'   : '.edit-polycy-description',
                'editKubeType'            : '.edit-kube-type',
                'editKubeTypeDescription' : '.edit-kube-type-description',
                'main'                    : '#add-image',
                'selectpicker'            : '.selectpicker',
            },

            events: {
                'click .prev-step'       : 'goBack',
                'click .delete-item'     : 'deleteItem',
                'click .edit-item'       : 'editItem',
                'click .add-more'        : 'addItem',
                'click .node'            : 'toggleNode',
                'change .replicas'       : 'changeReplicas',
                'change @ui.kubeTypes'   : 'changeKubeType',
                'change .kube-quantity'  : 'changeKubeQuantity',
                'change @ui.policy'      : 'changePolicy',
                'click @ui.editPolicy'   : 'editPolicy',
                'click @ui.editKubeType' : 'editKubeType',
            },

            triggers: {
                'click .save-container'     : 'pod:save',
                'click .save-run-container' : 'pod:run',
            },

            deleteItem: function(evt){
                evt.stopPropagation();
                var name = $(evt.target).closest('tr').children('td:first').attr('id');
                if (this.model.get('containers').length >= 2) {
                    this.model.deleteContainer(name);
                    if (name == this.model.last_edited_container) {
                        this.model.last_edited_container = _.last(this.model.get('containers')).name;
                    }
                    this.recalcTotal();
                    this.render();
                } else {
                    utils.modalDialogDelete({
                        title: "Delete",
                        body: "After deleting the last container, you will go " +
                              "back to the main page. Delete this container?",
                        small: true,
                        show: true,
                        footer: {
                            buttonOk: function(){
                                Pods.navigate('pods', {trigger: true});
                            },
                            buttonCancel: true
                        }
                    });
                }
            },

            editItem: function(evt){
                evt.stopPropagation();
                var tgt = evt.target,
                    name = $(tgt).closest('tr').children('td:first').attr('id');
                this.model.last_edited_container = name;
                this.trigger('step:portconf', name);
            },

            addItem: function(evt){
                evt.stopPropagation();
                this.model.last_edited_container = null;
                this.trigger('step:getimage');
            },

            // edit env vars of the last edited container
            goBack: function(evt){
                evt.stopPropagation();
                this.trigger('step:envconf', this.model.last_edited_container);
            },

            toggleNode: function(evt){
                evt.stopPropagation();
                var tgt = $(evt.target),
                    node = tgt.closest('td').next('td').text().trim();
                this.model.set('node', node);
                this.render();
            },

            changeReplicas: function(evt){
                evt.stopPropagation();
                this.model.set('replicas', parseInt($(evt.target).val().trim()));
            },

            changeKubeQuantity: function(evt){
                evt.stopPropagation();
                var num = parseInt(evt.target.value);
                this.getCurrentContainer().kubes = num;

                this.recalcTotal();
                this.render();
                $('.kube-quantity button span').text(num);
            },

            changeKubeType: function(evt){
                evt.stopPropagation();
                var kube_id = parseInt(evt.target.value);
                this.model.set('kube_type', kube_id);

                this.recalcTotal();
                this.render();
            },

            changePolicy: function(evt){
                evt.stopPropagation();
                var restart_policy = $(evt.target).val();
                this.model.set('restartPolicy', restart_policy)
            },

            getKubePrice: function(kubeId) {
                var packageKube = _.find(packageKubes, function(p) {
                    return p.package_id === this.pid && p.kube_id === kubeId;
                }, {pid: this.package.id});
                return packageKube ? packageKube.kube_price : 0;
            },

            getUserPackage: function() {
                return _.find(packages, function(p) {  // 'packages' && 'userPackage' is taken from index.html
                    return p.id === userPackage
                })
            },

            getFormattedPrice: function(price, format) {
                format = typeof format !== 'undefined' ? format : '0.00';
                return this.package.prefix + numeral(price).format(format) + this.package.suffix;
            },

            recalcTotal: function() {
                var kube_id = this.model.get('kube_type'),
                    containers = this.model.get('containers'),
                    volumes = this.model.get('volumes'),
                    kube = _.findWhere(kubeTypes, {id: kube_id}),
                    kube_price = this.getKubePrice(kube_id),
                    total_kubes = _.reduce(containers,
                        function (sum, c) { return sum + c.kubes; }, 0);

                this.cpu_data = total_kubes * kube.cpu + ' ' + kube.cpu_units;
                this.ram_data = total_kubes * kube.memory + ' ' + kube.memory_units;
                this.hdd_data = total_kubes * kube.disk_space + ' ' + kube.disk_space_units;

                var allPorts = _.flatten(_.pluck(containers, 'ports'), true),
                    allPersistentVolumes = _.filter(_.pluck(volumes, 'persistentDisk')),
                    total_size = _.reduce(allPersistentVolumes,
                        function(sum, v) { return sum + v.pdSize; }, 0);
                this.isPublic = _.some(_.pluck(allPorts, 'isPublic'));
                this.isPerSorage = !!allPersistentVolumes.length;

                var rawContainerPrices = _.map(containers,
                    function(c) { return kube_price * c.kubes; });
                this.containerPrices = _.map(rawContainerPrices,
                    function(price) { return this.getFormattedPrice(price); }, this);

                var total_price = _.reduce(rawContainerPrices,
                    function(sum, p) { return sum + p; });
                if (this.isPublic)
                    total_price += this.package.price_ip
                if (this.isPerSorage)
                    total_price += this.package.price_pstorage * total_size
                this.total_price = this.getFormattedPrice(total_price)
            },

            getCurrentContainer: function() {
                var containers = this.model.get('containers'),
                    last_edited = _.findWhere(containers, {name: this.model.last_edited_container});
                return last_edited || _.last(containers);
            },

            onRender: function() {
                this.ui.selectpicker.selectpicker();
                this.ui.kubeQuantity.selectpicker('val', this.getCurrentContainer().kubes);
                this.ui.kubeTypes.selectpicker('val', this.model.get('kube_type'));
            },

            editPolicy: function(){
                this.ui.editPolicy.hide();
                this.ui.editPolycyDescription.hide()
                this.ui.policy.attr('disabled',false);
                this.$('.policy .disabled').removeClass('disabled');
            },

            editKubeType: function(){
                this.ui.editKubeType.hide();
                this.ui.editKubeTypeDescription.hide()
                this.ui.kubeTypes.attr('disabled',false);
                this.$('.kube-type-wrapper .disabled').removeClass('disabled');
            },
        });

    });

    return Pods.Views.NewItem;
});
