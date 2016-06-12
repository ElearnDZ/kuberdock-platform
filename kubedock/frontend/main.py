from flask import (Blueprint, request, render_template, make_response,
                   session, redirect, url_for)
from ..sessions import create_token


main = Blueprint('main', __name__)


# TODO: remove in the next release
@main.route('/login', methods=['GET', 'POST'])
def login():
    return redirect(url_for('main.index'))


@main.route('/', methods=['GET'])
def index():
    token = request.args.get('token2')
    if token is not None:
        token = create_token(session)
        resp = make_response(render_template('index.html', token=token))
        if 'X-Auth-Token' not in resp.headers:
            resp.headers['X-Auth-Token'] = token
        return resp
    return render_template('index.html', token=None)


#@main.route('/test', methods=['GET'])
#def run_tests():
#    if TEST:
#        return render_template('t/pod_index.html')
#    return "not found", 404
