import docker
import logging
import os
import shutil
import subprocess
import sys

from pathlib import Path
from secrets import token_hex

from illumidesk.apis.jupyterhub_api import JupyterHubAPI
from illumidesk.apis.nbgrader_service import NbGraderServiceHelper

from .constants import NBGRADER_COURSE_CONFIG_TEMPLATE
from .constants import NBGRADER_HOME_CONFIG_TEMPLATE


logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


class Course:
    """
    Class to manage new course setups.

    Attributes:
        org: Organization name used in the account's sub-domain
        course_id: The normalized course id. Must not contain more than
          30 characters or have special characters.
        course_root: Course's root path
        domain: Domain name from tool consumer that launched the request
        exchange_root: Path for exchange folder
        gid: Grader's group id
        grader_name: Grader's account name
        grader_root: Grader's home path
        is_new_setup: True indicates a new setup, False otherwise
        token: JupyterHub API token used to authenticat requests with the Hub
        uid: Grader's user id
        user_role: the user role set in the grader's share notebook
    """

    def __init__(self, org: str, course_id: str, domain: str):
        self.org = org
        self.course_id = course_id
        self.domain = domain
        self.exchange_root = Path(os.environ.get('MNT_ROOT'), self.org, 'exchange')
        self.grader_name = f'grader-{course_id}'
        self.grader_root = Path(
            os.environ.get('MNT_ROOT'),
            org,
            'home',
            self.grader_name,
        )
        self.grader_shared_folder = Path(os.environ.get('MNT_ROOT'), org, 'shared', self.course_id)
        shared_folder_env = os.environ.get('SHARED_FOLDER_ENABLED') or 'False'
        self.is_shared_folder_enabled = True if shared_folder_env.lower() in ('true', '1') else False
        self.course_root = self.grader_root / course_id
        self.token = token_hex(32)
        self.client = docker.from_env()
        self.uid = int(os.environ.get('NB_GRADER_UID'))
        self.gid = int(os.environ.get('NB_GID'))
        self.user_role = 'Grader'
        self._is_new_setup = False
        self.jupyterhub_api = JupyterHubAPI()

    @property
    def jupyter_config_path(self):
        return self.grader_root / '.jupyter'

    @property
    def nbgrader_home_config_path(self):
        return self.jupyter_config_path / 'nbgrader_config.py'

    @property
    def nbgrader_course_config_path(self):
        return self.course_root / 'nbgrader_config.py'

    @property
    def is_new_setup(self):
        return self._is_new_setup

    async def setup(self):
        """
        Function to bootstrap new course setup

        Returns:
            is_new_setup: boolean to indicate whether or not the this setup
            function executed the functions to set up a new course.
        """
        if self.should_setup():
            self.create_directories()
            await self.add_jupyterhub_grader_group()
            await self.add_jupyterhub_student_group()
            self.run()

    def should_setup(self):
        """
        If the grader container exists then the setup_course boolean is set to
        false, otherwise true.

        Raises:
            docker.errors.NotFound
        """
        try:
            self.client.containers.get(self.grader_name)
            logger.debug('Grader container exists %s' % self.grader_name)
        except docker.errors.NotFound:
            logger.error('Grader container not found')
            self._is_new_setup = True
            return True

        return False

    def create_directories(self):
        """
        Creates exchange, grader account, and course directories as well
        as nbgrader configuration files. All directories and files are updated to have the
        UID/GID that belong to the instructor/grader values. Students and Grader/Instructors
        should have different UID's but the same GID.
        """
        logger.debug('Creating exchange directory %s' % self.exchange_root)
        self.exchange_root.mkdir(parents=True, exist_ok=True)
        self.exchange_root.chmod(0o777)
        logger.debug(
            'Creating grader directory and permissions with path %s to %s:%s ' % (self.grader_root, self.uid, self.gid)
        )
        self.grader_root.mkdir(parents=True, exist_ok=True)
        shutil.chown(str(self.grader_root), user=self.uid, group=self.gid)
        self.course_root.mkdir(parents=True, exist_ok=True)
        logger.debug(
            'Changing course directory permissions with path %s to %s:%s ' % (self.course_root, self.uid, self.gid)
        )
        shutil.chown(str(self.course_root), user=self.uid, group=self.gid)

        logger.debug('Course jupyter config path %s' % self.jupyter_config_path)
        self.jupyter_config_path.mkdir(parents=True, exist_ok=True)
        shutil.chown(str(self.jupyter_config_path), user=self.uid, group=self.gid)
        logger.debug('Change course jupyter config permissions to %s:%s' % (self.uid, self.gid))

        logger.debug('Grader home nbgrader_config.py path %s' % self.nbgrader_home_config_path)
        # format the config file with current settings/values and append the db_url setting
        nbgrader_config = NBGRADER_HOME_CONFIG_TEMPLATE.format(
            grader_name=self.grader_name,
            course_id=self.course_id,
            db_url=NbGraderServiceHelper(self.course_id).db_url,
        )

        self.nbgrader_home_config_path.write_text(nbgrader_config)
        shutil.chown(str(self.nbgrader_home_config_path), user=self.uid, group=self.gid)
        logger.debug(
            'Added shared grader home nbgrader config %s with permissions %s:%s'
            % (nbgrader_config, self.uid, self.gid)
        )

        logger.debug('Grader course nbgrader_config.py path %s' % self.nbgrader_course_config_path)
        nbgrader_config = NBGRADER_COURSE_CONFIG_TEMPLATE.format(course_id=self.course_id)
        self.nbgrader_course_config_path.write_text(nbgrader_config)
        shutil.chown(str(self.nbgrader_course_config_path), user=self.uid, group=self.gid)
        logger.debug(
            'Added shared grader course nbgrader config %s with permissions %s:%s'
            % (nbgrader_config, self.uid, self.gid)
        )
        if self.is_shared_folder_enabled is True:
            self.create_shared_directory()

    def create_shared_directory(self):
        """
        Creates the shared folder and initialize the git repo
        """
        git_init_commands = '''
        git init;
        git config --local user.name "illumidesk-grader";
        git config --local user.email "grader@illumidesk.local";
        echo '.ipynb_checkpoints/' >> .gitignore;
        git add .;
        git commit -m "Initial commit";
        '''
        logger.debug('Creating shared directory %s' % self.grader_shared_folder)
        self.grader_shared_folder.mkdir(parents=True, exist_ok=True)
        shutil.chown(str(self.grader_shared_folder), user=self.uid, group=self.gid)
        # initiate git repo
        try:
            # run git init
            logger.info(f'Initializing git repo in shared directory: {self.grader_shared_folder}')
            subprocess.check_output(git_init_commands, cwd=f'{self.grader_shared_folder}', shell=True)
        except Exception as er:
            logger.debug(f'Error initializing the git repo:{er}')

    async def add_jupyterhub_grader_group(self):
        """
        Add formgrader group with JupyterHub's REST API by sending a
        POST request to the the endpoint ../groups/formgrade-{course_id}.

        Returns:
            Response from JupyterHub's add group endpoint
        """
        group_name = f'formgrade-{self.course_id}'
        logger.debug(f'Adding grader group {group_name} with JupyterHub REST API')
        result = await self.jupyterhub_api.create_group(group_name)
        logger.debug('Response object when adding formgrader group: %s' % result)

    async def add_jupyterhub_student_group(self):
        """
        Add nbgrader group with JupyterHub's REST API by sending a
        POST request to the the endpoint ../groups/nbgrader-{course_id}.

        Returns:
            Response from JupyterHub's add group endpoint
        """
        group_name = f'nbgrader-{self.course_id}'
        logger.debug(f'Adding student group {group_name} with JupyterHub REST API')
        result = await self.jupyterhub_api.create_group(group_name)
        logger.debug('Response object when adding nbgrader group: %s' % result)

    def run(self):
        """
        Create and run a grader notebook with the docker client. This service's settings
        should coincide with the grader's JupyterHub.services definition. The JupyterHub.service
        is defined as an externally managed service and the docker client is what manages this
        grader service.
        """
        logger.debug('Running grader container with exchange root %s' % self.exchange_root)
        jupyterhub_api_url = os.environ.get('JUPYTERHUB_API_URL')
        jupyterhub_api_token = os.environ.get('JUPYTERHUB_API_TOKEN')
        base_url = os.environ.get('JUPYTERHUB_BASE_URL') or ''
        logger.debug('Grader container JUPYTERHUB_API_URL set to %s' % jupyterhub_api_url)
        logger.debug('Grader container JUPYTERHUB_API_TOKEN set to %s' % jupyterhub_api_token)
        # set initial volumes dict
        docker_volumes = {
            str(self.grader_root): {'bind': f'/home/{self.grader_name}'},
            str(self.exchange_root): {'bind': '/srv/nbgrader/exchange'},
        }
        if self.is_shared_folder_enabled:
            docker_volumes[str(self.grader_shared_folder)] = {'bind': f'/home/{self.grader_name}/shared'}
        self.client.containers.run(
            detach=True,
            image=os.environ.get('DOCKER_GRADER_IMAGE') or 'illumidesk/grader-notebook:latest',
            command=['start-notebook.sh', f'--group=formgrade-{self.course_id}'],
            environment=[
                f'JUPYTERHUB_SERVICE_NAME={self.course_id}',
                f'JUPYTERHUB_API_TOKEN={self.token}',
                f'JUPYTERHUB_API_URL={jupyterhub_api_url}',
                f'JUPYTERHUB_BASE_URL={base_url}/',
                f'JUPYTERHUB_SERVICE_PREFIX={base_url}/services/{self.course_id}/',
                f'JUPYTERHUB_CLIENT_ID=service-{self.course_id}',
                f'JUPYTERHUB_USER={self.grader_name}',
                f'NB_GRADER_UID={self.uid}',
                f'NB_GID={self.gid}',
                f'NB_USER={self.grader_name}',
                f'USER_ROLE={self.user_role}',
            ],
            volumes=docker_volumes,
            name=self.grader_name,
            user='root',
            working_dir=f'/home/{self.grader_name}',
            network=os.environ.get('DOCKER_NETWORK_NAME'),
            restart_policy={'Name': 'on-failure', 'MaximumRetryCount': 5},
        )

    def get_service_config(self) -> dict:
        """
        Creates service config definition that is used in jupyterhub's services section
        """
        url = f'http://{self.grader_name}:8888'
        service_config = {
            'name': self.course_id,
            'url': url,
            'oauth_no_confirm': True,
            'admin': True,
            'api_token': self.token,
        }
        return service_config
