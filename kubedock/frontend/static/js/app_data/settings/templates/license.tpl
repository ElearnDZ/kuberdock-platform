<div id="item-controls" class="licenseTab">
    <div class="status-line">
        <span class="icon <%= status %>"><span>License status: <%= status ? status : 'unknown'%></span></span>
        <span class="award"><span>License type:
            <% if (type){ %>
                <%= type %>
            <% } else { %>
                unknown
            <% }%></span>
        </span>
    </div>
    <div class="row">
        <div class="col-md-10 col-md-offset-1 control-icons">
            <div class="col-md-6 col-sm-12 info">
                <div class="editGroup">
                    <b>Installation ID:</b> <span class="edit-field peditable"> <%= installationID %></span>
                </div>
                <div><b>Platform:</b> <%= platform %></div>
                <div><b>Storage:</b> <%= storage %></div>
            </div>
            <div class="col-md-6 col-sm-12 servers">
                <div><b>KuberDock version:</b> <%= version.KuberDock %></div>
                <div><b>Kubernetes version:</b> <%= version.kubernetes %></div>
                <% if (version.docker !== 'unknown'){ %>
                    <div><b>Docker version:</b> <%= version.docker %></div>
                <% } %>
                <div><b>Support:</b> <a href="mailto:helpdesk@kuberdock.com">helpdesk@kuberdock.com</a></div>
            </div>
        </div>
    </div>
</div>
<div id="item-info">
    <table id="license-table" class="table">
        <thead>
            <tr>
                <th><b>License Usage</b></th>
                <th>Nodes</th>
                <th>Cores</th>
                <th>Memory (GB)</th>
                <th>Containers</th>
                <th>Users pods</th>
                <th>Predefined apps</th>
                <th>Persistent volume (GB)</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><b>License limits</b></td>
                <td><%= data.nodes[0] %></td>
                <td><%= data.cores[0] %></td>
                <td><%= data.memory[0] %></td>
                <td><%= data.containers[0] %></td>
                <td><%= data.pods[0] %></td>
                <td><%= data.apps[0] %></td>
                <td><%= data.persistentVolume[0] %></td>
                <td></td>
            </tr>
            <tr <%= attention ? 'class="attention"' : '' %>>
                <td><b>Current state</b></td>
                <% if(data.nodes[3]) {%>
                    <td class="critical">
                        <span class="warning-info-title-ico" data-toggle="tooltip" data-placement="right" title="The number of this nodes is under limit">
                            <span><%= data.nodes[1] %></span>
                        </span>
                    </td>
                <% } else { %>
                    <td><%= data.nodes[1] %></td>
                <% } %>
                <% if(data.cores[3]) {%>
                    <td class="critical">
                        <span class="warning-info-title-ico" data-toggle="tooltip" data-placement="right" title="The number of this cores is under limit">
                            <span><%= data.cores[1] %></span>
                        </span>
                    </td>
                <% } else { %>
                    <td><%= data.cores[1] %></td>
                <% } %>
                <% if(data.memory[3]) {%>
                    <td class="critical">
                        <span class="warning-info-title-ico" data-toggle="tooltip" data-placement="left" title="The size of this memory is under limit">
                            <span><%= data.memory[1] %></span>
                        </span>
                    </td>
                <% } else { %>
                    <td><%= data.memory[1] %></td>
                <% } %>
                <% if(data.containers[3]) {%>
                    <td class="critical">
                        <span class="warning-info-title-ico" data-toggle="tooltip" data-placement="left" title="The number of this containers is under limit">
                            <span><%= data.containers[1] %></span>
                        </span>
                    </td>
                <% } else { %>
                    <td><%= data.containers[1] %></td>
                <% } %>
                <% if(data.pods[3]) {%>
                    <td class="critical">
                        <span class="warning-info-title-ico" data-toggle="tooltip" data-placement="left" title="The number of this users pods is under limit">
                            <span><%= data.pods[1] %></span>
                        </span>
                    </td>
                <% } else { %>
                    <td><%= data.pods[1] %></td>
                <% } %>
                <% if(data.apps[3]) {%>
                    <td class="critical">
                        <span class="warning-info-title-ico" data-toggle="tooltip" data-placement="left" title="The number of this apps is under limit">
                            <span><%= data.apps[1] %></span>
                        </span>
                    </td>
                <% } else { %>
                    <td><%= data.apps[1] %></td>
                <% } %>
                <% if(data.persistentVolume[3]) {%>
                    <td class="critical">
                        <span class="warning-info-title-ico" data-toggle="tooltip" data-placement="left" title="The size of this persistent volumes is under limit">    <span><%= data.persistentVolume[1] %></span>
                        </span>
                    </td>
                <% } else { %>
                    <td><%= data.persistentVolume[1] %></td>
                <% } %>
                <td class="font-fix">
                    <span class="check-for-update" title="Update status"></span>
                </td>
            </tr>
        </tbody>
    </table>
</div>
