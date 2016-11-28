import App from 'isv/app';
// import Model from 'isv/model';
import * as utils from 'app_data/utils';

import {Details as AppDetailsView,
        Conf as AppConfView,
        } from 'isv/application/views';
import {Topbar, Sidebar} from 'isv/misc/views';

const controller = {
    doLogin(options){
        console.log('not authorized');
        // TODO: redirect to WHMCS -> login -> redirect back with SSO?
    },

    showApplicationView(view){
        App.rootLayout.contents.show(view);
        if (!App.rootLayout.topbar.hasView())
            App.rootLayout.topbar.show(new Topbar({model: view.model}));
        if (!App.rootLayout.sidebar.hasView())
            App.rootLayout.sidebar.show(new Sidebar());
    },

    appDetails(){
        utils.preloader2.show();
        App.getPodCollection().then(podCollection => {
            const pod = podCollection.at(0);
            if (!pod){
                utils.notifyWindow('Application not found');
                // TODO: redirect to "order app" page
                return;
            }
            let detailsView = new AppDetailsView({model: pod});
            this.showApplicationView(detailsView);
            utils.preloader2.hide();
        });
    },

    appConf(){
        utils.preloader2.show();
        App.getPodCollection().done(podCollection => {
            const pod = podCollection.at(0);
            if (!pod){
                utils.notifyWindow('Application not found');
                return;
            }
            let confView = new AppConfView({model: pod});
            this.showApplicationView(confView);
            utils.preloader2.hide();
        });
    },

    appBackups(){
        console.log('show appBackups');
        App.rootLayout.contents.empty();
    },
};

export default Marionette.Object.extend(controller);
