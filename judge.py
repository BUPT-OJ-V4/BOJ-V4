import os
import sys
import django
import nsq
import json
import requests
from bojv4 import conf
import time
import threading
from django.db import connection

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ['DJANGO_SETTINGS_MODULE'] = 'bojv4.settings'
django.setup()

from submission.abstract_models import NormalSubmission
from contest.models import Submission as ContestSubmission
from django.core.files.base import ContentFile
from contest.models import ContestProblem
from django.contrib.auth.models import User
import logging
logger = logging.getLogger('judge')


class NsqQueue(object):

    handlers = []

    @classmethod
    def add_callback(cls, handler, topic, channel, address='127.0.0.1:4150'):
        r = nsq.Reader(message_handler=handler, nsqd_tcp_addresses=[address],
                topic=topic, channel=channel, lookupd_poll_interval=15)
        cls.handlers.append(r)

    @classmethod
    def start(cls):
        nsq.run()

def submission_handler(message):
    connection.close()
    logger.error("message.body: %s", message.body)
    mp = json.loads(message.body)
    # print json.dumps(mp, indent=4)
    sub_pk = mp.get('submission-id', None)
    is_contest = mp.get('submission-type', 'contest')
    if is_contest == 'contest':
        sub = ContestSubmission.objects.filter(pk=sub_pk).first()
    else:
        sub = NormalSubmission.objects.filter(pk=sub_pk).first()
    status = mp.get('status', None)
    if not sub or not status or status not in conf.STATUS_CODE.keys():
        logger.error("error status : %s", status)
        return True
    position = mp.get('position', '')
    if position != '':
        # CaseResult.deal_case_result(mp)
        # cases = sub.get_info('cases')
        case = {}
        case['position'] = int(position)
        case['time'] = int(mp.get('time', 0) * 1000)
        case['memory'] = mp.get('memory', 0)
        case['status'] = status
        sub.add_case(case)
        if status == 'AC':
            # sub.score += sub.problem.get_score(position)
            sub.add_score(int(position))
            sub.save()
        logger.error("======================json success2==================")
        sub.deal_case_result(case)
    else:
        if 'compile-message' in mp:
            sub.set_info('compile-message', mp['compile-message'])
        sub.status = status
        sub.save()
    logger.info("judge end")
    return True


def submit_handler(message):
    try:
        mp = json.loads(message.body)
        s = ContestSubmission()
        s.problem = ContestProblem.objects.get(pk=int(mp['problem']))
        s.language = mp['language']
        # sub.problem = s.problem.problem
        s.user = User.objects.get(pk=int(mp['user']))
        s.save()
        # s.submission = sub
        # s.save()
        s.judge(mp['code'])
    except Exception as ex:
        print ex
    return True


if __name__ == '__main__':
    NsqQueue.add_callback(handler=submission_handler, topic='submission', channel='123456')
    NsqQueue.add_callback(handler=submit_handler, topic='submit', channel='adfasdf')
    NsqQueue.start()

