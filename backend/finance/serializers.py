from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import Group, GroupMembership, GroupRole, Category, FinancialOperation, User
from decimal import Decimal


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password')
        read_only_fields = ('id',)

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = (
            'id',
            'name',
            'created_at',
        )


class GroupMembershipSerializer(serializers.ModelSerializer):
    invite_username = serializers.CharField(write_only=True, required=False)
    member_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = GroupMembership
        fields = (
            'id',
            'user',
            'invite_username',
            'member_username',
            'group',
            'role',
            'created_at',
        )
        read_only_fields = ('id', 'group', 'created_at')
        extra_kwargs = {'user': {'required': False}}

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None:
            fields['user'].read_only = True
            fields['invite_username'].read_only = True
        return fields

    def validate(self, attrs):
        invite_username = attrs.pop('invite_username', None)
        if invite_username:
            try:
                attrs['user'] = User.objects.get(username=invite_username, is_active=True)
            except User.DoesNotExist as exc:
                raise serializers.ValidationError({
                    'invite_username': 'Активный пользователь с таким именем не найден.'
                }) from exc

        user = attrs.get('user', self.instance.user if self.instance else None)
        if user is None:
            raise serializers.ValidationError({
                'invite_username': 'Укажите имя пользователя или его ID.'
            })

        group_id = self.context['view'].kwargs.get('group_pk')
        if self.instance is None and GroupMembership.objects.filter(
            user=user, group_id=group_id,
        ).exists():
            raise serializers.ValidationError({
                'invite_username': 'Пользователь уже состоит в этой группе.'
            })

        group_id = self.instance.group_id if self.instance else group_id
        role = attrs.get('role', self.instance.role if self.instance else None)
        if role == GroupRole.OWNER:
            owners = GroupMembership.objects.filter(
                group_id=group_id,
                role=GroupRole.OWNER,
            )
            if self.instance:
                owners = owners.exclude(pk=self.instance.pk)
            if owners.exists():
                raise serializers.ValidationError({
                    'role': 'В группе уже есть владелец. Назначить второго владельца нельзя.'
                })
        return attrs


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = (
            'id',
            'user',
            'group',
            'name',
            'type',
            'created_at',
        )
        read_only_fields = (
            'id',
            'user',
            'created_at',
        )

    def validate(self, attrs):
        group = attrs.get('group', self.instance.group if self.instance else None)
        user = self.context['request'].user

        if self.instance and 'group' in attrs and group != self.instance.group:
            raise serializers.ValidationError(
                'После создания нельзя менять область действия категории.'
            )

        if group is not None:
            if not GroupMembership.objects.filter(
                user=user,
                group=group,
            ).exists():
                raise serializers.ValidationError(
                    'Пользователь не является участником указанной группы.'
                )
            if not GroupMembership.objects.filter(
                user=user, group=group, role='OWNER'
            ).exists():
                raise serializers.ValidationError(
                    'Только владелец группы может управлять её категориями.'
                )

        category_type = attrs.get('type', self.instance.type if self.instance else None)
        if self.instance and category_type != self.instance.type and self.instance.financial_operations.exists():
            raise serializers.ValidationError(
                {'type': 'Нельзя менять тип категории, к которой привязаны операции.'}
            )

        return attrs


class FinancialOperationSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))

    class Meta:
        model = FinancialOperation
        fields = (
            'id',
            'group',
            'user',
            'category',
            'amount',
            'type',
            'date',
            'description',
            'created_at',
        )
        read_only_fields = (
            'id',
            'user',
            'created_at',
        )

    def validate(self, attrs):
        request = self.context['request']
        user = request.user

        instance = self.instance

        group = attrs.get(
            'group',
            instance.group if instance else None
        )

        category = attrs.get(
            'category',
            instance.category if instance else None
        )

        operation_type = attrs.get(
            'type',
            instance.type if instance else None
        )

        if group is None:
            if category.group_id is not None:
                raise serializers.ValidationError(
                    'Личная операция должна использовать личную категорию.'
                )

            if category.user_id != user.id:
                raise serializers.ValidationError(
                    'Нельзя использовать чужую личную категорию.'
                )

        else:
            membership = GroupMembership.objects.filter(
                user=user,
                group=group,
            ).first()
            if membership is None:
                raise serializers.ValidationError(
                    'Пользователь не является участником указанной группы.'
                )
            if self.instance is None and membership.role == 'OBSERVER':
                raise serializers.ValidationError(
                    'Наблюдатель не может создавать операции в группе.'
                )

            if category.group_id != group.id:
                raise serializers.ValidationError(
                    'Категория должна принадлежать указанной группе.'
                )

        if category.type != operation_type:
            raise serializers.ValidationError(
                'Тип операции должен совпадать с типом категории.'
            )

        return attrs
