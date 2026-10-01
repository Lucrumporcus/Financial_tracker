from decimal import Decimal

from django.db.models import Sum
from rest_framework.decorators import action

from django.db import models
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from .permissions import (
    IsGroupMember,
    IsGroupOwner,
    CanManageCategory,
    CanManageFinancialOperation,
)
from rest_framework.response import Response

from .models import (
    Category,
    FinancialOperation,
    Group,
    GroupMembership,
    GroupRole,
)
from .permissions import IsGroupMember, IsGroupOwner
from .serializers import (
    CategorySerializer,
    FinancialOperationSerializer,
    GroupMembershipSerializer,
    GroupSerializer,
)

class GroupViewSet(viewsets.ModelViewSet):
    serializer_class = GroupSerializer

    def get_queryset(self):
        return Group.objects.filter(
            memberships__user=self.request.user
        ).distinct()

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticated]
        elif self.action in ['list', 'retrieve']:
            permission_classes = [
                IsAuthenticated,
                IsGroupMember,
            ]
        else:
            permission_classes = [
                IsAuthenticated,
                IsGroupOwner,
            ]

        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        group = serializer.save()

        GroupMembership.objects.create(
            user=self.request.user,
            group=group,
            role=GroupRole.OWNER,
        )

class FinancialOperationViewSet(viewsets.ModelViewSet):
    serializer_class = FinancialOperationSerializer
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'create', 'summary']:
            permission_classes = [
                IsAuthenticated,
            ]
        else:
            permission_classes = [
                IsAuthenticated,
                CanManageFinancialOperation,
            ]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user

        queryset = FinancialOperation.objects.filter(
            models.Q(user=user)
            | models.Q(
                group__memberships__user=user
            )
        ).select_related(
            'user',
            'group',
            'category',
        ).distinct()

        operation_type = self.request.query_params.get('type')
        category_id = self.request.query_params.get('category')
        group_id = self.request.query_params.get('group')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')

        if operation_type:
            queryset = queryset.filter(
                type=operation_type
            )

        if category_id:
            queryset = queryset.filter(
                category_id=category_id
            )

        if group_id:
            queryset = queryset.filter(
                group_id=group_id
            )

        if date_from:
            queryset = queryset.filter(
                date__gte=date_from
            )

        if date_to:
            queryset = queryset.filter(
                date__lte=date_to
            )

        return queryset

    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user
        )

    @action(
        detail=False,
        methods=['get'],
        url_path='summary',
    )
    def summary(self, request):
        queryset = self.get_queryset()

        income = queryset.filter(
            type='INCOME'
        ).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        expense = queryset.filter(
            type='EXPENSE'
        ).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        balance = income - expense

        return Response({
            'income': income,
            'expense': expense,
            'balance': balance,
        })

class GroupMembershipViewSet(viewsets.ModelViewSet):
    serializer_class = GroupMembershipSerializer

    def get_queryset(self):
        return GroupMembership.objects.filter(
            group_id=self.kwargs['group_pk'],
            group__memberships__user=self.request.user,
        ).select_related(
            'user',
            'group',
        )

    def get_permissions(self):
        if self.action == 'list' or self.action == 'retrieve':
            permission_classes = [
                IsAuthenticated,
                IsGroupMember,
            ]
        else:
            permission_classes = [
                IsAuthenticated,
                IsGroupOwner,
            ]

        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        serializer.save(
            group_id=self.kwargs['group_pk']
        )

    def destroy(self, request, *args, **kwargs):
        membership = self.get_object()

        if membership.role == GroupRole.OWNER:
            owner_count = GroupMembership.objects.filter(
                group=membership.group,
                role=GroupRole.OWNER,
            ).count()

            if owner_count <= 1:
                return Response(
                    {
                        'detail': 'Нельзя удалить единственного владельца группы.'
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return super().destroy(request, *args, **kwargs)

class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'create']:
            permission_classes = [
                IsAuthenticated,
            ]
        else:
            permission_classes = [
                IsAuthenticated,
                CanManageCategory,
            ]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user

        return Category.objects.filter(
            models.Q(user=user)
            | models.Q(
                group__memberships__user=user
            )
        ).distinct()

    def perform_create(self, serializer):
        group = serializer.validated_data.get('group')

        if group is None:
            serializer.save(user=self.request.user)
            return

        is_owner = GroupMembership.objects.filter(
            user=self.request.user,
            group=group,
            role=GroupRole.OWNER,
        ).exists()

        if not is_owner:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                'Только владелец группы может создавать групповые категории.'
            )

        serializer.save(user=None)

    def perform_create(self, serializer):
        group = serializer.validated_data.get('group')

        if group is None:
            serializer.save(user=self.request.user)
            return

        is_owner = GroupMembership.objects.filter(
            user=self.request.user,
            group=group,
            role=GroupRole.OWNER,
        ).exists()

        if not is_owner:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                'Только владелец группы может создавать групповые категории.'
            )

        serializer.save()