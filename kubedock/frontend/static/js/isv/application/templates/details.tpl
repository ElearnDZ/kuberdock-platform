<div class="row">
    <h2 class="col-sm-12">Credentials</h2>
    <div class="hidden-xs col-sm-2 isv-block text-center storage"></div>
    <div class="col-xs-12 col-sm-10 isv-block">
        <p>Domain name: <a href="http://<%- domain %>"><%- domain %></a></p>
        <p>Admin username: Admin</p>
        <p>Admin password: ***** <span class="copy-password" data-toggle="tooltip" data-placement="top" data-original-title="Copy admin password to clipboard"></span></p>
        <a href="#">Reset password</a>
    </div>
</div>
<div class="row">
    <h2 class="col-sm-12">Details</h2>
    <div class="hidden-xs col-sm-2 isv-block text-center layers"></div>
    <div class="col-xs-12 col-sm-4 isv-block">
        <p>Current package: <%- template_plan_name %></p>
        <p>Price: $29.95/month</p>
        <p>Due date: TODO</p>
    </div>
    <div class="hidden-xs col-sm-2 isv-block text-center info-outline"></div>
    <div class="col-xs-12 col-sm-4 isv-block">
        <p>Status: <span class="statuses <%- status %>"><%- status %></span></p>
        <p>Version: <%- template_version_id || 'Not set'%></p>
        <p>Last update: <%- appLastUpdate %></p>
    </div>
</div>
