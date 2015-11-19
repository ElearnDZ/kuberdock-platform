<div id="container-page">
    <div class="breadcrumbs-wrapper">
        <div class="container breadcrumbs" id="breadcrumbs">
            <ul class="breadcrumb">
                <li>
                    <a href="/#pods">Pods</a>
                </li>
                <li>
                    <a href="/#pods/<%- parentID %>"><%- podName %></a>
                </li>
                <li class="active"><%- image %> (<%- name %>)</li>
            </ul>
        </div>
    </div>
    <div class="container">
        <div class="row">
            <div class="col-sm-3 col-md-2 sidebar">
                <ul class="nav nav-sidebar">
                    <li role="presentation" class="stats active">Logs</li>
                    <li role="presentation" class="go-to-stats">Monitoring</li>
                    <!-- <li role="presentation" class="go-to-volumes ">Timelines</li> -->
                    <li role="presentation" class="go-to-ports configuration">General</li>
                    <li role="presentation" class="go-to-envs">Variables</li>
                    <!-- <li role="presentation" class="go-to-resources">Limits</li> -->
<!--                     <li role="presentation" class="configuration">
                        <span class="go-to-ports">Configuration</span>
                        <ul class="nav sub-nav">
                        </ul>
                    </li> -->
                </ul>
            </div>
            <div id="details_content" class="col-xs-10 logs-tab no-padding">
                <div id="tab-content">
                    <div class="status-line <%- state %> curent-margin">Status: <%- state %>
                        <% if (state == "running"){ %>
                            <span id="stopContainer">Stop</span>
                            <!-- AC-1279 -->
                            <% if (!updateIsAvailable) { %>
                                <span class="check-for-update" title="Check <%- image %> for updates">Check for updates</span>
                            <% } else { %>
                                <span class="container-update" title="Update <%- image %> container">Update</span>
                            <% } %>
                        <% } else  if (state == "stopped"){ %>
                            <span id="startContainer">Start</span>
                        <% } %>
                        <!-- <span>Terminate</span> -->
                        <!-- <span>Redeploy</span> -->
                        <% if (sourceUrl !== undefined) { %>
                            <a class="pull-right image-link" href="<%- /^https?:\/\//.test(sourceUrl) ? sourceUrl : 'http://' + sourceUrl %>" target="blank">Learn more about this image</a>
                        <% } %>
                    </div>
                    <div class="col-xs-10">
                        <div class="info col-xs-6">
                            <div>Image: <%- image %></div>
                            <div>Kube type: <%- kube_type.name %></div>
                            <div>Restart policy: <%- restart_policy %></div>
                            <div>Kubes: <span <!--class="editContainerKubes"-->><%- kubes %></span>
                            </div>
                        </div>
                        <div class="col-xs-6 servers">
                            <div>CPU: <%- kube_type.cpu * kubes %> <%- kube_type.cpu_units %></div>
                            <div>RAM: <%- kube_type.memory * kubes %> <%- kube_type.memory_units %></div>
                            <div>HDD: <%- kube_type.disk_space * kubes %> <%- kube_type.disk_space_units %> </div>
                        </div>
                    </div>
                    <div class="col-xs-12 no-padding container-logs-wrapper">
                        <div class="container-logs">
                            <% if (!logs.length) { %>
                                <p>Nothing to show because containers log is empty.</p>
                            <% } else { %>
                                <% _.each(logs, function(serie){ %>

                                <p class="container-logs-started"><%- new Date(serie.start).toISOString() %>: Started</p>
                                <% _.each(serie.hits, function(line){ %>
                                    <p><%- new Date(line['@timestamp']).toISOString() %>: <%- line.log %></p>
                                <% }) %>
                                <% if (serie.end) { %>
                                    <p class="container-logs-<%- serie.exit_code ? 'failed' : 'succeeded' %>"><%- new Date(serie.end).toISOString() %>: <%- serie.exit_code ? 'Falied' : 'Exited successfully' %></p>
                                    <p class="container-logs-<%- serie.exit_code ? 'failed' : 'succeeded' %>-reason"><%- serie.reason %></p>
                                <% } %>

                                <% }) %>
                            <% } %>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>