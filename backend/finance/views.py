from decimal import Decimal
import csv
import io
from datetime import datetime
from uuid import UUID

from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Sum
from django.http import HttpResponse
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from django.db import models
from rest_framework import status, viewsets
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated
from .permissions import IsGroupMember, IsGroupOwner, CanManageCategory, CanManageFinancialOperation
from rest_framework.response import Response
from rest_framework.parsers import FormParser, MultiPartParser

from .models import (
    Category,
    FinancialOperation,
    Group,
    GroupMembership,
    GroupRole,
)
from .serializers import (
    CategorySerializer,
    FinancialOperationSerializer,
    GroupMembershipSerializer,
    GroupSerializer,
    RegistrationSerializer,
)


class RegistrationView(CreateAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = []

class GroupViewSet(viewsets.ModelViewSet):
    serializer_class = GroupSerializer

    def get_queryset(self):
        return Group.objects.filter(
            memberships__user=self.request.user
        ).distinct()

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticated]
        elif self.action == 'list':
            permission_classes = [IsAuthenticated]
        elif self.action == 'retrieve':
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

    def destroy(self, request, *args, **kwargs):
        group = self.get_object()
        with transaction.atomic():
            Group.objects.select_for_update().get(pk=group.pk)
            FinancialOperation.objects.filter(group=group).delete()
            return super().destroy(request, *args, **kwargs)

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

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="operations.csv"'
        response.write('\ufeff')
        writer = csv.writer(response, delimiter=';')
        writer.writerow(['Дата', 'Тип', 'Сумма, ₽', 'Категория', 'Группа', 'Описание'])
        def safe_cell(value):
            value = str(value or '')
            return "'" + value if value[:1] in ('=', '+', '-', '@', '\t', '\r') else value

        for operation in self.get_queryset():
            amount = f'{operation.amount:,.2f}'.replace(',', '\u00a0').replace('.', ',')
            writer.writerow([
                operation.date.strftime('%d.%m.%Y'),
                'Доход' if operation.type == 'INCOME' else 'Расход',
                amount,
                safe_cell(operation.category.name),
                safe_cell(operation.group.name if operation.group else 'Личная'),
                safe_cell(operation.description),
            ])
        return response

    @action(
        detail=False, methods=['post'], url_path='import-csv',
        parser_classes=[MultiPartParser, FormParser],
    )
    def import_csv(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return Response({'file': 'Загрузите CSV-файл в поле file.'}, status=400)
        try:
            content = upload.read().decode('utf-8-sig')
            first_line = content.splitlines()[0] if content.splitlines() else ''
            delimiter = ';' if first_line.count(';') > first_line.count(',') else ','
            reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
            aliases = {
                'date': 'date', 'дата': 'date',
                'type': 'type', 'тип': 'type', 'тип операции': 'type',
                'amount': 'amount', 'сумма': 'amount', 'сумма, ₽': 'amount', 'сумма ₽': 'amount',
                'category': 'category', 'категория': 'category',
                'group': 'group', 'группа': 'group',
                'description': 'description', 'описание': 'description',
            }
            source_columns = {
                aliases[field.strip().casefold()]: field
                for field in (reader.fieldnames or [])
                if field and field.strip().casefold() in aliases
            }
            required = {'date', 'type', 'amount', 'category'}
            if not required.issubset(source_columns):
                return Response({'file': 'Нужны столбцы даты, типа, суммы и категории. Поддерживаются русский и старый английский формат.'}, status=400)

            def value_for(row, field):
                value = row.get(source_columns.get(field, ''), '')
                return value.strip() if isinstance(value, str) else value

            def is_uuid(value):
                try:
                    UUID(str(value))
                    return True
                except (ValueError, TypeError, AttributeError):
                    return False

            created = 0
            with transaction.atomic():
                for row_number, row in enumerate(reader, start=2):
                    date_value = value_for(row, 'date')
                    try:
                        date_value = datetime.strptime(date_value, '%d.%m.%Y').date().isoformat() if '.' in date_value else date_value
                    except ValueError:
                        transaction.set_rollback(True)
                        return Response({'row': row_number, 'errors': {'date': 'Используйте дату в формате ДД.ММ.ГГГГ или ГГГГ-ММ-ДД.'}}, status=400)

                    type_value = value_for(row, 'type')
                    type_value = {'доход': 'INCOME', 'расход': 'EXPENSE'}.get(type_value.casefold(), type_value.upper())

                    amount_value = value_for(row, 'amount').replace('₽', '').replace('руб.', '').replace('\u00a0', '').replace(' ', '')
                    if ',' in amount_value and '.' in amount_value:
                        if amount_value.rfind(',') > amount_value.rfind('.'):
                            amount_value = amount_value.replace('.', '').replace(',', '.')
                        else:
                            amount_value = amount_value.replace(',', '')
                    else:
                        amount_value = amount_value.replace(',', '.')

                    group_value = value_for(row, 'group')
                    group_id = None
                    if group_value and group_value.casefold() not in {'личная', '—', '-'}:
                        if is_uuid(group_value):
                            group_id = group_value
                        else:
                            matching_groups = Group.objects.filter(
                                name__iexact=group_value,
                                memberships__user=request.user,
                            ).distinct()
                            if matching_groups.count() != 1:
                                transaction.set_rollback(True)
                                return Response({'row': row_number, 'errors': {'group': 'Группа не найдена или её название неоднозначно.'}}, status=400)
                            group_id = str(matching_groups.first().id)

                    category_value = value_for(row, 'category')
                    category_id = category_value
                    if not is_uuid(category_value):
                        matching_categories = Category.objects.filter(name__iexact=category_value, type=type_value)
                        if group_id:
                            matching_categories = matching_categories.filter(group_id=group_id)
                        else:
                            matching_categories = matching_categories.filter(group__isnull=True, user=request.user)
                        if matching_categories.count() != 1:
                            transaction.set_rollback(True)
                            return Response({'row': row_number, 'errors': {'category': 'Категория не найдена или её название неоднозначно.'}}, status=400)
                        category_id = str(matching_categories.first().id)

                    serializer = self.get_serializer(data={
                        'date': date_value, 'type': type_value,
                        'amount': amount_value, 'category': category_id,
                        'group': group_id,
                        'description': value_for(row, 'description') or '',
                    })
                    if not serializer.is_valid():
                        transaction.set_rollback(True)
                        return Response({'row': row_number, 'errors': serializer.errors}, status=400)
                    serializer.save(user=request.user)
                    created += 1
            return Response({'created': created}, status=201)
        except (UnicodeDecodeError, csv.Error) as exc:
            return Response({'file': f'Некорректный CSV: {exc}'}, status=400)

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
        with transaction.atomic():
            group = Group.objects.select_for_update().get(pk=self.kwargs['group_pk'])
            if serializer.validated_data.get('role') == GroupRole.OWNER and GroupMembership.objects.filter(
                group=group,
                role=GroupRole.OWNER,
            ).exists():
                raise ValidationError({
                    'role': 'В группе уже есть владелец. Назначить второго владельца нельзя.'
                })
            serializer.save(group=group)

    def update(self, request, *args, **kwargs):
        membership = self.get_object()
        new_role = request.data.get('role', membership.role)
        with transaction.atomic():
            Group.objects.select_for_update().get(pk=membership.group_id)
            if membership.role == GroupRole.OWNER and new_role != GroupRole.OWNER and GroupMembership.objects.filter(
                group=membership.group, role=GroupRole.OWNER,
            ).count() <= 1:
                return Response(
                    {'detail': 'Нельзя понизить единственного владельца группы.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        membership = self.get_object()
        with transaction.atomic():
            Group.objects.select_for_update().get(pk=membership.group_id)
            if membership.role == GroupRole.OWNER and GroupMembership.objects.filter(
                group=membership.group, role=GroupRole.OWNER,
            ).count() <= 1:
                return Response(
                    {'detail': 'Нельзя удалить единственного владельца группы.'},
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

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        if category.financial_operations.exists():
            return Response(
                {'detail': 'Нельзя удалить категорию, которая используется в операциях.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {'detail': 'Нельзя удалить категорию, которая используется в операциях.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
