import requests
import requests_cache
# requests_cache.install_cache()   # RM because it makes session stuff fail...

from ricecooker.config import LOGGER


STUDIO_URL = 'https://studio.learningequality.org'

STUDIO_URL = 'http://127.0.0.1:8080'

LOGIN_ENDPOINT =         STUDIO_URL + '/accounts/login/'
NODES_ENDPOINT =         STUDIO_URL + '/api/get_nodes_by_ids_complete/'
LICENSES_LIST_ENDPOINT = STUDIO_URL + '/api/license'
CHANNEL_ENDPOINT =       STUDIO_URL + '/api/channel/'
CONTENTNODE_ENDPOINT =   STUDIO_URL + '/api/contentnode'
MOVE_NODES_ENDPOINT =    STUDIO_URL + '/api/move_nodes/'
# TODO https://studio.learningequality.org/api/get_node_path/ca8f380/18932/41b2549
# TODO https://studio.learningequality.org/api/language
# TODO `api/get_total_size/(?P<ids>[^/]*)` where ids are split by commas or run this script:


class StudioApi(object):
    """
    Helper class whose methods allow access to Studo API endpoints for debugging.
    """

    def __init__(self, token, username=None, password=None, studio_url=STUDIO_URL):
        self.token = token
        self.licenses_by_id = self.get_licenses()
        if username and password:
            self.session = self._create_logged_in_session(username, password)
        else:
            self.session = None

    def _create_logged_in_session(self, username, password):
        session = requests.session()
        session.headers.update({"referer": STUDIO_URL})
        session.headers.update({'User-Agent': 'Mozilla/5.0 Firefox/63.0'})
        session.get(LOGIN_ENDPOINT)
        csrftoken = session.cookies.get("csrftoken")
        session.headers.update({"csrftoken": csrftoken})
        session.headers.update({"referer": LOGIN_ENDPOINT})
        post_data = {
            "csrfmiddlewaretoken": csrftoken,
            "username": username,
            "password": password
        }
        response2 = session.post(LOGIN_ENDPOINT, data=post_data)
        assert response2.status_code == 200, 'Login POST failed'
        return session


    def get_channel(self, channel_id):
        """
        Calls the /api/channel/{{channel_id}} endpoint to get the channel info.
        Returns a dictionary of useful information like:
          - `name` and `description`
          - `main_tree` {"id": studio_id} where `studio_id` is the root of the channel's main tree
          - `staging_tree`: {"id": studio_id} for the root of the staging tree
          - `trash_tree`: tree where deleted nodes go
          - `ricecooker_version`: string that indicates what version of riccooker
             created this channel. If `Null` this means it's a manually uploaded
             channel or a derivative channel
        """
        # TODO: add TokenAuth to this entpoint so can use without session login
        # headers = {"Authorization": "Token {0}".format(self.token)}
        url = CHANNEL_ENDPOINT + channel_id
        LOGGER.info('  GET ' + url)
        response = self.session.get(url)
        channel_data = response.json()
        return channel_data

    def get_channel_root_studio_id(self, channel_id, tree='main'):
        """
        Return the `studio_id` for the root of the tree `tree` for `channel_id`.
        """
        channel_data = self.get_channel(channel_id)
        tree_key = tree + '_tree'
        tree_data = channel_data[tree_key]
        return tree_data['id']


    def get_licenses(self):
        headers = {"Authorization": "Token {0}".format(self.token)}
        response = requests.get(LICENSES_LIST_ENDPOINT, headers=headers)
        licenses_list = response.json()
        licenses_dict = {}
        for license in licenses_list:
            licenses_dict[license['id']] = license
        return licenses_dict


    def get_nodes_by_ids_complete(self, studio_id):
        """
        Get the complete JSON representation of a content node from the Studio API.
        """
        headers = {"Authorization": "Token {0}".format(self.token)}
        url = NODES_ENDPOINT + studio_id
        LOGGER.info('  GET ' + url)
        response = requests.get(url, headers=headers)
        studio_node = response.json()[0]
        return studio_node


    def get_tree_for_studio_id(self, studio_id):
        """
        Returns the full json tree (recusive calls to /api/get_nodes_by_ids_complete)
        """
        channel_parent = {'children': []}  # this is like _ with children
        def _build_subtree(parent, studio_id):
            subtree = self.get_nodes_by_ids_complete(studio_id)
            if 'children' in subtree:
                children_refs = subtree['children']
                subtree['children'] = []
                for child_studio_id in children_refs:
                    _build_subtree(subtree, child_studio_id)
            parent['children'].append(subtree)
        _build_subtree(channel_parent, studio_id)
        channel = channel_parent['children'][0]
        return channel



    def get_contentnode(self, studio_id):
        """
        Return the `studio_id` for the root of the tree `tree` for `channel_id`.
        """
        return self.get_nodes_by_ids_complete(studio_id)

    def put_contentnode(self, data):
        """
        Send a PUT requests to /api/contentnode to update Studio node to data.
        """
        REQUIRED_FIELDS = ['id', 'tags', 'prerequisite', 'parent']
        assert data_has_required_keys(data, REQUIRED_FIELDS), 'missing necessary attributes'        
        studio_id = data['id']
        url = CONTENTNODE_ENDPOINT
        print('  semantic PATCH using PUT ' + url)
        csrftoken = self.session.cookies.get("csrftoken")
        self.session.headers.update({"x-csrftoken": csrftoken})
        response = self.session.put(url, json=[data])
        node_data = response.json()
        return node_data

    def delete_contentnode(self, data, channel_id, trash_studio_id=None):
        """
        Send a POST requests to /api/move_nodes/ to delete Studio node spcified
        in `data` in the channel specified in `channel_id`. For efficiency, you
        can provide `trash_studio_id` which is the studio id the trash tree for
        the channel.
        """
        REQUIRED_FIELDS = ['id']
        assert data_has_required_keys(data, REQUIRED_FIELDS), 'missing necessary attributes'
        if trash_studio_id is None:
            channel_data = self.get_channel(channel_id)
            trash_studio_id = channel_data['trash_tree']['id']
        post_data = {
            'nodes': [data],
            'target_parent': trash_studio_id,
            'channel_id': channel_id,
        }
        url = MOVE_NODES_ENDPOINT
        print('  semantic DELETE using POST to ' + url)
        csrftoken = self.session.cookies.get("csrftoken")
        self.session.headers.update({"x-csrftoken": csrftoken})
        response = self.session.post(url, json=post_data)
        deleted_data = response.json()
        return deleted_data




def data_has_required_keys(data, required_keys):
    verdict = True
    for key in required_keys:
        if key not in data:
            verdict = False
    return verdict







