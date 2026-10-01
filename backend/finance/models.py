import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username

class Group(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    name = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class GroupRole(models.TextChoices):
    OWNER = 'OWNER', 'Владелец'
    MEMBER = 'MEMBER', 'Участник'
    OBSERVER = 'OBSERVER', 'Наблюдатель'

class GroupMembership(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='group_memberships'
    )

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='memberships'
    )

    role = models.CharField(
        max_length=20,
        choices=GroupRole.choices
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'group'],
                name='unique_user_group_membership'
            )
        ]

    def __str__(self):
        return f'{self.user.username} — {self.group.name}'

class CategoryType(models.TextChoices):
    INCOME = 'INCOME', 'Доход'
    EXPENSE = 'EXPENSE', 'Расход'


class Category(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='categories'
    )

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='categories'
    )

    name = models.CharField(max_length=255)

    type = models.CharField(
        max_length=10,
        choices=CategoryType.choices
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class FinancialOperationType(models.TextChoices):
    INCOME = 'INCOME', 'Доход'
    EXPENSE = 'EXPENSE', 'Расход'


class FinancialOperation(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='financial_operations'
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='financial_operations'
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='financial_operations'
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    type = models.CharField(
        max_length=10,
        choices=FinancialOperationType.choices
    )

    date = models.DateField()

    description = models.TextField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name='financial_operation_amount_positive'
            )
        ]

    def __str__(self):
        return f'{self.amount} — {self.type}'