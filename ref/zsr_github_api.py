import time
import datetime
# from datetime import datetime
import json
import logging
from typing import Iterable
from random import randint
import init
import os.path
import pathlib
from github.fetch_raw_diff import *
from util import localfile
from util import language_tool
import util.timeUtil
from github import fetch_raw_diff
import os

try:
    import settings
except ImportError:
    settings = object()

# _tokens = getattr(settings, "SCRAPER_GITHUB_API_TOKENS", [])

with open(init.currentDIR+"/data/token.txt", 'r') as file:
    _tokens = [line.rstrip('\n') for line in file]

logger = logging.getLogger('ghd.scraper')

LOCAL_DATA_PATH = init.LOCAL_DATA_PATH
file_list_cache = {}


class RepoDoesNotExist(requests.HTTPError):
    pass


class TokenNotReady(requests.HTTPError):
    pass


def parse_commit(commit):
    github_author = commit['author'] or {}
    commit_author = commit['commit'].get('author') or {}
    return {
        'sha': commit['sha'],
        'author': github_author.get('login'),
        'author_name': commit_author.get('name'),
        'author_email': commit_author.get('email'),
        'authored_date': commit_author.get('date'),
        'message': commit['commit']['message'].replace("\n", ","),
        'committed_date': commit['commit']['committer']['date'],
        'parents': "\n".join(p['sha'] for p in commit['parents']),
        'verified': commit.get('verification', {}).get('verified')
    }


class GitHubAPIToken(object):
    api_url = "https://api.github.com/"

    token = None
    timeout = None
    _user = None
    _headers = None

    limit = None  # see __init__ for more details

    def __init__(self, token=None, timeout=None):
        if token is not None:
            self.token = token
            self._headers = {
                "Authorization": "token " + token,
                # "Accept": "application/vnd.github.v3+json",
                "Accept": "application/vnd.github.mockingbird-preview"
                #                 "User-Agent": "request"
            }
        self.limit = {}
        for api_class in ('core', 'search'):
            self.limit[api_class] = {
                'limit': None,
                'remaining': None,
                'reset_time': None
            }
        self.timeout = timeout
        super(GitHubAPIToken, self).__init__()

    @property
    def user(self):
        if self._user is None:
            try:
                r = self.request('user')
            except TokenNotReady:
                pass
            else:
                self._user = r.json().get('login', '')
        return self._user

    def _check_limits(self):
        # regular limits will be updaated automatically upon request
        # we only need to take care about search limit
        try:
            s = self.request('rate_limit').json()['resources']['search']
        except TokenNotReady:
            # self.request updated core limits already; search limits unknown
            s = {'remaining': None, 'reset': None, 'limit': None}

        self.limit['search'] = {
            'remaining': s['remaining'],
            'reset_time': s['reset'],
            'limit': s['limit']
        }

    @staticmethod
    def api_class(url):
        return 'search' if url.startswith('search') else 'core'

    def ready(self, url):
        t = self.when(url)
        return not t or t <= time.time()

    def legit(self):
        if self.limit['core']['limit'] is None:
            self._check_limits()
        return self.limit['core']['limit'] < 100

    def when(self, url):
        key = self.api_class(url)
        if self.limit[key]['remaining'] != 0:
            return 0
        return self.limit[key]['reset_time']

    def request(self, url,timeline=False, method='get', data=None, **params):
        # TODO: use coroutines, perhaps Tornado (as PY2/3 compatible)

        if not self.ready(url):
            raise TokenNotReady
        # Exact API version can be specified by Accept header:
        # "Accept": "application/vnd.github.v3+json"}

        # might throw a timeout
        if timeline:
            tl_headers = self._headers
            tl_headers["Accept"] = "application/vnd.github.mockingbird-preview+json"
            r = requests.request(
                method, self.api_url +"repos/"+url, params=params, data=data,
                headers=tl_headers, timeout=self.timeout)
        else:
            r = requests.request(
                method, self.api_url + url, params=params, data=data,
                headers=self._headers, timeout=self.timeout)

        if 'X-RateLimit-Remaining' in r.headers:
            remaining = int(r.headers['X-RateLimit-Remaining'])
            self.limit[self.api_class(url)] = {
                'remaining': remaining,
                'reset_time': int(r.headers['X-RateLimit-Reset']),
                'limit': int(r.headers['X-RateLimit-Limit'])
            }

            if r.status_code == 403 and remaining == 0:
                raise TokenNotReady
            if r.status_code == 443:
                print('443 error')
                raise TokenNotReady
        return r


class GitHubAPI(object):
    """ This is a convenience class to pool GitHub API keys and update their
    limits after every request. Actual work is done by outside classes, such
    as _IssueIterator and _CommitIterator
    """
    _instance = None  # instance of API() for Singleton pattern implementation
    tokens = None

    def __new__(cls, *args, **kwargs):  # Singleton
        if not isinstance(cls._instance, cls):
            cls._instance = super(GitHubAPI, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, tokens=_tokens, timeout=30):
        if not tokens:
            raise EnvironmentError(
                "No GitHub API tokens found in settings.py. Please add some.")
        self.tokens = [GitHubAPIToken(t, timeout=timeout) for t in tokens]

    def requestPR(self, url, method='get', page=1, data=None, **params):
        # type: (str, str, bool, str) -> dict
        """ Generic, API version agnostic request method """
        timeout_counter = 0
        params['page'] = page
        params['per_page'] = init.numPRperPage
        while True:
            for token in self.tokens:
                # for token in sorted(self.tokens, key=lambda t: t.when(url)):
                if not token.ready(url):
                    continue

                try:
                    r = token.request(url, method=method, data=data, **params)
                    # print(r.url)
                except requests.ConnectionError:
                    print('except requests.ConnectionError')
                    continue
                except TokenNotReady:
                    continue
                except requests.exceptions.Timeout:
                    timeout_counter += 1
                    if timeout_counter > len(self.tokens):
                        raise
                    continue  # i.e. try again

                if r.status_code in (404, 451):
                    print("404, 451 retry..")
                    return {}
                    # API v3 only
                    # raise RepoDoesNotExist(
                    #     "GH API returned status %s" % r.status_code)
                elif r.status_code == 409:
                    print("409 retry..")
                    # repository is empty https://developer.github.com/v3/git/
                    return {}
                elif r.status_code == 410:
                    print("410 retry..")
                    # repository is empty https://developer.github.com/v3/git/
                    return {}
                elif r.status_code == 401:
                    print("401,Bad credentials, please remove this token")
                    continue
                elif r.status_code == 403:
                    # repository is empty https://developer.github.com/v3/git/
                    print("403 retry..")
                    time.sleep(randint(1, 60))
                    continue
                elif r.status_code == 443:
                    # repository is empty https://developer.github.com/v3/git/
                    print("443 retry..")
                    time.sleep(randint(1, 29))
                    continue
                elif r.status_code == 502:
                    # repository is empty https://developer.github.com/v3/git/
                    print("443 retry..")
                    time.sleep(randint(1, 29))
                    continue
                r.raise_for_status()
                res = r.json()
                return res

            next_res = min(token.when(url) for token in self.tokens)
            sleep = int(next_res - time.time()) + 1
            if sleep > 0:
                logger.info(
                    "%s: out of keys, resuming in %d minutes, %d seconds",
                    datetime.now().strftime("%H:%M"), *divmod(sleep, 60))
                time.sleep(sleep)
                logger.info(".. resumed")

    def request(self, url,time_line=False,time_delay=None,early_pr=None, method='get', paginate=False, data=None,   **params):
        # type: (str, str, bool, str) -> dict
        """ Generic, API version agnostic request method """

        timeout_counter = 0
        if paginate:
            paginated_res = []
            params['page'] = 1
            params['per_page'] = 100
            # params['per_page'] = 30

        while True:
            for token in self.tokens:
                # for token in sorted(self.tokens, key=lambda t: t.when(url)):
                if not token.ready(url):
                    continue

                try:
                    if time_line:
                        r = token.request(url,time_line, method=method, data=data, **params)
                    else:
                        r = token.request(url, method=method, data=data, **params)
                    print(r.url)
                except requests.ConnectionError:
                    print('except requests.ConnectionError')
                    continue
                except TokenNotReady:
                    continue
                except requests.exceptions.Timeout:
                    timeout_counter += 1
                    if timeout_counter > len(self.tokens):
                        raise
                    continue  # i.e. try again

                if r.status_code in (404, 451):
                    print("404, 451 retry..")
                    return {}
                    # API v3 only
                    # raise RepoDoesNotExist(
                    #     "GH API returned status %s" % r.status_code)
                elif r.status_code == 409:
                    print("409 retry..")
                    # repository is empty https://developer.github.com/v3/git/
                    return {}
                elif r.status_code == 410:
                    print("410 retry..")
                    # repository is empty https://developer.github.com/v3/git/
                    return {}
                elif r.status_code == 401:
                    print("401,Bad credentials, please remove this token")
                    continue
                elif r.status_code == 403:
                    # repository is empty https://developer.github.com/v3/git/
                    print("403 retry..")
                    time.sleep(randint(1, 60))
                    continue
                elif r.status_code == 443:
                    # repository is empty https://developer.github.com/v3/git/
                    print("443 retry..")
                    time.sleep(randint(1, 29))
                    continue
                elif r.status_code == 502:
                    # repository is empty https://developer.github.com/v3/git/
                    print("502 retry..")
                    time.sleep(randint(1, 29))
                    continue
                elif r.status_code == 500:
                    # repository is empty https://developer.github.com/v3/git/
                    print("500 retry..")
                    time.sleep(randint(1, 29))
                    continue
                elif r.status_code == 504:
                    # repository is empty https://developer.github.com/v3/git/
                    print("504 Server Error: Gateway Time-out for url. Retry..")
                    time.sleep(randint(1, 29))
                    continue
                elif r.status_code == 422:
                    print("422 skip..")
                    return {}

                r.raise_for_status()
                res = r.json()
                if paginate:
                    paginated_res.extend(res)
                    # add to limit pr's time in one year //zy
                    if len(paginated_res):
                        if time_delay:
                            # if limit pr number
                            if early_pr:
                                for pr in paginated_res:
                                    # find early_pr
                                    if pr['number'] == early_pr:
                                        early_time = datetime.datetime.strptime(pr['created_at'],'%Y-%m-%dT%H:%M:%SZ').date()
                                    else:
                                        early_time = None
                                    # determine limit time
                                    if early_time:
                                        end_time = early_time + datetime.timedelta(days=-time_delay)
                                    else:
                                        end_time = None
                                    # ensure prs in limit time are all fetched
                                    if end_time:
                                        current_time = datetime.datetime.strptime(paginated_res[-1]['created_at'],'%Y-%m-%dT%H:%M:%SZ').date()
                                        if current_time < end_time:
                                            return paginated_res
                                        else:
                                            break
                            else:
                                if 'created_at' in paginated_res[0]:
                                    upper_date_str = paginated_res[0]['created_at']
                                    upper_date = datetime.datetime.strptime(upper_date_str,'%Y-%m-%dT%H:%M:%SZ')
                                    lower_date = upper_date.date() + datetime.timedelta(days=-time_delay)
                                    current_date = datetime.datetime.strptime(paginated_res[-1]['created_at'],'%Y-%m-%dT%H:%M:%SZ').date()
                                    if current_date < lower_date:
                                        return paginated_res
                                    else:
                                        pass
                                else:
                                    pass

                        else:
                            pass
                    else:
                        pass
                    has_next = 'rel="next"' in r.headers.get("Link", "")
                    if not res or not has_next:
                        return paginated_res
                    else:
                        params["page"] += 1
                        continue
                else:
                    return res

            next_res = min(token.when(url) for token in self.tokens)
            sleep = int(next_res - time.time()) + 1
            if sleep > 0:
                logger.info(
                    "%s: out of keys, resuming in %d minutes, %d seconds",
                    datetime.now().strftime("%H:%M"), *divmod(sleep, 60))
                time.sleep(sleep)
                logger.info(".. resumed")

    def repo_issues(self, repo_name, page=None):
        # type: (str, int) -> Iterable[dict]
        url = "repos/%s/issues" % repo_name

        if page is None:
            data = self.request(url, paginate=True, state='all')
        else:
            data = self.request(url, page=page, per_page=100, state='all')

        for issue in data:
            if 'pull_request' not in issue:
                yield {
                    'author': issue['user']['login'],
                    'closed': issue['state'] != "open",
                    'created_at': issue['created_at'],
                    'updated_at': issue['updated_at'],
                    'closed_at': issue['closed_at'],
                    'number': issue['number'],
                    'title': issue['title']
                }

    def repo_commits(self, repo_name):

        url = "repos/%s/commits" % repo_name

        for commit in self.request(url, paginate=True):
            # might be None for commits authored outside of github
            yield parse_commit(commit)

        url = "repos/%s/pulls" % repo_name

        for pr in self.request(url, paginate=True, state='all'):
            body = pr.get('body', {})
            head = pr.get('head', {})
            head_repo = head.get('repo') or {}
            base = pr.get('base', {})
            base_repo = base.get('repo') or {}

            yield {
                'id': int(pr['number']),  # no idea what is in the id field
                'title': pr['title'],
                'body': body,
                'labels': 'labels' in pr and [l['name'] for l in pr['labels']],
                'created_at': pr['created_at'],
                'updated_at': pr['updated_at'],
                'closed_at': pr['closed_at'],
                'merged_at': pr['merged_at'],
                'author': pr['user']['login'],
                'head': head_repo.get('full_name'),
                'head_branch': head.get('label'),
                'base': base_repo.get('full_name'),
                'base_branch': base.get('label'),
            }

    def pr_status(self, repo, pr_id):
        url = "repos/%s/pulls/%s" % (repo, pr_id)
        pr = self.request(url)
        return pr['state']

    def pull_request_commits(self, repo, pr_id):
        # type: (str, int) -> Iterable[dict]
        url = "repos/%s/pulls/%d/commits" % (repo, pr_id)

        for commit in self.request(url, paginate=True, state='all'):
            yield parse_commit(commit)

    def issue_comments(self, repo, issue_id):
        """ Return comments on an issue or a pull request
        Note that for pull requests this method will return only general
        comments to the pull request, but not review comments related to
        some code. Use review_comments() to get those instead

        :param repo: str 'owner/repo'
        :param issue_id: int, either an issue or a Pull Request id
        """
        url = "repos/%s/issues/%s/comments" % (repo, issue_id)

        for comment in self.request(url, paginate=True, state='all'):
            yield {
                'body': comment['body'],
                'author': comment['user']['login'],
                'created_at': comment['created_at'],
                'updated_at': comment['updated_at'],
            }

    def get_issue_pr_timeline(self, repo, issue_id):
        """ Return timeline on an issue or a pull request
        :param repo: str 'owner/repo'url
        :param issue_id: int, either an issue or a Pull Request id
        """
        url = "repos/%s/issues/%s/timeline" % (repo, issue_id)
        # print(url)
        events = self.request(url, paginate=True, state='all')
        return events

    def issue_pr_timeline(self, repo, issue_id):
        """ Return timeline on an issue or a pull request
        :param repo: str 'owner/repo'url
        :param issue_id: int, either an issue or a Pull Request id
        """
        url = "repos/%s/issues/%s/timeline" % (repo, issue_id)
        events = self.request(url, paginate=True, state='all')
        for event in events:
            # print('repo: ' + repo + ' issue: ' + str(issue_id) + ' event: ' + event['event'])
            if event['event'] == 'cross-referenced':
                author = event['actor'] or {}
                yield {
                    'event': event['event'],
                    'author': author.get('login'),
                    'email': '',
                    'author_type': author.get('type'),
                    'author_association': '',
                    'commit_id': "",
                    'created_at': event.get('created_at'),
                    'id': event['source']['issue']['number'],
                    'repo': event['source']['issue']['repository']['full_name'],
                    'type': 'pull_request' if 'pull_request' in event['source']['issue'].keys() else 'issue',
                    'state': event['source']['issue']['state'],
                    'assignees': event['source']['issue']['assignees'],
                    'label': "",
                    'body': ''
                }
            elif event['event'] == 'referenced':
                author = event['actor'] or {}
                yield {
                    'event': event['event'],
                    'author': author.get('login'),
                    'email': '',
                    'author_type': author.get('type'),
                    'author_association': '',
                    'commit_id': event['commit_id'],
                    'created_at': event['created_at'],
                    'id': '',
                    'repo': '',
                    'type': 'commit',
                    'state': '',
                    'assignees': '',
                    'label': '',
                    'body': ''
                }
            elif event['event'] == 'labeled':
                author = event['actor'] or {}
                yield {
                    'event': event['event'],
                    'author': author.get('login'),
                    'email': '',
                    'author_type': author.get('type'),
                    'author_association': '',
                    'commit_id': '',
                    'created_at': event.get('created_at'),
                    'id': '',
                    'repo': '',
                    'type': "label",
                    'state': '',
                    'assignees': '',
                    'label': event['label']['name'],
                    'body': ''
                }
            elif event['event'] == 'committed':
                yield {
                    'event': event['event'],
                    'author': event['author']['name'],
                    'email': event['author']['email'],
                    'author_type': '',
                    'author_association': '',
                    'commit_id': event['sha'],
                    'created_at': event.get('created_at'),
                    'id': '',
                    'repo': '',
                    'type': "commit",
                    'state': '',
                    'assignees': '',
                    'label': '',
                    'body': ''
                }
            elif event['event'] == 'reviewed':
                author = event['user'] or {}
                yield {
                    'event': event['event'],
                    'author': author.get('login'),
                    'email': '',
                    'author_type': author.get('type'),
                    'author_association': event['author_association'],
                    'commit_id': '',
                    'created_at': event.get('created_at'),
                    'id': '',
                    'repo': '',
                    'type': "review",
                    'state': event['state'],
                    'assignees': '',
                    'label': '',
                    'body': ''
                }
            elif event['event'] == 'commented':
                yield {
                    'event': event['event'],
                    'author': event['user']['login'],
                    'email': '',
                    'author_type': event['user']['type'],
                    'author_association': event['author_association'],
                    'commit_id': '',
                    'created_at': event.get('created_at'),
                    'id': '',
                    'repo': '',
                    'type': "comment",
                    'state': '',
                    'assignees': '',
                    'label': '',
                    'body': event['body']
                }
            elif event['event'] == 'assigned':
                author = event['actor'] or {}
                yield {
                    'event': event['event'],
                    'author': author.get('login'),
                    'email': '',
                    'author_type': author.get('type'),
                    'author_association': '',
                    'commit_id': '',
                    'created_at': event.get('created_at'),
                    'id': '',
                    'repo': '',
                    'type': "comment",
                    'state': '',
                    'assignees': '',
                    'label': '',
                    'body': ''
                }
            elif event['event'] == 'closed':
                author = event['actor'] or {}
                yield {
                    'event': event['event'],
                    'author': author.get('login'),
                    'email': '',
                    'author_type': author.get('type'),
                    'author_association': '',
                    'commit_id': event['commit_id'],
                    'created_at': event.get('created_at'),
                    'id': '',
                    'repo': '',
                    'type': "close",
                    'state': '',
                    'assignees': '',
                    'label': '',
                    'body': ''
                }
            elif event['event'] == 'subscribed':
                author = event['actor'] or {}
                yield {
                    'event': event['event'],
                    'author': author.get('login'),
                    'email': '',
                    'author_type': author.get('type'),
                    'author_association': '',
                    'commit_id': event['commit_id'],
                    'created_at': event.get('created_at'),
                    'id': event['commit_id'],
                    'repo': '',
                    'type': "subscribed",
                    'state': '',
                    'assignees': '',
                    'label': '',
                    'body': ''
                }
            elif event['event'] == 'merged':
                author = event['actor'] or {}
                yield {
                    'event': event['event'],
                    'author': author.get('login'),
                    'email': '',
                    'author_type': author.get('type'),
                    'author_association': '',
                    'commit_id': event['commit_id'],
                    'created_at': event.get('created_at'),
                    'id': event['commit_id'],
                    'repo': '',
                    'type': "merged",
                    'state': '',
                    'assignees': '',
                    'label': '',
                    'body': ''
                }
            else:
                yield {
                    'event': event['event'],
                    'author': '',
                    'email': '',
                    'author_type': '',
                    'author_association': '',
                    'commit_id': '',
                    'created_at': event.get('created_at'),
                    'id': '',
                    'repo': '',
                    'type': "",
                    'state': '',
                    'assignees': '',
                    'label': '',
                    'body': ''
                }

    def pr_changedFiles(self, repo, pr_id):
        """ Return changed file list on an issue or a pull request
        :param repo: str 'owner/repo'url
        :param pr_id: int,  Pull Request id
        """
        url = "repos/%s/pulls/%s/files" % (repo, pr_id)
        files = self.request(url, paginate=True, state='all')
        for file in files:
            # print('repo: ' + repo + ' issue: ' + str(issue_id) + ' event: ' + event['event'])

            yield {
                'filename': file['filename'],
                'status': file['status'],
                'additions': file['additions'],
                'deletions': file['deletions'],
                'changes': file['changes'],
                'blob_url': file['blob_url'],
                'raw_url': file['raw_url'],
                'contents_url': file['contents_url']
            }

    def commit_changedFile(self, repo, sha):
        """ Return changed file list on an issue or a pull request
        :param repo: str 'owner/repo'url
        :param sha,
        """

        url = "repos/%s/commits/%s" % (repo, sha)
        commitInfo = self.request(url)
        files = commitInfo['files']
        for file in files:
            yield {
                'filename': file['filename'],
                'status': file['status'],
                'additions': file['additions'],
                'deletions': file['deletions'],
                'changes': file['changes']
            }

    def repoLastPushDate(self, repoUrl):
        url = "repos/%s" % (repoUrl)
        repoInfo = self.request(url)
        if (len(repoInfo) == 0):
            print(repoUrl + " deleted")
            return ''
        else:
            return repoInfo['pushed_at']

    def userEmail(self, loginID):
        """ Return changed file list on an issue or a pull request
        :param repo: str 'owner/repo'url
        :param sha,
        """
        url = "users/%s" % (loginID)
        userInfo = self.request(url)
        if (len(userInfo) == 0):
            print(loginID + " deleted")
            return ''
        else:
            email = userInfo['email']
            return email


def review_comments(self, repo, pr_id):
    """ Pull request comments attached to some code
    See also issue_comments()
    """
    url = "repos/%s/pulls/%s/comments" % (repo, pr_id)

    for comment in self.request(url, paginate=True, state='all'):
        yield {
            'id': comment['id'],
            'body': comment['body'],
            'author': comment['user']['login'],
            'created_at': comment['created_at'],
            'updated_at': comment['updated_at'],
            'author_association': comment['author_association']
        }


def user_info(self, user):
    # Docs: https://developer.github.com/v3/users/#response
    return self.request("users/" + user)


def org_members(self, org):
    # TODO: support pagination
    return self.request("orgs/%s/members" % org)


def user_orgs(self, user):
    # TODO: support pagination
    return self.request("users/%s/orgs" % user)


@staticmethod
def project_exists(repo_name):
    return bool(requests.head("https://github.com/" + repo_name))


@staticmethod
def canonical_url(project_url):
    # type: (str) -> str
    """ Normalize URL
    - remove trailing .git  (IMPORTANT)
    - lowercase (API is insensitive to case, but will allow to deduplicate)
    - prepend "github.com"

    :param project_url: str, user_name/repo_name
    :return: github.com/user_name/repo_name with both names normalized

    >>> GitHubAPI.canonical_url("pandas-DEV/pandas")
    'github.com/pandas-dev/pandas'
    >>> GitHubAPI.canonical_url("http://github.com/django/django.git")
    'github.com/django/django'
    >>> GitHubAPI.canonical_url("https://github.com/A/B/")
    'github.com/a/b/'
    """
    url = project_url.lower()
    for chunk in ("httpp://", "https://", "github.com"):
        if url.startswith(chunk):
            url = url[len(chunk):]
    if url.endswith("/"):
        url = url[:-1]
    while url.endswith(".git"):
        url = url[:-4]
    return "github.com/" + url


@staticmethod
def activity(repo_name):
    # type: (str) -> dict
    """Unofficial method to get top 100 contributors commits by week"""
    url = "https://github.com/%s/graphs/contributors" % repo_name
    headers = {
        'X-Requested-With': 'XMLHttpRequest',
        'Accept-Encoding': "gzip,deflate,br",
        'Accept': "application/json",
        'Origin': 'https://github.com',
        'Referer': url,
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:53.0) "
                      "Gecko/20100101 Firefox/53.0",
        "Host": 'github.com',
        "Accept-Language": 'en-US,en;q=0.5',
        "Connection": "keep-alive",
        "Cache-Control": 'max-age=0',
    }
    cookies = requests.get(url).cookies
    r = requests.get(url + "-data", cookies=cookies, headers=headers)
    r.raise_for_status()
    return r.json()


class GitHubAPIv4(GitHubAPI):
    def v4(self, query, **params):
        # type: (str) -> dict
        payload = json.dumps({"query": query, "variables": params})
        return self.request("graphql", 'post', data=payload)

    def repo_issues(self, repo_name, cursor=None):
        # type: (str, str) -> Iterable[dict]
        owner, repo = repo_name.split("/")
        query = """query ($owner: String!, $repo: String!, $cursor: String) {
        repository(name: $repo, owner: $owner) {
          hasIssuesEnabled
            issues (first: 100, after: $cursor,
              orderBy: {field:CREATED_AT, direction: ASC}) {
                nodes {author {login}, closed, createdAt,
                       updatedAt, number, title}
                pageInfo {endCursor, hasNextPage}
        }}}"""

        while True:
            data = self.v4(query, owner=owner, repo=repo, cursor=cursor
                           )['data']['repository']
            if not data:  # repository is empty, deleted or moved
                break

            for issue in data["issues"]:
                yield {
                    'author': issue['author']['login'],
                    'closed': issue['closed'],
                    'created_at': issue['createdAt'],
                    'updated_at': issue['updatedAt'],
                    'closed_at': None,
                    'number': issue['number'],
                    'title': issue['title']
                }

            cursor = data["issues"]["pageInfo"]["endCursor"]

            if not data["issues"]["pageInfo"]["hasNextPage"]:
                break

    def repo_commits(self, repo_name, cursor=None):
        # type: (str, str) -> Iterable[dict]
        """As of June 2017 GraphQL API does not allow to get commit parents
        Until this issue is fixed this method is only left for a reference
        Please use commits() instead"""
        owner, repo = repo_name.split("/")
        query = """query ($owner: String!, $repo: String!, $cursor: String) {
        repository(name: $repo, owner: $owner) {
          ref(qualifiedName: "master") {
            target { ... on Commit {
              history (first: 100, after: $cursor) {
                nodes {sha:oid, author {name, email, user{login}}
                       message, committedDate}
                pageInfo {endCursor, hasNextPage}
        }}}}}}"""

        while True:
            data = self.v4(query, owner=owner, repo=repo, cursor=cursor
                           )['data']['repository']
            if not data:
                break

            for commit in data["ref"]["target"]["history"]["nodes"]:
                yield {
                    'sha': commit['sha'],
                    'author': commit['author']['user']['login'],
                    'author_name': commit['author']['name'],
                    'author_email': commit['author']['email'],
                    'authored_date': None,
                    'message': commit['message'],
                    'committed_date': commit['committedDate'],
                    'parents': None,
                    'verified': None
                }

            cursor = data["ref"]["target"]["history"]["pageInfo"]["endCursor"]
            if not data["ref"]["target"]["history"]["pageInfo"]["hasNextPage"]:
                break


def fetch_pr_code_info(repo, pr_id, must_in_local=False):
    global file_list_cache
    ind = (repo, pr_id)
    if ind in file_list_cache:
        return file_list_cache[ind]

    path = LOCAL_DATA_PATH + '/pr_data/%s/%s' % (repo, pr_id)
    # if os.path.exists(path + '/toobig.txt'):
    #     return []

    raw_diff_path = path + '/raw_diff.json'
    pull_files_path = path + '/pull_files.json'


    if os.path.exists(raw_diff_path) or os.path.exists(pull_files_path):
        if os.path.exists(raw_diff_path):
            file_list = localfile.get_file(raw_diff_path)
        elif os.path.exists(pull_files_path):
            pull_files = localfile.get_file(pull_files_path)
            file_list = [parse_diff(file["file_full_name"], file["changed_code"]) for file in pull_files]
        else:
            raise Exception('error on fetch local file %s' % path)
    else:
        if must_in_local:
            raise Exception('not found in local')
        file_list = fetch_file_list(repo, pr_id)

    codeOnlyFileList = filterNonCodeFiles(file_list,path)
    if len(codeOnlyFileList) > 0:
        file_list_cache[ind] = codeOnlyFileList
    return codeOnlyFileList

def filterNonCodeFiles(file_list, outfile_prefix):
    newFileList = []
    count = 0
    for f in file_list:
        if count > 500:
            localfile.write_to_file(outfile_prefix + "/toobig.txt", '500file')
            return []
        if not language_tool.is_text(f['name']):
            newFileList.append(f)
            count +=1
    return newFileList

# -------------------About Repo--------------------------------------------------------
def get_repo_PRlist(repo, type, renew, time_delay=None, early_pr=None):
    api = GitHubAPI()
    save_path = LOCAL_DATA_PATH + '/pr_data/' + repo + '/%s_list.json' % type

    # todo: could be extended to analyze forks in the future
    if type == 'fork':
        save_path = LOCAL_DATA_PATH + '/result/' + repo + '/forks_list.json'

    if (os.path.exists(save_path)) and (not renew):
        print("read from local files and return")
        try:
            return localfile.get_file(save_path)
        except:
            pass

    print('files does not exist in local disk, start to fetch new list for ', repo, type)
    if (type == 'pull') or (type == 'issue'):
        ret = api.request('repos/%s/%ss' % (repo, type), time_delay, early_pr, state='all', paginate=True)
    else:
        if type == 'branch':
            type = 'branche'
        ret = api.request('repos/%s/%ss' % (repo, type), True)

    localfile.write_to_file(save_path, ret)
    return ret

def get_repo_info_forPR_experiment(repo, type, renew):
    filtered_result = []
    api = GitHubAPI()
    print(init.local_pr_data_dir + repo + '/pull_list.json')
    save_path = LOCAL_DATA_PATH + '/pr_data/' + repo + '/pull_list.json'

    if (os.path.exists(save_path)) and (not renew):
        try:
            return localfile.get_file(save_path)
        except:
            pass

def get_repo_info_forPR(repo, type, renew,time_delay=None, early_pr=None):
    filtered_result = []
    api = GitHubAPI()
    # print(init.local_pr_data_dir + repo + '/pull_list.json')
    print(init.local_pr_data_dir + repo + '/issue_list.json')
    # pullListfile = pathlib.Path(init.local_pr_data_dir + repo + '/pull_list.json')
    pullListfile = pathlib.Path(init.local_pr_data_dir + repo + '/issue_list.json')
    if pullListfile.exists():
        tocheck_pr = getOldOpenPRs(repo)
        print("tocheck_pr " + str(tocheck_pr))
        if (tocheck_pr is None):
            tocheck_pr = 0

        save_path = LOCAL_DATA_PATH + '/pr_data/' + repo + '/%s_list.json' % type
        if type == 'fork':
            save_path = LOCAL_DATA_PATH + '/result/' + repo + '/forks_list.json'

        if (os.path.exists(save_path)) and (not renew):
            try:
                return localfile.get_file(save_path)
            except:
                pass

        print('start fetch new list for ', repo, type)
        if (type == 'pull') or (type == 'issue'):
            page_index = 1
            while (True):
                ret = api.requestPR('repos/%s/%ss' % (repo, type), state='all', page=page_index)
                numPR = init.numPRperPage
                if (len(ret) > 0):
                    for pr in ret:
                        # if (pr['number'] >= tocheck_pr):
                        if (pr['number'] >= tocheck_pr):
                            filtered_result.append(pr)
                        else:
                            print('get all ' + str(len(filtered_result)) + ' prs')
                            localfile.replaceWithNewPRs(save_path, filtered_result)
                            return filtered_result
                    if (len(filtered_result) < numPR):
                        print('get all ' + str(len(filtered_result)) + ' prs -- after page ' + str(page_index))
                        localfile.replaceWithNewPRs(save_path, filtered_result)
                        return filtered_result
                    else:
                        page_index += 1
                        numPR += init.numPRperPage
                else:
                    print("get pulls failed")
                    return filtered_result
        else:
            if type == 'branch':
                type = 'branche'
            ret = api.request('repos/%s/%ss' % (repo, type), True)

        localfile.write_to_file(save_path, ret)
        print("finish write pull list of ",repo)
    else:
        print('pull list does not exist, get from scratch')
        ret = get_repo_PRlist(repo, type, renew,time_delay,early_pr)
    return ret


def fetch_commit(url, renew=False):
    api = GitHubAPI()
    save_path = LOCAL_DATA_PATH + '/pr_data/%s.json' % url.replace('https://api.github.com/repos/', '')
    if os.path.exists(save_path) and (not renew):
        try:
            return localfile.get_file(save_path)
        except:
            pass

    c = api.request(url)
    time.sleep(0.7)
    file_list = []
    for f in c['files']:
        if 'patch' in f:
            file_list.append(fetch_raw_diff.parse_diff(f['filename'], f['patch']))
    localfile.write_to_file(save_path, file_list)
    return file_list


# ------------------About Pull Requests----------------------------------------------------

def get_pull(repo, num, renew=False):
    api = GitHubAPI()
    save_path = LOCAL_DATA_PATH + '/pr_data/%s/%s/api.json' % (repo, num)
    if os.path.exists(save_path) and (not renew):
        try:
            return localfile.get_file(save_path)
        except:
            pass

    r = api.request('repos/%s/pulls/%s' % (repo, num))
    time.sleep(3.0)
    localfile.write_to_file(save_path, r)
    return r


def concat_commits(commits):
    total_message = ''
    for c in commits:
        message = c['commit']['message']
        total_message += message + '\n'
    return total_message


def get_pr_commit(repo, pr_id, renew=False):
    save_path = LOCAL_DATA_PATH + '/pr_data/%s/%s/commits.json' % (repo, pr_id)
    commit_url = 'repos/%s/pulls/%s/commits' % (repo, pr_id)
    if os.path.exists(save_path) and (not renew) and (os.stat(save_path).st_size > 2):
        try:
            return localfile.get_file(save_path)
        except:

            pass
    #     commits = api.request(pull['commits_url'].replace('https://api.github.com/', ''), True)
    api = GitHubAPI()
    commits = api.request(commit_url.replace('https://api.github.com/', ''), paginate=True, state='all')
    time.sleep(0.7)
    localfile.write_to_file(save_path, commits)
    return commits


def get_another_pull(pull, renew=False):
    api = GitHubAPI()
    save_path = LOCAL_DATA_PATH + '/pr_data/%s/%s/another_pull.json' % (
        pull["base"]["repo"]["full_name"], pull["number"])
    if os.path.exists(save_path) and (not renew):
        try:
            return localfile.get_file(save_path)
        except:
            pass

    comments_href = pull["_links"]["comments"]["href"]  # found cites in comments, but checking events is easier.
    comments = api.request(comments_href, True)
    time.sleep(0.7)
    candidates = []
    for comment in comments:
        candidates.extend(get_pr_and_issue_numbers(comment["body"]))
    candidates.extend(get_pr_and_issue_numbers(pull["body"]))

    result = list(set(candidates))

    localfile.write_to_file(save_path, result)
    return result


# def fetch_file_list(pull, renew=False):
def fetch_file_list(repo, num, renew=False):
    api = GitHubAPI()
    # repo, num = pull["base"]["repo"]["full_name"], str(pull["number"])
    outfile_prefix = init.local_pr_data_dir + repo + "/" + str(num)
    save_path = outfile_prefix + '/raw_diff.json'
    if os.path.exists(save_path) and (not renew):
        try:
            return localfile.get_file(save_path)
        except:
            pass
    file_list = []

    li = api.request('repos/%s/pulls/%s/files' % (repo, num), paginate=True)
    time.sleep(0.8)
    for f in li:
        if f.get('changes', 0) <= 5000 and ('filename' in f) and ('patch' in f):
            file_list.append(fetch_raw_diff.parse_diff(f['filename'], f['patch']))

    localfile.write_to_file(save_path, file_list)
    return file_list


pull_commit_sha_cache = {}


def pull_commit_sha(p):
    index = (p["base"]["repo"]["full_name"], p["number"])
    if index in pull_commit_sha_cache:
        return pull_commit_sha_cache[index]
    c = get_pr_commit(p)
    ret = [(x["sha"], x["commit"]["author"]["name"]) for x in
           list(filter(lambda x: x["commit"]["author"] is not None, c))]
    pull_commit_sha_cache[index] = ret
    return ret


# ------------------Data Pre Collection----------------------------------------------------
def run_and_save(repo, skip_big=False):
    repo = repo.strip()

    skip_exist = True

    pulls = get_repo_PRlist(repo, 'pull', True)

    for pull in pulls:
        num = str(pull["number"])
        pull_dir = LOCAL_DATA_PATH + '/pr_data/' + repo + '/' + num

        pull = get_pull(repo, num)

        if skip_big and check_too_big(pull):
            continue

        if skip_exist and os.path.exists(pull_dir + '/raw_diff.json'):
            continue

        fetch_file_list(repo, pull)

        print('finish on', repo, num)


def getOldOpenPRs(repo):
    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    old_openPR_list = []

    file = init.local_pr_data_dir + repo + '/pull_list.json'
    latest_pr = 0
    with open(file) as json_file:
        data = json.load(json_file)
        if (len(data) > 0):
            latest_pr = data[0]['number']
            print("latest_pr " + str(latest_pr))
            for pr in data:
                number = pr['number']
                state = pr['state']
                created_at = pr['created_at']
                if (state == 'open'):
                    if (util.timeUtil.days_between(created_at, now) < 3):
                        old_openPR_list.append(number)

            if len(old_openPR_list) > 0:
                minID = min(old_openPR_list)
                if minID < latest_pr:
                    print("min(old_openPR_list)" + str(minID))
                    return minID
                else:
                    return latest_pr
            else:
                print("latest_pr" + str(latest_pr))
                return latest_pr


# This function checks if the PR has changed too many files
def check_too_big(pull):
    if not ("changed_files" in pull):
        pull = get_pull(pull["base"]["repo"]["full_name"], pull["number"])

    if not ("changed_files" in pull):
        pull = get_pull(pull["base"]["repo"]["full_name"], pull["number"], True)

    if pull["changed_files"] > 50:
        #         print('more than 50 changed files')
        return True
    if (pull["additions"] >= 10000) or (pull["deletions"] >= 10000):
        #         print('more than 10000 Loc changes')
        return True
    return False


check_large_cache = {}


# This function checks if the pull has changed too many files, call check_too_big internally. I am not sure why this is efficient...
def check_large(pull):
    #     print ("check_large:" + str(pull['number']))
    global check_large_cache
    index = (pull["base"]["repo"]["full_name"], pull["number"])
    if index in check_large_cache:
        return check_large_cache[index]

    check_large_cache[index] = True  # defalue true

    if check_too_big(pull):
        return True

    try:
        l = len(fetch_pr_code_info(pull))
    except Exception as e:
        if 'too big' in str(e):
            return True

    '''
    if l == 0:
        try:
            file_list = fetch_file_list(pull, True)
        except:
            path = '/DATA/luyao/pr_data/%s/%s' % (pull["base"]["repo"]["full_name"], pull["number"])
            flag_path = path + '/too_large_flag.json'
            localfile.write_to_file(flag_path, 'flag')
            print('too big', pull['html_url'])
            return True
    '''

    path = init.LOCAL_DATA_PATH + '/pr_data/%s/%s/raw_diff.json' % (pull["base"]["repo"]["full_name"], pull["number"])
    if os.path.exists(path) and (os.path.getsize(path) >= 50 * 1024):
        return True

    check_large_cache[index] = False
    return False


def text2list_precheck(func):
    def proxy(text):
        if text is None:
            return []
        ret = func(text)
        return ret

    return proxy


def get_timeline(url,time_line=False,renew=False):
        api = GitHubAPI()
        save_path = LOCAL_DATA_PATH + '/pr_data/%s.json' % url.replace('https://api.github.com/repos/', '').replace('issues/','')

        if os.path.exists(save_path) and (not renew):
            try:
                return localfile.get_file(save_path)
            except:
                pass

        if time_line:
            c = api.request(url,time_line=True)
        else:
            c = api.request(url)

        cr_re_list = []
        for item in c:
            if item['event'] == 'cross-referenced':
                cr_re_list.append(item)

        # localfile.write_to_file(save_path, c)
        localfile.write_to_file(save_path, cr_re_list)
        return cr_re_list



@text2list_precheck
def get_numbers(text):
    # todo previous version, got tons of FP crossreferece numbers
    # nums = list(filter(lambda x: len(x) >= 3, re.findall('([0-9]+)', text)))
    # nums = list(set(nums))

    # use get_pr_and_issue_numbers instead

    return get_pr_and_issue_numbers(text)


@text2list_precheck
def get_version_numbers(text):
    nums = [''.join(x) for x in re.findall('(\d+\.)?(\d+\.)(\d+)', text)]
    nums = list(set(nums))
    return nums


@text2list_precheck
def get_pr_and_issue_numbers(text):
    nums = []
    nums += re.findall('#([0-9]+)', text)
    nums += re.findall('pull\/([0-9]+)', text)
    nums += re.findall('issues\/([0-9]+)', text)
    nums = list(filter(lambda x: len(x) > 0, nums))
    nums = list(set(nums))
    return nums
