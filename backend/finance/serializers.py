from rest_framework import serializers

from .models import Group, GroupMembership, Category, FinancialOperation


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = (
            'id',
            'name',
            'created_at',
        )


class GroupMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMembership
        fields = (
            'id',
            'user',
            'group',
            'role',
            'created_at',
        )


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
        group = attrs.get('group')
        user = self.context['request'].user

        if group is not None:
            if not GroupMembership.objects.filter(
                user=user,
                group=group,
            ).exists():
                raise serializers.ValidationError(
                    'Пользователь не является участником указанной группы.'
                )

        return attrs


class FinancialOperationSerializer(serializers.ModelSerializer):
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
            if not GroupMembership.objects.filter(
                user=user,
                group=group,
            ).exists():
                raise serializers.ValidationError(
                    'Пользователь не является участником указанной группы.'
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