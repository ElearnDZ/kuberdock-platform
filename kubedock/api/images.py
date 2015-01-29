import json
from flask import Blueprint, request, current_app, jsonify
from .. import tasks
from ..core import db
from ..models import ImageCache, DockerfileCache
import datetime

images = Blueprint('images', __name__, url_prefix='/images')

def process(data):
    data = data.strip();
    pos = data.find(' ')
    if pos <= 0:
        return []
    return map((lambda x: x.strip('\'"[] ')), data[pos:].split(','))

def parse(data):
    ready = {'command': [], 'workingDir': [], 'ports': [], 'volumeMounts': []}
    for line in data.splitlines():
        if line.startswith('CMD'):
            ready['command'].extend(process(line))
        elif line.startswith('WORKDIR'):
            ready['workingDir'].extend(process(line))
        elif line.startswith('VOLUME'):
            ready['volumeMounts'].extend(process(line))
        elif line.startswith('EXPOSE'):
            ready['ports'].extend(process(line))
    return ready

@images.route('/', methods=['GET'])
def get_list_by_keyword():
    search_key = request.args.get('searchkey', 'none')
    query = db.session.query(ImageCache).get(search_key)
    if query is not None:
        if (datetime.datetime.now() - query.time_stamp).seconds < 86400:    # 1 day
            return jsonify({'status': 'OK', 'data': query.data})
    result = tasks.get_container_images.delay(search_key)
    rv = result.wait()
    data = json.loads(rv)['results']
    if query is None:
        db.session.add(ImageCache(query=search_key, data=data, time_stamp=datetime.datetime.now()))
    else:
        query.data = data
        query.time_stamp = datetime.datetime.now()
    db.session.commit()
    return jsonify({'status': 'OK', 'data': data})

@images.route('/new', methods=['POST'])
def get_dockerfile_data():
    image = request.form.get('image', 'none')
    query = db.session.query(DockerfileCache).get(image)
    current_app.logger.debug(query)
    if query is not None:
        if (datetime.datetime.now() - query.time_stamp).seconds < 86400:    # 1 day
            return jsonify({'status': 'OK', 'data': query.data})
    result = tasks.get_dockerfile.delay(image)
    rv = result.wait()

    out = parse(rv)
    out['image'] = image
    current_app.logger.debug(out)
    if query is None:
        db.session.add(DockerfileCache(image=image, data=out, time_stamp=datetime.datetime.now()))
    else:
        query.data = out
        query.time_stamp = datetime.datetime.now()
    db.session.commit()
    return jsonify({'status': 'OK', 'data': out})