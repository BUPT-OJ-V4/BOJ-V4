from __future__ import unicode_literals

from django.db import models
from django.contrib.auth.models import User, Group
from django_dag.models import node_factory, edge_factory


class UserProfile(models.Model):
    user = models.OneToOneField(User, related_name='profile')
    nickname = models.CharField(max_length=30)
    gender = models.CharField(max_length=1)
    prefer_lang = models.CharField(max_length=4)


class GroupProfile(node_factory('Consisting')):
    nickname = models.CharField(max_length=30)
    group = models.OneToOneField(Group, related_name='profile')
    admins = models.ManyToManyField(User, related_name='managed_group_profiles')
    superadmin = models.ForeignKey(User, default=1, related_name='established_group_profiles')

    def __unicode__(self):
        return self.group.__unicode__() + "_profile"


class Consisting(edge_factory(GroupProfile, concrete=False)):
    name = models.CharField(max_length=32, blank=True, null=True)