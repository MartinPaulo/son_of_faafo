#!/usr/bin/env python

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import argparse
import json
import logging

import flask
from flask.ext.sqlalchemy import SQLAlchemy


def initialize_logging(filename):
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO,
                        filename=filename)


def parse_command_line_arguments():
    """Parse the command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url", type=str, help="database connection URL",
        default="sqlite:////tmp/oat.db")
    parser.add_argument(
        "--log-file", type=str, help="write logs to this file", default=None)
    parser.add_argument(
        "--daemonize", action="store_true", help="run in background")
    return parser.parse_args()


app = flask.Flask(__name__)
args = parse_command_line_arguments()
initialize_logging(args.log_file)
app.config['SQLALCHEMY_DATABASE_URI'] = args.database_url
db = SQLAlchemy(app)


class Fractal(db.Model):
    __tablename__ = 'fractals'

    fractal_id = db.Column(db.String(36), primary_key=True)
    data = db.Column(db.Text())

    def __repr__(self):
        return "<Fractal(uuid='%s')>" % self.uuid


@app.route("/")
def index():
    return flask.jsonify({})


def get_fractal_from_database(fractal_id):
    try:
        return Fractal.query.get(fractal_id)
    except Exception:
        return None


def write_fractal_to_database(fractal_id, data):
    fractal = Fractal(
        fractal_id=fractal_id,
        data=json.dumps(data)
    )
    db.session.add(fractal)
    db.session.commit()


@app.route('/v1/fractals/<string:fractal_id>/result', methods=['POST'])
def publish_result(fractal_id):
    if (not flask.request.json or
        not flask.request.json.viewkeys() & {
            'duration', 'checksum'}):
        logging.error("wrong request: %s" % flask.request.json)
        flask.abort(400)

    fractal = get_fractal_from_database(fractal_id)

    if not fractal:
        flask.abort(400)

    data = json.loads(fractal.data)
    data['checksum'] = str(flask.request.json['checksum'])
    data['duration'] = float(flask.request.json['duration'])
    fractal.data = json.dumps(data)
    db.session.commit()
    data['uuid'] = fractal_id
    return flask.jsonify(data), 201


@app.route('/v1/fractals', methods=['POST'])
def create_fractal():
    if (not flask.request.json or
        not flask.request.json.viewkeys() >= {
            'uuid', 'parameter', 'dimension'} or
        not flask.request.json['parameter'].viewkeys() >= {
            'xa', 'xb', 'ya', 'yb', 'iterations'} or
        not flask.request.json['dimension'].viewkeys() >= {
            'width', 'height'}):
        logging.error("wrong request: %s" % flask.request.json)
        flask.abort(400)

    try:
        fractal_id = str(flask.request.json['uuid'])
        xa = float(flask.request.json['parameter']['xa'])
        xb = float(flask.request.json['parameter']['xb'])
        ya = float(flask.request.json['parameter']['ya'])
        yb = float(flask.request.json['parameter']['yb'])
        iterations = int(flask.request.json['parameter']['iterations'])
        width = int(flask.request.json['dimension']['width'])
        height = int(flask.request.json['dimension']['height'])
        fractal = {
            'checksum': '',
            'duration': 0.0,
            'parameter': {
                'xa': xa,
                'xb': xb,
                'ya': ya,
                'yb': yb,
                'iterations': iterations
            },
            'dimension': {
                'width': width,
                'height': height
            }
        }
    except Exception:
        flask.abort(400)

    write_fractal_to_database(fractal_id, fractal)

    fractal['uuid'] = fractal_id

    return flask.jsonify(fractal), 201


@app.errorhandler(404)
def not_found(error):
    return flask.make_response(flask.jsonify({'error': 'Not found'}), 404)


def main():
    db.create_all()
    app.run(host="0.0.0.0", debug=True)


if __name__ == "__main__":
    main()