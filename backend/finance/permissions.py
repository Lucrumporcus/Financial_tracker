from rest_framework.permissions import BasePermission

from .models import GroupMembership, GroupRole


class IsGroupMember(BasePermission):
    """
    Доступ только участникам указанной группы.
    """

    def has_permission(self, request, view):
        group_id = view.kwargs.get('group_pk') or view.kwargs.get('pk')

        if not group_id or not request.user.is_authenticated:
            return False

        return GroupMembership.objects.filter(
            user=request.user,
            group_id=group_id,
        ).exists()


class IsGroupOwner(BasePermission):
    """
    Доступ только владельцу указанной группы.
    """

    def has_permission(self, request, view):
        group_id = view.kwargs.get('group_pk') or view.kwargs.get('pk')

        if not group_id or not request.user.is_authenticated:
            return False

        return GroupMembership.objects.filter(
            user=request.user,
            group_id=group_id,
            role=GroupRole.OWNER,
        ).exists()

class CanManageCategory(BasePermission):
    """
    Разрешает изменение и удаление категории:
    - личной категории — только её владельцу;
    - групповой категории — только владельцу группы.
    """

    def has_object_permission(self, request, view, obj):
        if obj.group_id is None:
            return obj.user_id == request.user.id

        return GroupMembership.objects.filter(
            user=request.user,
            group_id=obj.group_id,
            role=GroupRole.OWNER,
        ).exists()


class CanManageFinancialOperation(BasePermission):
    """
    Разрешает изменение и удаление финансовой операции:
    - личной операции — только её создателю;
    - групповой операции — владельцу группы или её создателю,
      если он является участником с ролью MEMBER.
    """

    def has_object_permission(self, request, view, obj):
        if obj.group_id is None:
            return obj.user_id == request.user.id

        membership = GroupMembership.objects.filter(
            user=request.user,
            group_id=obj.group_id,
        ).first()

        if membership is None:
            return False

        if membership.role == GroupRole.OWNER:
            return True

        if membership.role == GroupRole.MEMBER:
            return obj.user_id == request.user.id

        return False