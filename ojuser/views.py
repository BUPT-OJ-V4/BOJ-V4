from account.views import SignupView, SettingsView
from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User, Group
from django.views.generic import TemplateView, ListView, DetailView
from django.views.generic.edit import FormView
from django.http import HttpResponseRedirect

from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.decorators import list_route, detail_route
from rest_framework import viewsets, status
from django_tables2 import RequestConfig

from .forms import UserProfileForm, UserSettingsForm, UserProfilesForm
from .forms import GroupProfileForm, GroupForm
from .serializers import UserSerializer, UserProfileSerializer
from .serializers import GroupSerializer, UserSlugSerializer
from .tables import GroupUserTable


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserProfileSerializer

    @list_route(methods=['post'], url_path='bulk_create')
    def create_users(self, request):
        serializer = UserProfileSerializer(
            data=request.data, many=True, context={'request': request}
        )
        #  print request.data
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer

    @detail_route(methods=['get'], url_path='members')
    def get_members(self, request, pk=None):
        qs = self.get_queryset()
        group = get_object_or_404(qs, pk=pk)
        serializer = UserSlugSerializer(group.user_set, many=True)
        return Response(serializer.data)

    @detail_route(methods=['post'], url_path='addmembers')
    def add_users(self, request, pk=None):
        users = []
        errors = []
        valid = 1
        qs = self.get_queryset()
        group = get_object_or_404(qs, pk=pk)
        for x in request.data:
            try:
                user = User.objects.get(username=x['username'])
                users.append(user)
                if user in group.user_set.all():
                    errors.append({"username:user have in group"})
                else:
                    errors.append({})
            except User.DoesNotExist:
                errors.append({"username:user do not exsit"})
                valid = 0
        #  print request.data
        if valid:
            group.user_set.add(*users)
            return Response(errors, status=status.HTTP_201_CREATED)
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)


class OjUserSignupView(SignupView):

    form_class = UserProfileForm

    def after_signup(self, form):
        self.create_profile(form)
        super(OjUserSignupView, self).after_signup(form)

    def create_profile(self, form):
        profile = self.created_user.profile
        profile.nickname = form.cleaned_data["nickname"]
        profile.gender = form.cleaned_data["gender"]
        profile.prefer_lang = form.cleaned_data["prefer_lang"]
        profile.save()


class OjUserSettingsView(SettingsView):
    form_class = UserSettingsForm

    def update_account(self, form):
        profile = self.request.user.profile
        profile.nickname = form.cleaned_data["nickname"]
        profile.save()
        super(OjUserSettingsView, self).update_account(form)

    def get_initial(self):
        initial = super(OjUserSettingsView, self).get_initial()
        profile = self.request.user.profile
        initial["nickname"] = profile.nickname
        return initial


class OjUserProfilesView(FormView):
    template_name = 'account/profiles.html'
    form_class = UserProfilesForm
    #  success_url = reverse_lazy('account')
    success_url = '.'
    messages = {
        "profiles_updated": {
            "level": messages.SUCCESS,
            "text": _("Account profiles updated.")
        },
    }

    def get_initial(self):
        initial = super(OjUserProfilesView, self).get_initial()
        profile = self.request.user.profile
        initial["gender"] = profile.gender
        initial["prefer_lang"] = profile.prefer_lang
        return initial

    def form_valid(self, form):
        profile = self.request.user.profile
        profile.gender = form.cleaned_data["gender"]
        profile.prefer_lang = form.cleaned_data["prefer_lang"]
        profile.save()
        if self.messages.get("profiles_updated"):
            messages.add_message(
                self.request,
                self.messages["profiles_updated"]["level"],
                self.messages["profiles_updated"]["text"]
            )
        return redirect(self.get_success_url())


class GroupListView(ListView):

    model = Group
    template_name = 'ojuser/group_list.html'

    def get_queryset(self):
        return self.request.user.groups.all()


class GroupDetailView(DetailView):

    model = Group
    template_name = 'ojuser/group_detail.html'

    def get_context_data(self, **kwargs):
        context = super(GroupDetailView, self).get_context_data(**kwargs)
        ob = context['object']
        context['admins'] = ob.profile.admins.all()
        context['parents'] = ob.profile.parents()
        context['children'] = ob.profile.children.all()
        return context


class GroupCreateView(TemplateView):
    template_name = 'ojuser/group_create_form.html'

    def post(self, request, *args, **kwargs):
        context = self.get_context_data()
        group_form = context["group_form"]
        group_profile_form = context["group_profile_form"]
        if group_form.is_valid() and group_profile_form.is_valid():
            group = group_form.save()
            group_profile_form = GroupProfileForm(request.POST, instance=group.profile)
            group_profile_form.superadmin = self.request.user
            group_profile_form.save()
            return HttpResponseRedirect(reverse('mygroup-member', args=[group.pk, ]))
        return super(GroupCreateView, self).render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super(GroupCreateView, self).get_context_data(**kwargs)

        group_form = GroupForm(self.request.POST or None)
        group_profile_form = GroupProfileForm(self.request.POST or None)
        context["group_form"] = group_form
        context["group_profile_form"] = group_profile_form

        return context


class GroupUpdateView(TemplateView):
    template_name = 'ojuser/group_update_form.html'

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        self.group_form = GroupForm(self.request.POST, instance=self.object)
        self.group_profile_form = GroupProfileForm(self.request.POST, instance=self.object.profile)
        if self.group_form.is_valid() and self.group_profile_form.is_valid():
            self.group_form.save()
            self.group_profile_form.superadmin = self.request.user
            self.group_profile_form.save()
            return HttpResponseRedirect(reverse('mygroup-member', args=[context['pk'], ]))
        return super(GroupUpdateView, self).render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super(GroupUpdateView, self).get_context_data(**kwargs)
        self.pk = self.kwargs['pk']
        qs = Group.objects.all()
        self.object = get_object_or_404(qs, pk=self.pk)

        self.group_form = GroupForm(instance=self.object)
        self.group_profile_form = GroupProfileForm(instance=self.object.profile)

        context["group_form"] = self.group_form
        context["group_profile_form"] = self.group_profile_form
        context['pk'] = self.pk

        return context


class UserAddView(TemplateView):
    template_name = 'ojuser/user_add.html'

    def get_context_data(self, **kwargs):
        context = super(UserAddView, self).get_context_data(**kwargs)
        return context


class GroupAddMemberView(TemplateView):
    template_name = 'ojuser/group_add_member.html'


class GroupMemberView(TemplateView):
    template_name = 'ojuser/group_member.html'

    def get_context_data(self, pk=None, **kwargs):
        context = super(GroupMemberView, self).get_context_data(**kwargs)
        group = Group.objects.get(pk=pk)
        group_users = group.user_set.all()
        group_users_table = GroupUserTable(group_users)
        RequestConfig(self.request).configure(group_users_table)
        context['group_users_table'] = group_users_table
        context['pk'] = pk
        return context
